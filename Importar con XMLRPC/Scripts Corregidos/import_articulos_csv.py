#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import xmlrpc.client
import csv
import traceback
import time
import logging
import sys
import re

# ---------- CONFIG ----------
url = "http://localhost:8073"
db = "test"
username = "admin"
password = "admin"

csv_path = "articulos.csv"
error_log_path = "import_articulos_errors.txt"

COL_IMPUESTOS = 'taxes_id/id' 
COL_PROVEEDOR = 'seller_ids'
COL_CATEGORIA = 'categ_id'
COL_MARCA = 'product_brand_id'
COL_CATEGORIA_POS = 'pos_categ_id'

TYPE_MAPPING = {
    'almacenable': 'product',
    'consumible': 'consu',
    'servicio': 'service'
}

DEFAULT_CHUNK_SIZE = 200
MAX_RETRIES = 3
SLEEP_BETWEEN_CHUNKS = 0.2
PROGRESS_REPORT_INTERVAL = 1000
# -----------------------------

start_time = time.time()

logging.basicConfig(filename=error_log_path, level=logging.INFO,
                    format="%(asctime)s - %(levelname)s - %(message)s")

# Conectar XML-RPC
try:
    common = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/common')
    uid = common.authenticate(db, username, password, {})
    if not uid:
        raise Exception("Autenticación fallida.")
    models = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/object')
    print("✅ Conexión a Odoo exitosa.")
except Exception as e:
    print(f"❌ Error de conexión: {e}")
    sys.exit(1)

# ---------- CACHES ----------
partners_cache = {}
categories_cache = {}
brands_cache = {}
pos_categories_cache = {}
taxes_normalized_cache = {}

# ---------- UTILS ----------
def has_value(v):
    return v is not None and str(v).strip() != ""

def parse_boolean(v):
    s = str(v).strip().lower()
    return s in ("1", "true", "verdadero", "si", "s", "y", "yes") if has_value(v) else False

def normalize_key(s):
    """Limpia la cadena para usarla como clave de caché: strip, upper, y cambia ',' por '.'"""
    return str(s).strip().upper().replace(',', '.')

def collect_unique_values_from_csv(column_name):
    values = set()
    try:
        with open(csv_path, mode='r', newline='', encoding='utf-8', errors='replace') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                if has_value(row.get(column_name)):
                    values.add(str(row[column_name]).strip())
    except FileNotFoundError:
        print(f"❌ ERROR: No se encontró el archivo '{csv_path}'")
        sys.exit(1)
    return values

def preload_or_create_entities(model, names_set, cache, extra_create_vals=None):
    if not names_set:
        return
    
    names_list = list(names_set)
    existing_records = models.execute_kw(db, uid, password, model, 'search_read',
                                         [[['name', 'in', names_list]]], {'fields': ['id', 'name']})
    
    found_names = set()
    for record in existing_records:
        clean_name = str(record['name']).strip()
        cache[normalize_key(clean_name)] = record['id']
        found_names.add(clean_name)
    
    new_names_to_create = names_set - found_names
    
    if new_names_to_create:
        sorted_new_names = sorted(list(new_names_to_create))
        vals_to_create = []
        base_vals = extra_create_vals or {}
        for name in sorted_new_names:
            vals = {'name': name}
            vals.update(base_vals)
            vals_to_create.append(vals)
        try:
            new_ids = models.execute_kw(db, uid, password, model, 'create', [vals_to_create])
            if isinstance(new_ids, int): 
                new_ids = [new_ids]
            for i, name in enumerate(sorted_new_names):
                if i < len(new_ids):
                    cache[normalize_key(name)] = new_ids[i]
        except Exception as e:
            logging.error(f"Fallo en bulk create de '{model}': {e}")
            
# ----------------------------------------------------
# FASE 1: PRECARGA IMPUESTOS Y ENTIDADES
# ----------------------------------------------------
print("\n--- FASE 1: PRECARGA TOTAL DE DATOS ---")

taxes = models.execute_kw(db, uid, password, 'account.tax', 'search_read', [[]], {'fields': ['id', 'name']})
for tax in taxes:
    name = str(tax.get('name', '')).strip()
    tax_id = tax.get('id')
    taxes_normalized_cache[normalize_key(name)] = tax_id

print(f"✅ Precargados {len(taxes_normalized_cache)} impuestos usando clave normalizada.")

unique_partners = collect_unique_values_from_csv(COL_PROVEEDOR)
unique_brands = collect_unique_values_from_csv(COL_MARCA)
unique_categories = collect_unique_values_from_csv(COL_CATEGORIA)
unique_pos_categories = collect_unique_values_from_csv(COL_CATEGORIA_POS)

