"""
Script BULK Optimizado Final con:
- Barra de progreso
- Estimación de tiempo
- Impuestos cliente/proveedor corregido
- purchase_method
- Marca
- Categoría POS
- Proveedores
- Creación/actualización en lotes
- available_in_pos
- description
"""

import xmlrpc.client
import csv
import time
import logging
import sys

# ---------- CONFIG ----------
url = "http://localhost:8073"
db = "test"
username = "admin"
password = "admin"

csv_path = "articulos.csv"
log_path = "import_log_articulos.txt"

logging.basicConfig(filename=log_path, level=logging.INFO, format='%(asctime)s - %(message)s')

# ---------- CONEXIÓN ----------
common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
uid = common.authenticate(db, username, password, {})
models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")

start_time = time.time()


# ---------- UTILIDADES ----------
def has_value(val):
    return val is not None and str(val).strip() != ''


def print_progress(current, total, start_time, prefix=''):
    percent = current / total * 100
    bar_len = 40
    filled_len = int(bar_len * current // total)
    bar = '=' * filled_len + '-' * (bar_len - filled_len)
    elapsed = time.time() - start_time
    remaining = (elapsed / current * (total - current)) if current else 0
    sys.stdout.write(f"\r{prefix} |{bar}| {percent:5.1f}% Completado, ETA: {remaining:.1f}s")
    sys.stdout.flush()
    if current == total:
        print('')


# ---------- PRECARGA ----------
print("Precargando datos de Odoo...")

# Productos
all_products = models.execute_kw(
    db, uid, password,
    'product.template', 'search_read',
    [[]], {'fields': ['id', 'default_code', 'barcode']}
)
products_by_code = {p['default_code']: p['id'] for p in all_products if p.get('default_code')}
products_by_barcode = {p['barcode']: p['id'] for p in all_products if p.get('barcode')}

# Impuestos
all_taxes = models.execute_kw(
    db, uid, password,
    'account.tax', 'search_read',
    [[]], {'fields': ['id', 'name']}
)
# guardar como {name_stripped: id}
taxes_cache = {t['name'].strip(): t['id'] for t in all_taxes if t.get('name')}


# ---------- CACHE ----------
taxes_cache = {}

def find_tax_by_name(name):
    """Busca impuestos por nombre exacto (ejemplo: IVA 21%)"""
    if not has_value(name):
        return []
    key = str(name).strip()
    if key in taxes_cache:
        return taxes_cache[key]
    try:
        ids = models.execute_kw(
            db, uid, password,
            'account.tax', 'search',
            [[['name', '=', key]]]
        )
        taxes_cache[key] = ids
        return ids
    except Exception as e:
        logging.error(f"Error buscando impuesto '{name}': {e}")
        return []



# Categorías
all_categs = models.execute_kw(
    db, uid, password,
    'product.category', 'search_read',
    [[]], {'fields': ['id', 'name']}
)
categs_cache = {c['name'].strip().lower(): c['id'] for c in all_categs if c.get('name')}


def get_categ_id(name):
    if not has_value(name):
        return False
    return categs_cache.get(name.strip().lower(), False)


# Categorías POS
all_pos_categs = models.execute_kw(
    db, uid, password,
    'pos.category', 'search_read',
    [[]], {'fields': ['id', 'name']}
)
pos_categ_cache = {c['name'].strip().lower(): c['id'] for c in all_pos_categs if c.get('name')}


def get_pos_categ_id(name):
    if not has_value(name):
        return False
    return pos_categ_cache.get(name.strip().lower(), False)


# Marcas
brands_cache = {}


def try_assign_brand(vals, brand_name):
    if not has_value(brand_name):
        return
    key = brand_name.strip().lower()
    if key in brands_cache:
        vals['product_brand_id'] = brands_cache[key]
        return
    brand_ids = models.execute_kw(db, uid, password, 'product.brand', 'search', [[['name', '=', brand_name]]])
    if brand_ids:
        brands_cache[key] = brand_ids[0]
        vals['product_brand_id'] = brand_ids[0]
    else:
        new_brand_id = models.execute_kw(db, uid, password, 'product.brand', 'create', [{'name': brand_name}])
        brands_cache[key] = new_brand_id
        vals['product_brand_id'] = new_brand_id


# Partners cache para proveedores
partners_cache = {}


def search_or_create_partner(name):
    key = name.strip().lower()
    if key in partners_cache:
        return partners_cache[key]
    ids = models.execute_kw(db, uid, password, 'res.partner', 'search', [[['name', '=', name]]], {'limit': 1})
    if ids:
        partners_cache[key] = ids[0]
        return ids[0]
    new_id = models.execute_kw(db, uid, password, 'res.partner', 'create', [{'name': name, 'supplier_rank': 1}])
    partners_cache[key] = new_id
    return new_id


def create_or_update_supplierinfo(product_tmpl_id, partner_id):
    domain = [('product_tmpl_id', '=', product_tmpl_id), ('name', '=', partner_id)]
    existing = models.execute_kw(db, uid, password, 'product.supplierinfo', 'search', [domain], {'limit': 1})
    if existing:
        return existing[0]
    return models.execute_kw(
        db, uid, password,
        'product.supplierinfo', 'create',
        [{'product_tmpl_id': product_tmpl_id, 'name': partner_id}]
    )


# ---------- LEER CSV ----------
new_products = []
updates = []
csv_rows = []

seen_barcodes = set()   # Para detectar duplicados

with open(csv_path, newline='', encoding='utf-8') as csvfile:
    reader = list(csv.DictReader(csvfile))
    total_rows = len(reader)
    csv_start_time = time.time()
    csv_rows = reader

    for idx, row in enumerate(reader, start=1):
        default_code = row.get('default_code')
        barcode = row.get('barcode')

        # ---- Validar duplicados de código de barra ----
        if has_value(barcode):
            if barcode in seen_barcodes:
                # Si ya existe en este CSV, lo dejamos en blanco
                logging.info(f"Fila {idx}: código de barra duplicado '{barcode}', se deja en blanco")
                barcode = ''
                row['barcode'] = ''  # también se pisa en la fila
            else:
                seen_barcodes.add(barcode)

        # Buscar si ya existe en Odoo
        product_tmpl_id = None
        if has_value(default_code) and default_code in products_by_code:
            product_tmpl_id = products_by_code[default_code]
        elif has_value(barcode) and barcode in products_by_barcode:
            product_tmpl_id = products_by_barcode[barcode]

        vals = {
            'name': row.get('name') or 'SIN NOMBRE',
            'default_code': default_code or False,
            'barcode': barcode or False,   # ya limpio si estaba duplicado
            'type': row.get('type') or 'product',
            'list_price': float(row['list_price']) if has_value(row.get('list_price')) else 0.0,
            'standard_price': float(row['standard_price']) if has_value(row.get('standard_price')) else 0.0,
            'purchase_ok': True,
            'sale_ok': True,
            'available_in_pos': True if str(row.get('available_in_pos')).strip().upper() == 'VERDADERO' else False,
            'description': row.get('description') or '',
        }


        # purchase_method
        if has_value(row.get('purchase_method')):
            val = str(row['purchase_method']).strip().lower()
            if val in ['purchase', 'receive']:
                vals['purchase_method'] = val

        # Categoría
        if has_value(row.get('categ_id')):
            cat_id = get_categ_id(row['categ_id'])
            if cat_id:
                vals['categ_id'] = cat_id

        # Categoría POS
        if has_value(row.get('pos_categ_id')):
            pos_id = get_pos_categ_id(row['pos_categ_id'])
            if pos_id:
                vals['pos_categ_id'] = pos_id

        # Marca
        try_assign_brand(vals, row.get('product_brand_id'))

        # ---------- IMPUESTOS ----------
        if has_value(row.get('taxes_id/id')):
            tax_ids = find_tax_by_name(row['taxes_id/id'])
            if tax_ids:
                vals['taxes_id'] = [(6, 0, tax_ids)]             # Cliente (ventas)
                vals['supplier_taxes_id'] = [(6, 0, tax_ids)]    # Proveedor (compras)
            else:
                logging.info(f"Fila {idx}: impuesto '{row.get('taxes_id/id')}' NO encontrado en Odoo")


        if product_tmpl_id:
            updates.append((product_tmpl_id, vals))
        else:
            new_products.append(vals)

        # Barra de progreso CSV
        if idx % max(1, total_rows // 50) == 0 or idx == total_rows:
            print_progress(idx, total_rows, csv_start_time, prefix="Procesando CSV")


# ---------- CREACIÓN ----------
print(f"\nCreando {len(new_products)} productos nuevos...")
create_start_time = time.time()
created_ids = []
for i in range(0, len(new_products), 50):
    batch = new_products[i:i+50]
    batch_ids = models.execute_kw(db, uid, password, 'product.template', 'create', [batch])
    if isinstance(batch_ids, int):
        batch_ids = [batch_ids]
    created_ids.extend(batch_ids)
    print_progress(min(i+50, len(new_products)), len(new_products), create_start_time, prefix="Creación productos")


# ---------- ACTUALIZACIÓN ----------
print(f"\nActualizando {len(updates)} productos existentes...")
update_start_time = time.time()
for i in range(0, len(updates), 50):
    batch = updates[i:i+50]
    for pid, vals in batch:
        models.execute_kw(db, uid, password, 'product.template', 'write', [[pid], vals])
    print_progress(min(i+50, len(updates)), len(updates), update_start_time, prefix="Actualización productos")


# ---------- ASIGNAR PROVEEDORES OPTIMIZADO EN LOTES ----------
print("\nAsignando proveedores a los productos (optimizado)...")

# 1️⃣ Precargar todos los nombres de proveedores únicos del CSV
all_seller_names = {row['seller_ids'].strip() for row in csv_rows if has_value(row.get('seller_ids'))}
seller_names = [name for name in all_seller_names if has_value(name)]
print(f"Se detectaron {len(seller_names)} proveedores en el CSV...")

# 2️⃣ Buscar en Odoo todos los partners existentes
existing_partners = models.execute_kw(
    db, uid, password,
    'res.partner', 'search_read',
    [[['name', 'in', seller_names]]],
    {'fields': ['id', 'name']}
)
for partner in existing_partners:
    partners_cache[partner['name'].strip().lower()] = partner['id']

# 3️⃣ Crear en lote los partners que faltan
to_create = [name for name in seller_names if name.strip().lower() not in partners_cache]
if to_create:
    batch_size = 100
    for i in range(0, len(to_create), batch_size):
        batch = [{'name': n, 'supplier_rank': 1} for n in to_create[i:i+batch_size]]
        new_ids = models.execute_kw(db, uid, password, 'res.partner', 'create', [batch])
        if isinstance(new_ids, int):
            new_ids = [new_ids]
        for name, pid in zip(to_create[i:i+batch_size], new_ids):
            partners_cache[name.strip().lower()] = pid
    print(f"Se crearon {len(to_create)} proveedores nuevos en Odoo.")

# 4️⃣ Construir la lista completa de supplierinfo a crear
supplierinfo_to_create = []

for idx, row in enumerate(csv_rows, start=1):
    seller_name = row.get('seller_ids')
    if not has_value(seller_name):
        continue

    # Determinar product_tmpl_id
    if idx <= len(created_ids):
        product_tmpl_id = created_ids[idx - 1]  # producto nuevo
    else:
        default_code = row.get('default_code')
        barcode = row.get('barcode')
        product_tmpl_id = None
        if has_value(default_code) and default_code in products_by_code:
            product_tmpl_id = products_by_code[default_code]
        elif has_value(barcode) and barcode in products_by_barcode:
            product_tmpl_id = products_by_barcode[barcode]

    if not product_tmpl_id:
        continue

    partner_id = partners_cache.get(seller_name.strip().lower())
    if partner_id:
        supplierinfo_to_create.append({
            'product_tmpl_id': product_tmpl_id,
            'name': partner_id
        })

print(f"Se van a crear {len(supplierinfo_to_create)} relaciones producto-proveedor...")

# 5️⃣ Crear supplierinfo en lotes de 100
batch_size = 100
for i in range(0, len(supplierinfo_to_create), batch_size):
    batch = supplierinfo_to_create[i:i+batch_size]
    models.execute_kw(db, uid, password, 'product.supplierinfo', 'create', [batch])
    print_progress(i+len(batch), len(supplierinfo_to_create), start_time, prefix="Proveedores")

# ---------- FIN ----------
elapsed = time.time() - start_time
print(f"\nImportación finalizada en {elapsed:.2f} segundos")
logging.info(f"Importación finalizada en {elapsed:.2f} segundos")
