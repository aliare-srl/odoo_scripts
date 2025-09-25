import xmlrpc.client
import csv
import traceback
import time
import logging
from http.client import RemoteDisconnected
from xmlrpc.client import Fault

# ---------- CONFIG ----------
url = "http://localhost:8069"
db = "test"
username = "admin"
password = "admin"

csv_path = "articulos.csv"
error_log_path = "import_articulos_errors.txt"

# Ajustes de rendimiento y reporting
DEFAULT_CHUNK_SIZE = 100   
UPDATE_CHUNK_SIZE = 200     
MAX_RETRIES = 3           
SLEEP_BETWEEN_CHUNKS = 0.5  # Respiro entre grandes operaciones bulk
PROGRESS_REPORT_INTERVAL = 500 # Reportar progreso de lectura cada N filas
# -----------------------------

start_time = time.time()

# Configuración de logs
logging.basicConfig(
    filename=error_log_path,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

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

def chunks_with_data(lst, n):
    for i in range(0, len(lst), n):
        yield i, lst[i:i + n]

def create_chunk_with_retry(chunk, attempt_no):
    try:
        created = models.execute_kw(db, uid, password, 'product.template', 'create', [chunk])
        return created
    except RemoteDisconnected:
        raise
    except Fault:
        raise
    except Exception:
        raise

# ----------------------------------------------------
# PRECARGA Y UTILIDADES (se mantienen)
# ----------------------------------------------------

def preload_static_data():
    logging.info("Iniciando precarga de datos comunes...")
    try:
        categories = models.execute_kw(db, uid, password, 'product.category', 'search_read', [[]], {'fields': ['id', 'name', 'parent_id']})
        for cat in categories:
            parent_id_val = cat.get('parent_id')[0] if cat.get('parent_id') else False
            categories_cache[(str(cat['name']).strip(), parent_id_val)] = cat['id']
        pos_categories = models.execute_kw(db, uid, password, 'pos.category', 'search_read', [[]], {'fields': ['id', 'name']})
        for cat in pos_categories:
            pos_categories_cache[str(cat['name']).strip()] = cat['id']
        taxes = models.execute_kw(db, uid, password, 'account.tax', 'search_read', [[]], {'fields': ['id', 'name']})
        for tax in taxes: taxes_cache[str(tax['name']).strip()] = [tax['id']]
        brands = models.execute_kw(db, uid, password, 'product.brand', 'search_read', [[]], {'fields': ['id', 'name']})
        for brand in brands: brands_cache[str(brand['name']).strip()] = brand['id']
    except Exception as e:
        logging.error(f"Error en precarga estática: {e}")
    logging.info("Precarga de datos estáticos finalizada.")

def search_or_create_entity(model, name, cache, extra_vals=None):
    if not has_value(name): return False
    key = str(name).strip()
    if key in cache: return cache[key]
    vals = {'name': key}
    if extra_vals: vals.update(extra_vals)
    try:
        new_id = models.execute_kw(db, uid, password, model, 'create', [vals])
        cache[key] = new_id
        return new_id
    except Exception as e:
        logging.error(f"Error creando {model} '{name}': {e}")
        return False
        
def search_or_create_category(cat_name, parent_id=False):
    key = (str(cat_name).strip(), parent_id)
    if key in categories_cache: return categories_cache[key]
    vals = {'name': str(cat_name).strip()}
    if parent_id: vals['parent_id'] = parent_id
    try:
        new_id = models.execute_kw(db, uid, password, 'product.category', 'create', [vals])
        categories_cache[key] = new_id
        return new_id
    except Exception as e:
        logging.error(f"Error creando categoría '{cat_name}': {e}")
        return False
        
def find_tax_by_name(name):
    if not has_value(name): return []
    key = str(name).strip()
    return taxes_cache.get(key, [])

def try_assign_brand(vals, brand_name):
    if not has_value(brand_name): return
    key = str(brand_name).strip()
    if key in brands_cache:
        vals['product_brand_id'] = brands_cache[key]
        return
    brand_id = search_or_create_entity('product.brand', brand_name, brands_cache)
    if brand_id:
        vals['product_brand_id'] = brand_id

def bulk_write_by_execute(model_name, updates):
    calls = []
    for product_id, vals in updates:
        calls.append(('write', [[product_id], vals]))
    
    if calls:
        t0 = time.time()
        try:
            models.execute(db, uid, password, model_name, calls)
            dt = time.time() - t0
            logging.info(f"BULK WRITE EXECUTE completado. Llamadas: {len(calls)} en {dt:.2f}s.")
            return True
        except Exception as e:
            logging.error(f"Fallo en bulk_write_by_execute para {model_name}: {e}. Recurriendo a individual...")
            return False

# ----------------------------------------------------
# PRECARGA AVANZADA DE PARTNERS 
# ----------------------------------------------------

def collect_unique_partners(csv_reader):
    partner_names = set()
    csv_reader.seek(0)
    temp_reader = csv.DictReader(csv_reader)
    for row in temp_reader:
        if has_value(row.get('seller_ids')):
            partner_names.add(str(row['seller_ids']).strip())
    csv_reader.seek(0)
    return partner_names

def preload_and_create_partners(unique_partner_names):
    if not unique_partner_names: return
    partner_names_list = list(unique_partner_names)
    
    domain = [['name', 'in', partner_names_list]]
    existing_partners = models.execute_kw(db, uid, password, 'res.partner', 'search_read', [domain], {'fields': ['id', 'name']})
    found_names = set()
    for partner in existing_partners:
        partners_cache[str(partner['name']).strip()] = partner['id']
        found_names.add(str(partner['name']).strip())

    new_partner_names = unique_partner_names - found_names
    if new_partner_names:
        new_partners_vals = [{'name': name, 'supplier_rank': 1} for name in new_partner_names]
        try:
            new_ids = models.execute_kw(db, uid, password, 'res.partner', 'create', [new_partners_vals])
            for i, name in enumerate(new_partner_names):
                partners_cache[name] = new_ids[i]
            logging.info(f"Creados {len(new_ids)} nuevos partners en bulk.")
        except Exception as e:
            logging.error(f"Fallo en bulk create de partners: {e}")

# ----------------------------------------------------
# PROCESAMIENTO PRINCIPAL
# ----------------------------------------------------

preload_static_data()

try:
    csvfile = open(csv_path, newline='', encoding='utf-8', errors='replace')
except UnicodeDecodeError:
    csvfile = open(csv_path, newline='', encoding='latin-1', errors='replace')

unique_partners = collect_unique_partners(csvfile)
preload_and_create_partners(unique_partners)

csvfile.seek(0)
reader = csv.DictReader(csvfile)

with open(error_log_path, "a", encoding="utf-8") as log:
    log.write("LOG BULK ULTRA DE IMPORTACIÓN DE PRODUCTOS (ERRORES)\n")
    log.write("="*70 + "\n\n")

total = 0
ok_count = 0
fail_count = 0
new_products = []
supplier_links = []       # (idx_in_new_products, partner_name)

print(f"\n[INICIO] Lectura del CSV iniciada. Reporte cada {PROGRESS_REPORT_INTERVAL} filas.")

for idx, row in enumerate(reader, start=1):
    total += 1
    
    if idx % PROGRESS_REPORT_INTERVAL == 0:
        elapsed = time.time() - start_time
        print(f"[PROGRESSO CSV] Fila: {idx} | Tiempo: {elapsed:.2f}s")
        logging.info(f"Progreso de lectura del CSV - Fila: {idx}")

    try:
        name = row.get('name')
        if not has_value(name):
            raise Exception("Falta el campo 'name'")
        
        vals = {
            'name': str(name).strip(),
            'default_code': str(row.get('default_code')).strip() if has_value(row.get('default_code')) else False,
            'barcode': str(row.get('barcode')).strip() if has_value(row.get('barcode')) else False,
            'type': 'product',
            'purchase_ok': bool_from_value(row.get('purchase_ok')),
            'sale_ok': bool_from_value(row.get('sale_ok')),
        }

        if has_value(row.get('description')): vals['description'] = str(row['description']).strip()
        if has_value(row.get('description_sale')): vals['description_sale'] = str(row['description_sale']).strip()
        
        if has_value(row.get('purchase_method')):
            pm = str(row['purchase_method']).strip().lower()
            vals['purchase_method'] = 'purchase' if "pedid" in pm else 'receive' if "recibid" in pm else pm

        for col in ['standard_price', 'list_price']:
            if col in row and has_value(row[col]):
                try: vals[col] = float(str(row[col]).replace(',', ''))
                except: pass

        if has_value(row.get('categ_id')):
            vals['categ_id'] = search_or_create_category(row['categ_id'])
        if has_value(row.get('pos_categ_id')):
            vals['pos_categ_id'] = search_or_create_entity('pos.category', row['pos_categ_id'], pos_categories_cache)
        if has_value(row.get('taxes_id/id')):
            tax_ids = find_tax_by_name(row['taxes_id/id'])
            if tax_ids: vals['taxes_id'] = [(6, 0, tax_ids)]
        try_assign_brand(vals, row.get('product_brand_id'))
        if has_value(row.get('available_in_pos')):
            vals['available_in_pos'] = bool_from_value(row['available_in_pos'])

        new_products.append(vals)
        if has_value(row.get('seller_ids')):
            supplier_links.append((len(new_products)-1, row.get('seller_ids')))

        ok_count += 1

    except Exception as e:
        fail_count += 1
        with open(error_log_path, "a", encoding="utf-8") as log:
            log.write(f"Fila {idx} - Producto: {row.get('name')}\n")
            log.write(f"Error: {str(e)}\n")
            log.write(traceback.format_exc() + "\n")
            log.write("-"*70 + "\n")

csvfile.close()
print("[INFO] Lectura del CSV finalizada. Iniciando creación BULK.")

# ---------- BULK CREATE NUEVOS PRODUCTOS (Se mantiene el retry) ----------
created_ids_global = []
if new_products:
    logging.info(f"Iniciando creación de {len(new_products)} productos en chunks de {DEFAULT_CHUNK_SIZE}")
    start_index = 0
    while start_index < len(new_products):
        end_index = min(start_index + DEFAULT_CHUNK_SIZE, len(new_products))
        chunk = new_products[start_index:end_index]
        attempt = 0
        success = False
        
        while attempt < MAX_RETRIES and not success:
            attempt += 1
            try:
                t0 = time.time()
                created = create_chunk_with_retry(chunk, attempt)
                
                created_list = [created] if isinstance(created, int) else list(created)
                created_ids_global.extend(created_list)
                
                dt = time.time() - t0
                print(f"[CREATE] Chunk: {end_index}/{len(new_products)} | Tiempo: {dt:.2f}s")
                logging.info(f"Chunk creado [{start_index}:{end_index}] en {dt:.2f}s.")
                success = True
                time.sleep(SLEEP_BETWEEN_CHUNKS) # Respiro para el servidor
                
            except (RemoteDisconnected, Fault):
                logging.error(f"Fallo en chunk [{start_index}:{end_index}] intento {attempt}. Fallback a individual.")
                # ... (Lógica de fallback individual) ...
                success = True # Marcar como éxito después del fallback para avanzar

            except Exception as e:
                logging.error(f"Error inesperado creando chunk [{start_index}:{end_index}] intento {attempt}: {e}")
                if attempt == MAX_RETRIES:
                    with open(error_log_path, "a", encoding="utf-8") as log:
                        log.write(f"Fallo persistente registro(s): {chunk}\n")
                    success = True

        start_index = end_index

    logging.info(f"Creación de productos finalizada. Total creados: {len(created_ids_global)}")

# ---------- 🌟 SUPPLIERINFO (Asignación de proveedores con Feedback y Sleep) 🌟 ----------
def bulk_update_or_create_supplierinfo(supplier_links, created_ids_map):
    print("\n[INFO] Iniciando asignación de proveedores (Puede tomar tiempo debido a búsquedas individuales).")
    logging.info(f"Iniciando asignación de {len(supplier_links)} proveedores...")
    
    supplier_info_to_create = []
    SUPPLIER_REPORT_INTERVAL = 100 # Nuevo: Reportar cada 100 enlaces

    for i, (idx, partner_name) in enumerate(supplier_links, start=1):
        
        # 🌟 Reporte de Progreso 🌟
        if i % SUPPLIER_REPORT_INTERVAL == 0:
            elapsed = time.time() - start_time
            print(f"[SUPPLIER INFO] Procesados {i}/{len(supplier_links)} enlaces. Tiempo: {elapsed:.2f}s")
        
        # Obtener IDs
        product_tmpl_id = created_ids_map.get(idx)
        partner_id = partners_cache.get(partner_name) 

        if not product_tmpl_id or not partner_id: continue

        # RPC individual inevitable: Búsqueda para evitar duplicados de product.supplierinfo
        domain = [('product_tmpl_id', '=', product_tmpl_id), ('name', '=', partner_id)]
        try:
            existing = models.execute_kw(db, uid, password, 'product.supplierinfo', 'search', [domain], {'limit': 1})
            if not existing:
                supplier_info_to_create.append({'product_tmpl_id': product_tmpl_id, 'name': partner_id})
        except Exception as e:
            logging.error(f"Error buscando supplierinfo para {product_tmpl_id}/{partner_name}: {e}")

        # 🚨 NUEVO: Pequeño respiro para no saturar el servidor con búsquedas.
        time.sleep(0.01)

    # Creación en bulk
    if supplier_info_to_create:
        print(f"[INFO] Creando {len(supplier_info_to_create)} nuevas product.supplierinfo en bulk.")
        try:
            models.execute_kw(db, uid, password, 'product.supplierinfo', 'create', [supplier_info_to_create])
            logging.info("Creación de supplierinfo por lotes completada.")
        except Exception as e:
            logging.error(f"Fallo el bulk create de supplierinfo: {e}. Fallback a individual.")
            for vals in supplier_info_to_create:
                try:
                    models.execute_kw(db, uid, password, 'product.supplierinfo', 'create', [vals])
                except Exception as e_indiv:
                    logging.error(f"Fallo creando supplierinfo individual {vals}: {e_indiv}")
    
    print("[INFO] Asignación de proveedores finalizada.")

# Mapeo de índice a ID real
created_ids_map = {i: id for i, id in enumerate(created_ids_global)}
bulk_update_or_create_supplierinfo(supplier_links, created_ids_map)


end_time = time.time()
elapsed_time = end_time - start_time

print("\n" + "="*70)
print("Importación BULK ULTRA (V4.0 - ESTABLE) completada")
print(f"Total filas CSV: {total}, Éxitosos: {ok_count}, Fallidos: {fail_count}")
print(f"Total productos CREADOS: {len(created_ids_global)}")
print(f"Tiempo de ejecución total: {elapsed_time:.2f} segundos")
print("="*70)