preload_or_create_entities('res.partner', unique_partners, partners_cache, {'supplier_rank': 1})
preload_or_create_entities('product.brand', unique_brands, brands_cache)
preload_or_create_entities('product.category', unique_categories, categories_cache)
preload_or_create_entities('pos.category', unique_pos_categories, pos_categories_cache)

# ----------------------------------------------------
# FASE 2: PROCESAMIENTO Y CREACIÓN DE PRODUCTOS
# ----------------------------------------------------
print("\n--- FASE 2: PROCESAMIENTO Y CREACIÓN DE PRODUCTOS ---")

products_to_create = []
supplier_links = []
sales_tax_links = [] # NUEVA LISTA para los IDs que necesitan actualizar el impuesto de venta

def find_tax_ids_for_csv_value(csv_tax_value):
    result_ids = []
    if not has_value(csv_tax_value):
        return result_ids
        
    parts = [p.strip() for p in re.split(r'[;,|]', csv_tax_value) if p.strip()] 
    
    for p in parts:
        norm = normalize_key(p)
        if norm in taxes_normalized_cache:
            tax_id = taxes_normalized_cache[norm]
            if tax_id not in result_ids:
                result_ids.append(tax_id)
        else:
            logging.warning(f"Impuesto '{p}' (Normalizado: '{norm}') no encontrado en caché de Odoo. Se omite.")

    return result_ids

with open(csv_path, mode='r', newline='', encoding='utf-8', errors='replace') as csvfile:
    reader = csv.DictReader(csvfile)
    for idx, row in enumerate(reader, start=1):
        if idx % PROGRESS_REPORT_INTERVAL == 0:
            print(f"[PROGRESO] Procesando fila {idx} del CSV...")

        try:
            if not has_value(row.get('name')): continue

            raw_type = str(row.get('detailed_type','')).strip().lower()
            product_type = TYPE_MAPPING.get(raw_type, 'product')
            raw_description = str(row.get('description','')).strip()
            clean_description = raw_description.replace('<p>', '').replace('</p>', '').strip() or False

            # Obtenemos los booleanos del CSV una sola vez
            sale_ok = parse_boolean(row.get('sale_ok'))
            purchase_ok = parse_boolean(row.get('purchase_ok'))

            standard_price = 0
            list_price = 0
            try:
                standard_price = float(str(row.get('standard_price', 0)).replace(',', '.') or 0)
            except: pass
            try:
                list_price = float(str(row.get('list_price', 0)).replace(',', '.') or 0)
            except: pass
            
            vals = {
                'name': str(row['name']).strip(),
                'description': clean_description,
                'type': product_type,
                'default_code': str(row.get('default_code','')).strip() or False,
                'barcode': str(row.get('barcode','')).strip() or False,
                'standard_price': standard_price,
                'list_price': list_price,
                'purchase_ok': purchase_ok,
                'sale_ok': sale_ok,
                'available_in_pos': parse_boolean(row.get('available_in_pos')),
                'purchase_method': str(row.get('purchase_method', 'purchase')).strip(),
                'invoice_policy': 'delivery' if sale_ok else 'order',
            }

            # Asignación de Impuestos (Lógica Separada)
            if has_value(row.get(COL_IMPUESTOS)):
                csv_tax_cell = str(row[COL_IMPUESTOS]).strip()
                tax_ids = find_tax_ids_for_csv_value(csv_tax_cell)
                
                if tax_ids:
                    # 1. IMPUESTO DE COMPRA: Lo asignamos para el CREATE inicial (el que SÍ funciona)
                    if purchase_ok:
                        vals['supplier_taxes_id'] = [(6, 0, tax_ids)]
                        
                    # 2. IMPUESTO DE VENTA: NO lo asignamos en el CREATE. Guardamos el enlace para la FASE 3b
                    if sale_ok:
                        # Guardamos el índice del producto (que es el tamaño actual de products_to_create) y el ID de los impuestos de venta a asignar
                        sales_tax_links.append((len(products_to_create), tax_ids)) 
                else:
                    logging.warning(f"Fila {idx} - Impuesto(s) '{csv_tax_cell}' no encontrado(s). Se omiten impuestos para este producto.")


            # Categ (Usa clave normalizada)
            if has_value(row.get(COL_CATEGORIA)):
                cat_name_key = normalize_key(row[COL_CATEGORIA])
                if cat_name_key in categories_cache:
                    vals['categ_id'] = categories_cache[cat_name_key]
                else:
                    logging.warning(f"Fila {idx} - Categoría '{row[COL_CATEGORIA].strip()}' no encontrada en caché. Se salta producto.")
                    continue

            # Marca (Usa clave normalizada)
            if has_value(row.get(COL_MARCA)):
                brand_name_key = normalize_key(row[COL_MARCA])
                if brand_name_key in brands_cache:
                    vals['product_brand_id'] = brands_cache[brand_name_key]

            # POS category (Usa clave normalizada)
            if has_value(row.get(COL_CATEGORIA_POS)):
                pos_cat_name_key = normalize_key(row[COL_CATEGORIA_POS])
                if pos_cat_name_key in pos_categories_cache:
                    vals['pos_categ_id'] = pos_categories_cache[pos_cat_name_key]

            if 'categ_id' not in vals:
                logging.error(f"Fila {idx} - ERROR CRÍTICO: No se pudo asignar 'categ_id'. Se salta producto.")
                continue

            products_to_create.append(vals)

            if has_value(row.get(COL_PROVEEDOR)):
                supplier_name = str(row[COL_PROVEEDOR]).strip()
                supplier_links.append((len(products_to_create) - 1, normalize_key(supplier_name)))

        except Exception as e:
            logging.error(f"Fila {idx} - Error procesando: {e}\n{traceback.format_exc()}")

