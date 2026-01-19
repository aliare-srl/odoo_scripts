"""
Script BULK Optimizado - INSERCIÓN Y ACTUALIZACIÓN DE PRECIOS
- Inserta productos que NO existen (por código de barras)
- NUEVA: Opción de actualizar precios de productos existentes
- Barra de progreso y estimación de tiempo
- Impuestos cliente/proveedor
- purchase_method
- Marca
- Categoría POS
- Proveedores
- available_in_pos
- description
"""

import xmlrpc.client
import csv
import time
import logging
import sys
import re

# ---------- CONFIG ----------
url = "http://localhost:8069"
db = "test"
username = "admin"
password = "admin"

csv_path = "articulos.csv"
log_path = "import_log_articulos.txt"

# ✨ NUEVA CONFIGURACIÓN - ACTUALIZACIÓN DE PRECIOS
UPDATE_PRICES = True  # True = actualizar precios de productos existentes | False = solo insertar nuevos
UPDATE_COST = True    # True = actualizar costo (standard_price) | False = no actualizar costo
UPDATE_SALE_PRICE = True  # True = actualizar precio de venta (list_price) | False = no actualizar precio venta

logging.basicConfig(filename=log_path, level=logging.INFO, format='%(asctime)s - %(message)s')

# ---------- CONEXIÓN ----------
common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
uid = common.authenticate(db, username, password, {})
models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")

start_time = time.time()


# ---------- UTILIDADES ----------
def has_value(val):
    return val is not None and str(val).strip() != ''


def sanitize_xml(value):
    """Elimina caracteres de control que rompen XML-RPC"""
    if not value:
        return value
    value = str(value)
    # Elimina caracteres de control (0x00-0x1F excepto tab, newline, carriage return)
    value = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F]', '', value)
    return value


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

# ✅ Productos existentes - SOLO POR CÓDIGO DE BARRAS
print("Cargando productos existentes por código de barras...")
all_products = models.execute_kw(
    db, uid, password,
    'product.template', 'search_read',
    [[['barcode', '!=', False]]], 
    {'fields': ['id', 'barcode', 'name', 'list_price', 'standard_price']}
)
products_by_barcode = {p['barcode']: p for p in all_products if p.get('barcode')}
print(f"✓ Cargados {len(products_by_barcode)} productos con código de barras")

# Impuestos
print("Cargando impuestos...")
all_taxes = models.execute_kw(
    db, uid, password,
    'account.tax', 'search_read',
    [[]], {'fields': ['id', 'name', 'type_tax_use']}
)

# Separar por tipo
sale_taxes_cache = {}      # Para clientes (ventas)
purchase_taxes_cache = {}  # Para proveedores (compras)

for t in all_taxes:
    if not t.get('name'):
        continue
    name = t['name'].strip()
    tax_type = t.get('type_tax_use', 'none')
    
    # Impuestos de venta (cliente)
    if tax_type in ['sale', 'none']:
        sale_taxes_cache[name] = t['id']
    
    # Impuestos de compra (proveedor)
    if tax_type in ['purchase', 'none']:
        purchase_taxes_cache[name] = t['id']

print(f"✓ Cargados {len(sale_taxes_cache)} impuestos de VENTA (cliente)")
print(f"✓ Cargados {len(purchase_taxes_cache)} impuestos de COMPRA (proveedor)")


def find_sale_tax_by_name(name):
    """Busca impuestos de VENTA (cliente) por nombre exacto"""
    if not has_value(name):
        return []
    key = str(name).strip()
    
    # Verificar cache
    if key in sale_taxes_cache:
        return [sale_taxes_cache[key]]
    
    try:
        # Buscar impuestos de venta o sin tipo específico
        ids = models.execute_kw(
            db, uid, password,
            'account.tax', 'search',
            [[['name', '=', key], ['type_tax_use', 'in', ['sale', 'none']]]]
        )
        if ids:
            sale_taxes_cache[key] = ids[0]
            logging.info(f"✓ Impuesto de VENTA encontrado: '{key}' -> ID {ids[0]}")
            return ids
        
        logging.warning(f"⚠️  Impuesto de VENTA '{key}' NO encontrado")
        return []
    except Exception as e:
        logging.error(f"Error buscando impuesto de venta '{name}': {e}")
        return []


