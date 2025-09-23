"""
Script BULK ULTRA de importación de artículos a Odoo 15 vía XML-RPC
Lee: articulos.csv
Genera log de errores: import_articulos_errors.txt
"""

import xmlrpc.client
import csv
import traceback
import time

# ---------- CONFIG ----------
url = "http://localhost:8073"
db = "test"
username = "admin"
password = "admin"

csv_path = "articulos.csv"
error_log_path = "import_articulos_errors.txt"
# -----------------------------

start_time = time.time()

# Conectar XML-RPC
common = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/common')
uid = common.authenticate(db, username, password, {})
if not uid:
    raise Exception("Autenticación fallida. Revisa url/db/usuario/contraseña")
models = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/object')

# ---------- CACHE ----------
categories_cache = {}
pos_categories_cache = {}
brands_cache = {}
partners_cache = {}
taxes_cache = {}

# ---------- UTIL ----------
def bool_from_value(v):
    if v is None or str(v).strip() == "":
        return False
    if isinstance(v, bool):
        return v
    s = str(v).strip().lower()
    return s in ("1", "true", "verdadero", "si", "sí", "y", "yes")

def has_value(v):
    return v is not None and str(v).strip() != ""

def search_or_create_category(cat_name, parent_id=False):
    if not has_value(cat_name):
        return False
    key = (str(cat_name).strip(), parent_id)
    if key in categories_cache:
        return categories_cache[key]
    domain = [['name', '=', str(cat_name).strip()]]
    ids = models.execute_kw(db, uid, password, 'product.category', 'search', [domain], {'limit': 1})
    if ids:
        categories_cache[key] = ids[0]
        return ids[0]
    new_id = models.execute_kw(db, uid, password, 'product.category', 'create', [{'name': str(cat_name).strip(), **({'parent_id': parent_id} if parent_id else {})}])
    categories_cache[key] = new_id
    return new_id

def search_or_create_pos_category(name):
    if not has_value(name):
        return False
    key = str(name).strip()
    if key in pos_categories_cache:
        return pos_categories_cache[key]
    domain = [['name', '=', key]]
    ids = models.execute_kw(db, uid, password, 'pos.category', 'search', [domain], {'limit': 1})
    if ids:
        pos_categories_cache[key] = ids[0]
        return ids[0]
    new_id = models.execute_kw(db, uid, password, 'pos.category', 'create', [{'name': key}])
    pos_categories_cache[key] = new_id
    return new_id

def search_or_create_partner(name):
    if not has_value(name):
        return False
    key = str(name).strip()
    if key in partners_cache:
        return partners_cache[key]
    domain = [['name', '=', key]]
    ids = models.execute_kw(db, uid, password, 'res.partner', 'search', [domain], {'limit': 1})
    if ids:
        partners_cache[key] = ids[0]
        return ids[0]
    new_id = models.execute_kw(db, uid, password, 'res.partner', 'create', [{'name': key, 'supplier_rank': 1}])
    partners_cache[key] = new_id
    return new_id

def find_tax_by_name(name):
    if not has_value(name):
        return []
    key = str(name).strip()
    if key in taxes_cache:
        return taxes_cache[key]
    ids = models.execute_kw(db, uid, password, 'account.tax', 'search', [[['name', '=', key]]])
    taxes_cache[key] = ids
    return ids

def try_assign_brand(vals, brand_name):
    if not has_value(brand_name):
        return
    key = str(brand_name).strip()
    if key in brands_cache:
        vals['product_brand_id'] = brands_cache[key]
        return
    try:
        brand_ids = models.execute_kw(db, uid, password, 'product.brand', 'search', [[['name', '=', key]]])
        if brand_ids:
            brands_cache[key] = brand_ids[0]
            vals['product_brand_id'] = brand_ids[0]
        else:
            new_brand_id = models.execute_kw(db, uid, password, 'product.brand', 'create', [{'name': key}])
            brands_cache[key] = new_brand_id
            vals['product_brand_id'] = new_brand_id
    except Exception as e:
        with open(error_log_path, "a", encoding="utf-8") as log:
            log.write(f"Error asignando marca '{brand_name}': {e}\n")
            log.write(traceback.format_exc() + "\n")
            log.write("-"*70 + "\n")

def create_or_update_supplierinfo(product_tmpl_id, partner_id):
    if not product_tmpl_id or not partner_id:
        return
    domain = [['name', '=', partner_id], ['product_tmpl_id', '=', product_tmpl_id]]
    existing = models.execute_kw(db, uid, password, 'product.supplierinfo', 'search', [domain], {'limit': 1})
    if not existing:
        models.execute_kw(db, uid, password, 'product.supplierinfo', 'create', [{'name': partner_id, 'product_tmpl_id': product_tmpl_id}])