# Creación en lotes
created_ids = []
if products_to_create:
    print(f"📦 Creando {len(products_to_create)} productos en Odoo...")
    for i in range(0, len(products_to_create), DEFAULT_CHUNK_SIZE):
        chunk = products_to_create[i:i + DEFAULT_CHUNK_SIZE]
        for attempt in range(MAX_RETRIES):
            try:
                ids = models.execute_kw(db, uid, password, 'product.template', 'create', [chunk])
                created_ids.extend(ids)
                time.sleep(SLEEP_BETWEEN_CHUNKS)
                break
            except Exception as e:
                logging.error(f"Fallo creando chunk [{i}:{i+len(chunk)}] (Intento {attempt + 1}/{MAX_RETRIES}): {e}")
                if attempt == MAX_RETRIES - 1:
                    print(f"❌ Fallo persistente creando chunk de productos [{i}:{i+len(chunk)}]. Revisar '{error_log_path}'")
                time.sleep(1 + attempt)

# ----------------------------------------------------
## FASE 3: ASIGNACIÓN OPTIMIZADA DE PROVEEDORES
# ----------------------------------------------------
print("\n--- FASE 3: ASIGNACIÓN OPTIMIZADA DE PROVEEDORES ---")

if supplier_links and created_ids:
    product_idx_to_id_map = {i: id for i, id in enumerate(created_ids)}
    all_product_ids = list(product_idx_to_id_map.values())
    
    valid_partner_names = set(link[1] for link in supplier_links)
    valid_partner_ids = [partners_cache[name] for name in valid_partner_names if name in partners_cache]

    existing_rels_raw = models.execute_kw(db, uid, password, 'product.supplierinfo', 'search_read',
        [[('product_tmpl_id', 'in', all_product_ids), ('name', 'in', valid_partner_ids)]],
        {'fields': ['product_tmpl_id', 'name']})

    existing_rels_set = {(rec['product_tmpl_id'][0], rec['name'][0]) for rec in existing_rels_raw}

    supplierinfo_to_create = []
    for product_idx, partner_key in supplier_links:
        product_id = product_idx_to_id_map.get(product_idx)
        partner_id = partners_cache.get(partner_key) 

        if product_id and partner_id and (product_id, partner_id) not in existing_rels_set:
            supplierinfo_to_create.append({
                'product_tmpl_id': product_id,
                'name': partner_id
            })

    if supplierinfo_to_create:
        try:
            print(f"🔗 Creando {len(supplierinfo_to_create)} nuevas relaciones producto-proveedor...")
            models.execute_kw(db, uid, password, 'product.supplierinfo', 'create', [supplierinfo_to_create])
            print("    -> ✅ Relaciones creadas exitosamente.")
        except Exception as e:
            logging.error(f"Fallo creando supplierinfo: {e}")
            print(f"    -> ❌ Error creando relaciones: {e}")

# ----------------------------------------------------
# FINAL
# ----------------------------------------------------


end_time = time.time()
print("\n" + "="*70)
print(f"🏁 Importación completada en {end_time - start_time:.2f} segundos")
print(f"Total productos CREADOS: {len(created_ids)}")
print("="*70)