def find_purchase_tax_by_name(name):
    """Busca impuestos de COMPRA (proveedor) por nombre exacto"""
    if not has_value(name):
        return []
    key = str(name).strip()
    
    # Verificar cache
    if key in purchase_taxes_cache:
        return [purchase_taxes_cache[key]]
    
    try:
        # Buscar impuestos de compra o sin tipo específico
        ids = models.execute_kw(
            db, uid, password,
            'account.tax', 'search',
            [[['name', '=', key], ['type_tax_use', 'in', ['purchase', 'none']]]]
        )
        if ids:
            purchase_taxes_cache[key] = ids[0]
            logging.info(f"✓ Impuesto de COMPRA encontrado: '{key}' -> ID {ids[0]}")
            return ids
        
        logging.warning(f"⚠️  Impuesto de COMPRA '{key}' NO encontrado")
        return []
    except Exception as e:
        logging.error(f"Error buscando impuesto de compra '{name}': {e}")
        return []


# Categorías
print("Cargando categorías...")
all_categs = models.execute_kw(
    db, uid, password,
    'product.category', 'search_read',
    [[]], {'fields': ['id', 'name']}
)
categs_cache = {c['name'].strip().lower(): c['id'] for c in all_categs if c.get('name')}
print(f"✓ Cargadas {len(categs_cache)} categorías")


def get_categ_id(name):
    if not has_value(name):
        return False
    return categs_cache.get(name.strip().lower(), False)


# Categorías POS
print("Cargando categorías POS...")
all_pos_categs = models.execute_kw(
    db, uid, password,
    'pos.category', 'search_read',
    [[]], {'fields': ['id', 'name']}
)
pos_categ_cache = {c['name'].strip().lower(): c['id'] for c in all_pos_categs if c.get('name')}
print(f"✓ Cargadas {len(pos_categ_cache)} categorías POS")


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


# ---------- LEER CSV ----------
new_products = []
update_products = []  # ✨ NUEVA: Lista de productos a actualizar
skipped_products = []
csv_rows = []
seen_barcodes = set()

print("\nProcesando archivo CSV...")
print(f"Configuración: UPDATE_PRICES={UPDATE_PRICES}, UPDATE_COST={UPDATE_COST}, UPDATE_SALE_PRICE={UPDATE_SALE_PRICE}")
print("-" * 60)