# ---------- LEER CSV ----------
try:
    csvfile = open(csv_path, newline='', encoding='utf-8', errors='replace')
except UnicodeDecodeError:
    csvfile = open(csv_path, newline='', encoding='latin-1', errors='replace')

reader = csv.DictReader(csvfile)

with open(error_log_path, "w", encoding="utf-8") as log:
    log.write("LOG BULK ULTRA DE IMPORTACIÓN DE PRODUCTOS (ERRORES)\n")
    log.write("="*70 + "\n\n")

total = 0
ok_count = 0
fail_count = 0
new_products = []
update_products = []
supplier_bulk = []

for idx, row in enumerate(reader, start=1):
    total += 1
    try:
        name = row.get('name')
        if not has_value(name):
            raise Exception("Falta el campo 'name'")

        default_code = row.get('default_code')
        barcode = row.get('barcode')

        domain = []
        if has_value(default_code):
            domain = [['default_code', '=', str(default_code).strip()]]
        elif has_value(barcode):
            domain = [['barcode', '=', str(barcode).strip()]]

        product_ids = models.execute_kw(db, uid, password, 'product.template', 'search', [domain], {'limit': 1}) if domain else []
        product_tmpl_id = product_ids[0] if product_ids else False

        vals = {
            'name': str(name).strip(),
            'default_code': str(default_code).strip() if has_value(default_code) else False,
            'barcode': str(barcode).strip() if has_value(barcode) else False,
            'type': 'product',
            'purchase_ok': bool_from_value(row.get('purchase_ok')),
            'sale_ok': bool_from_value(row.get('sale_ok')),
        }

        # Precios
        for col in ['standard_price', 'list_price']:
            if col in row and has_value(row[col]):
                try:
                    vals[col] = float(str(row[col]).replace(',', ''))
                except:
                    pass

        # Categorías, POS, Taxes, Brand
        if has_value(row.get('categ_id')):
            vals['categ_id'] = search_or_create_category(row['categ_id'])
        if has_value(row.get('pos_categ_id')):
            vals['pos_categ_id'] = search_or_create_pos_category(row['pos_categ_id'])
        if has_value(row.get('taxes_id/id')):
            tax_ids = find_tax_by_name(row['taxes_id/id'])
            if tax_ids:
                vals['taxes_id'] = [(6, 0, tax_ids)]
        try_assign_brand(vals, row.get('product_brand_id'))
        if has_value(row.get('available_in_pos')):
            vals['available_in_pos'] = bool_from_value(row['available_in_pos'])

        if product_tmpl_id:
            update_products.append((product_tmpl_id, vals))
        else:
            new_products.append(vals)

        if has_value(row.get('seller_ids')):
            supplier_bulk.append((product_tmpl_id if product_tmpl_id else None, row.get('seller_ids')))

        ok_count += 1

    except Exception as e:
        fail_count += 1
        with open(error_log_path, "a", encoding="utf-8") as log:
            log.write(f"Fila {idx} - Producto: {row.get('name')}\n")
            log.write(f"Error: {str(e)}\n")
            log.write(traceback.format_exc() + "\n")
            log.write("-"*70 + "\n")

csvfile.close()

# ---------- BULK CREATE NUEVOS PRODUCTOS ----------
created_ids = []
if new_products:
    created_ids = models.execute_kw(db, uid, password, 'product.template', 'create', [new_products])
    if isinstance(created_ids, int):
        created_ids = [created_ids]

# Mapear supplier_bulk con productos recién creados
created_index = 0
updated_supplier_bulk = []
for product_tmpl_id, partner_val in supplier_bulk:
    if not has_value(partner_val):
        continue
    if product_tmpl_id:
        updated_supplier_bulk.append((product_tmpl_id, partner_val))
    else:
        if created_index < len(created_ids):
            updated_supplier_bulk.append((created_ids[created_index], partner_val))
            created_index += 1

# ---------- BULK WRITE EXISTENTES ----------
for product_id, vals in update_products:
    models.execute_kw(db, uid, password, 'product.template', 'write', [[product_id], vals])

# ---------- BULK SUPPLIERINFO ----------
for product_tmpl_id, partner_val in updated_supplier_bulk:
    partner_id = search_or_create_partner(partner_val)
    if product_tmpl_id and partner_id:
        create_or_update_supplierinfo(product_tmpl_id, partner_id)

end_time = time.time()
elapsed_time = end_time - start_time

print("Importación BULK ULTRA completada")
print(f"Total: {total}, Éxitosos: {ok_count}, Fallidos: {fail_count}")
print(f"Log de errores: {error_log_path}")
print(f"Tiempo de ejecución: {elapsed_time:.2f} segundos")