with open(csv_path, newline='', encoding='utf-8') as csvfile:
    reader = list(csv.DictReader(csvfile))
    total_rows = len(reader)
    csv_start_time = time.time()
    csv_rows = reader

    for idx, row in enumerate(reader, start=1):
        barcode = sanitize_xml(row.get('barcode', '').strip())

        # ✅ VALIDACIÓN 1: Sin código de barras = OMITIR
        if not has_value(barcode):
            skipped_products.append({
                'fila': idx,
                'nombre': row.get('name', 'SIN NOMBRE'),
                'razon': 'Sin código de barras'
            })
            logging.info(f"Fila {idx}: OMITIDO - Sin código de barras")
            continue

        # ✅ VALIDACIÓN 2: Código de barras duplicado en el CSV
        if barcode in seen_barcodes:
            skipped_products.append({
                'fila': idx,
                'nombre': row.get('name', 'SIN NOMBRE'),
                'razon': f'Código de barras duplicado en CSV: {barcode}'
            })
            logging.info(f"Fila {idx}: OMITIDO - Código de barras duplicado en CSV: {barcode}")
            continue

        # ✅ Marcar como visto
        seen_barcodes.add(barcode)

        # ✨ NUEVA LÓGICA: Verificar si existe para actualizar o crear
        existing_product = products_by_barcode.get(barcode)
        
        if existing_product and UPDATE_PRICES:
            # ✨ ACTUALIZACIÓN DE PRECIOS
            update_vals = {
                'id': existing_product['id'],
                'barcode': barcode,
                'name': existing_product['name'],
            }
            
            # Actualizar costo si está habilitado
            if UPDATE_COST and has_value(row.get('standard_price')):
                new_cost = float(row['standard_price'])
                old_cost = existing_product.get('standard_price', 0.0)
                if new_cost != old_cost:
                    update_vals['standard_price'] = new_cost
                    update_vals['cost_changed'] = True
                    update_vals['old_cost'] = old_cost
            
            # Actualizar precio de venta si está habilitado
            if UPDATE_SALE_PRICE and has_value(row.get('list_price')):
                new_price = float(row['list_price'])
                old_price = existing_product.get('list_price', 0.0)
                if new_price != old_price:
                    update_vals['list_price'] = new_price
                    update_vals['price_changed'] = True
                    update_vals['old_price'] = old_price
            
            # Solo agregar si hay algo que actualizar
            if 'standard_price' in update_vals or 'list_price' in update_vals:
                update_products.append(update_vals)
                logging.info(f"Fila {idx}: ACTUALIZAR precios - {existing_product['name']}")
            else:
                skipped_products.append({
                    'fila': idx,
                    'nombre': row.get('name', 'SIN NOMBRE'),
                    'razon': 'Ya existe y precios son iguales',
                    'producto_odoo': existing_product['name']
                })
            continue
        
        elif existing_product and not UPDATE_PRICES:
            # Ya existe pero NO se actualizan precios
            skipped_products.append({
                'fila': idx,
                'nombre': row.get('name', 'SIN NOMBRE'),
                'razon': f'Ya existe en Odoo (UPDATE_PRICES=False)',
                'producto_odoo': existing_product['name']
            })
            logging.info(f"Fila {idx}: OMITIDO - Producto ya existe (sin actualización): {existing_product['name']}")
            continue

        # ✅ PRODUCTO NUEVO - Construir valores
        vals = {
            'name': sanitize_xml(row.get('name') or 'SIN NOMBRE'),
            'default_code': sanitize_xml(row.get('default_code')) or False,
            'barcode': barcode,
            'type': row.get('type') or 'product',
            'list_price': float(row['list_price']) if has_value(row.get('list_price')) else 0.0,
            'standard_price': float(row['standard_price']) if has_value(row.get('standard_price')) else 0.0,
            'purchase_ok': True,
            'sale_ok': True,
            'available_in_pos': True if str(row.get('available_in_pos')).strip().upper() == 'VERDADERO' else False,
            'description': sanitize_xml(row.get('description')) or '',
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
            tax_name = row['taxes_id/id'].strip()
            
            # Buscar impuesto de VENTA (cliente)
            sale_tax_ids = find_sale_tax_by_name(tax_name)
            if sale_tax_ids:
                vals['taxes_id'] = [(6, 0, sale_tax_ids)]
                logging.info(f"Fila {idx}: Impuesto de VENTA '{tax_name}' asignado (ID: {sale_tax_ids[0]})")
            else:
                logging.warning(f"Fila {idx}: Impuesto de VENTA '{tax_name}' NO encontrado")
            
            # Buscar impuesto de COMPRA (proveedor)
            purchase_tax_ids = find_purchase_tax_by_name(tax_name)
            if purchase_tax_ids:
                vals['supplier_taxes_id'] = [(6, 0, purchase_tax_ids)]
                logging.info(f"Fila {idx}: Impuesto de COMPRA '{tax_name}' asignado (ID: {purchase_tax_ids[0]})")
            else:
                logging.warning(f"Fila {idx}: Impuesto de COMPRA '{tax_name}' NO encontrado")

        new_products.append(vals)

        # Barra de progreso CSV
        if idx % max(1, total_rows // 50) == 0 or idx == total_rows:
            print_progress(idx, total_rows, csv_start_time, prefix="Procesando CSV")


# ---------- RESUMEN ----------
print(f"\n{'='*60}")
print(f"RESUMEN DE PROCESAMIENTO:")
print(f"{'='*60}")
print(f"Total de filas en CSV:           {total_rows}")
print(f"Productos NUEVOS a crear:        {len(new_products)}")
print(f"Productos a ACTUALIZAR:          {len(update_products)}")  # ✨ NUEVO
print(f"Productos OMITIDOS:              {len(skipped_products)}")

# Estadísticas de actualización
if update_products:
    cost_updates = sum(1 for p in update_products if 'cost_changed' in p)
    price_updates = sum(1 for p in update_products if 'price_changed' in p)
    print(f"  → Actualizaciones de costo:    {cost_updates}")
    print(f"  → Actualizaciones de precio:   {price_updates}")

# Estadísticas de impuestos
products_with_tax = sum(1 for p in new_products if 'taxes_id' in p)
products_without_tax = len(new_products) - products_with_tax
print(f"  → Con impuestos asignados:     {products_with_tax}")
print(f"  → Sin impuestos:               {products_without_tax}")
print(f"{'='*60}")

# Detalles de productos omitidos
if skipped_products:
    print(f"\n📋 DETALLES DE PRODUCTOS OMITIDOS:")
    print(f"{'-'*60}")
    for item in skipped_products[:20]:  # Mostrar solo los primeros 20
        print(f"Fila {item['fila']:4d}: {item['nombre'][:35]:35s} - {item['razon']}")
        if 'producto_odoo' in item:
            print(f"           → Ya existe en Odoo como: {item['producto_odoo']}")
    
    if len(skipped_products) > 20:
        print(f"\n... y {len(skipped_products) - 20} productos más omitidos (ver log completo)")
    print(f"{'-'*60}")

# ✨ NUEVA: Detalles de actualizaciones
if update_products and len(update_products) <= 50:
    print(f"\n💰 DETALLES DE ACTUALIZACIONES DE PRECIOS:")
    print(f"{'-'*60}")
    for item in update_products[:20]:
        changes = []
        if 'cost_changed' in item:
            changes.append(f"Costo: ${item['old_cost']:.2f} → ${item['standard_price']:.2f}")
        if 'price_changed' in item:
            changes.append(f"Venta: ${item['old_price']:.2f} → ${item['list_price']:.2f}")
        print(f"{item['name'][:40]:40s} - {' | '.join(changes)}")
    
    if len(update_products) > 20:
        print(f"\n... y {len(update_products) - 20} actualizaciones más")
    print(f"{'-'*60}")

# Confirmar antes de continuar
total_operations = len(new_products) + len(update_products)
if total_operations > 0:
    print(f"\n⚠️  OPERACIONES A REALIZAR:")
    if new_products:
        print(f"   → Crear {len(new_products)} productos nuevos")
    if update_products:
        print(f"   → Actualizar precios de {len(update_products)} productos existentes")
    
    response = input("\n¿Desea continuar? (s/n): ")
    if response.lower() != 's':
        print("❌ Operación cancelada por el usuario")
        sys.exit(0)
else:
    print("\n✓ No hay operaciones pendientes.")
    sys.exit(0)


# ---------- ACTUALIZACIÓN DE PRECIOS ----------
updated_count = 0
update_errors = []

if update_products:
    print(f"\n{'='*60}")
    print(f"ACTUALIZANDO PRECIOS DE {len(update_products)} PRODUCTOS...")
    print(f"{'='*60}")
    update_start_time = time.time()
    
    for i in range(0, len(update_products), 50):
        batch = update_products[i:i+50]
        try:
            for product in batch:
                update_vals = {}
                if 'standard_price' in product:
                    update_vals['standard_price'] = product['standard_price']
                if 'list_price' in product:
                    update_vals['list_price'] = product['list_price']
                
                if update_vals:
                    models.execute_kw(
                        db, uid, password,
                        'product.template', 'write',
                        [[product['id']], update_vals]
                    )
                    updated_count += 1
            
            print_progress(min(i+50, len(update_products)), len(update_products), 
                         update_start_time, prefix="Actualizando precios")
        except Exception as e:
            error_msg = f"Error actualizando lote {i}-{i+50}: {str(e)}"
            update_errors.append(error_msg)
            logging.error(error_msg)
            print(f"\n❌ {error_msg}")
    
    print(f"\n✓ Actualizados {updated_count} productos exitosamente")


# ---------- CREACIÓN ----------
created_ids = []
create_errors = []

if new_products:
    print(f"\n{'='*60}")
    print(f"CREANDO {len(new_products)} PRODUCTOS NUEVOS...")
    print(f"{'='*60}")
    create_start_time = time.time()
    
    for i in range(0, len(new_products), 50):
        batch = new_products[i:i+50]
        try:
            batch_ids = models.execute_kw(db, uid, password, 'product.template', 'create', [batch])
            if isinstance(batch_ids, int):
                batch_ids = [batch_ids]
            created_ids.extend(batch_ids)
            print_progress(min(i+50, len(new_products)), len(new_products), create_start_time, prefix="Creación productos")
        except Exception as e:
            error_msg = f"Error en lote {i}-{i+50}: {str(e)}"
            create_errors.append(error_msg)
            logging.error(error_msg)
            print(f"\n❌ {error_msg}")

    print(f"\n✓ Creados {len(created_ids)} productos exitosamente")


# ---------- ASIGNAR PROVEEDORES OPTIMIZADO EN LOTES ----------
if created_ids:
    print(f"\n{'='*60}")
    print("ASIGNANDO PROVEEDORES...")
    print(f"{'='*60}")

    # 1️⃣ Precargar proveedores del CSV
    all_seller_names = {sanitize_xml(row['seller_ids'].strip()) for row in csv_rows if has_value(row.get('seller_ids'))}
    seller_names = [name for name in all_seller_names if has_value(name)]
    print(f"Se detectaron {len(seller_names)} proveedores en el CSV...")

    # 2️⃣ Buscar partners existentes
    existing_partners = models.execute_kw(
        db, uid, password,
        'res.partner', 'search_read',
        [[['name', 'in', seller_names]]],
        {'fields': ['id', 'name']}
    )
    for partner in existing_partners:
        partners_cache[partner['name'].strip().lower()] = partner['id']

    # 3️⃣ Crear partners faltantes
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
        print(f"✓ Creados {len(to_create)} proveedores nuevos")

    # 4️⃣ Construir supplierinfo
    supplierinfo_to_create = []
    created_products_map = {}  # mapear barcode -> product_tmpl_id

    # Mapear productos creados por barcode
    for idx, vals in enumerate(new_products):
        if idx < len(created_ids):
            created_products_map[vals['barcode']] = created_ids[idx]

    for row in csv_rows:
        seller_name = sanitize_xml(row.get('seller_ids', '').strip())
        barcode = sanitize_xml(row.get('barcode', '').strip())
        
        if not has_value(seller_name) or not has_value(barcode):
            continue

        product_tmpl_id = created_products_map.get(barcode)
        if not product_tmpl_id:
            continue

        partner_id = partners_cache.get(seller_name.strip().lower())
        if partner_id:
            supplierinfo_to_create.append({
                'product_tmpl_id': product_tmpl_id,
                'name': partner_id
            })

    print(f"Se van a crear {len(supplierinfo_to_create)} relaciones producto-proveedor...")

    # 5️⃣ Crear supplierinfo en lotes
    if supplierinfo_to_create:
        batch_size = 100
        supplier_start = time.time()
        for i in range(0, len(supplierinfo_to_create), batch_size):
            batch = supplierinfo_to_create[i:i+batch_size]
            try:
                models.execute_kw(db, uid, password, 'product.supplierinfo', 'create', [batch])
                print_progress(i+len(batch), len(supplierinfo_to_create), supplier_start, prefix="Proveedores")
            except Exception as e:
                error_msg = f"Error asignando proveedores en lote {i}-{i+batch_size}: {str(e)}"
                create_errors.append(error_msg)
                logging.error(error_msg)


# ---------- RESUMEN FINAL ----------
elapsed = time.time() - start_time
all_errors = update_errors + create_errors

print(f"\n{'='*60}")
print(f"IMPORTACIÓN FINALIZADA")
print(f"{'='*60}")
print(f"Tiempo total:                    {elapsed:.2f} segundos")
print(f"Productos creados:               {len(created_ids)}")
print(f"Productos actualizados:          {updated_count}")  # ✨ NUEVO
print(f"Productos omitidos:              {len(skipped_products)}")
print(f"Errores:                         {len(all_errors)}")
print(f"{'='*60}")

if all_errors:
    print("\n❌ ERRORES DETECTADOS:")
    for error in all_errors[:10]:
        print(f"  - {error}")
    if len(all_errors) > 10:
        print(f"  ... y {len(all_errors) - 10} errores más (ver log)")

logging.info(f"Importación finalizada en {elapsed:.2f} segundos")
logging.info(f"Productos creados: {len(created_ids)}, Actualizados: {updated_count}, Omitidos: {len(skipped_products)}, Errores: {len(all_errors)}")
print(f"\n✓ Revisa el archivo '{log_path}' para más detalles")
