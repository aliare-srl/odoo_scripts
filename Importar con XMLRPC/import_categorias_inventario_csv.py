"""
Script BULK ULTRA de importación de categorías de inventario a Odoo 15 vía XML-RPC
Lee: categorias_inventarios.csv
Genera log de errores: import_log_inventario.txt
Importación por lotes (batch) para mayor velocidad
"""

import xmlrpc.client
import csv
import logging
import time

# ---------------------------
# CONFIGURACIÓN
# ---------------------------
url = "http://localhost:8069"
db = "nombre_de_tu_base"
username = "admin"
password = "admin"

csv_file = "categorias_inventarios.csv"
log_file = "import_log_inventario.txt"
batch_size = 50  # número de registros por batch

# ---------------------------
# LOGGING
# ---------------------------
logging.basicConfig(
    filename=log_file,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# ---------------------------
# CONEXIÓN ODOO
# ---------------------------
common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
uid = common.authenticate(db, username, password, {})
models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")

if not uid:
    logging.error("Error de autenticación en Odoo.")
    raise Exception("No se pudo autenticar en Odoo")

# ---------------------------
# HELPER: Normalizar texto
# ---------------------------
def _norm(s):
    if not s:
        return ""
    s = str(s).strip().lower()
    for a,b in [("á","a"),("é","e"),("í","i"),("ó","o"),("ú","u")]:
        s = s.replace(a,b)
    return s

# Mapeos a valores de Odoo
valuation_map = {
    "manual": "manual_periodic",
    "manual periodico": "manual_periodic",
    "manual (periodico)": "manual_periodic",
    "manual_periodic": "manual_periodic",
    "real_time": "real_time",
    "real time": "real_time",
    "automatico": "real_time",
    "automatico (en tiempo real)": "real_time",
    "automatico/real time": "real_time",
    "automatico (real time)": "real_time",
    "automatic": "real_time"
}

cost_method_map = {
    "precio estandar": "standard",
    "precio estándar": "standard",
    "estandar": "standard",
    "standard": "standard",
    "fifo": "fifo",
    "precio medio": "average",
    "promedio": "average",
    "average": "average",
    "costo promedio": "average"
}

def map_selection(value, mapping, field_name):
    if not value:
        return None
    key = _norm(value)
    mapped = mapping.get(key)
    if not mapped:
        logging.warning(f"Valor no reconocido para {field_name}: '{value}'. Se omite ese campo.")
    return mapped

# ---------------------------
# FUNCIÓN: obtener o crear categoría padre
# ---------------------------
def get_or_create_parent(parent_name):
    try:
        if not parent_name:
            return False
        parent_name = str(parent_name).strip()
        parent = models.execute_kw(db, uid, password, 'product.category', 'search', [[['name','=',parent_name]]], {'limit':1})
        if parent:
            return parent[0]
        parent_id = models.execute_kw(db, uid, password, 'product.category', 'create', [{'name': parent_name}])
        logging.info(f"Categoría padre '{parent_name}' creada con ID {parent_id}.")
        return parent_id
    except Exception as e:
        logging.error(f"Error al crear/buscar categoría padre '{parent_name}': {e}")
        return False

# ---------------------------
# LECTURA CSV Y BULK ULTRA
# ---------------------------
start_time = time.time()
ok_count = 0
fail_count = 0
batch_vals = []

try:
    csvfile = open(csv_file, newline='', encoding='utf-8', errors='replace')
except UnicodeDecodeError:
    csvfile = open(csv_file, newline='', encoding='latin-1', errors='replace')

reader = csv.DictReader(csvfile)
if "name" not in reader.fieldnames:
    logging.error("El CSV no contiene la columna obligatoria 'name'")
    raise Exception("El CSV no tiene la columna 'name'")

for index, row in enumerate(reader, start=1):
    try:
        name = str(row.get("name") or "").strip()
        if not name:
            logging.warning(f"Fila {index}: categoría vacía, saltada.")
            fail_count += 1
            continue

        # Campos opcionales
        parent_name = row.get("parent_id/id") or row.get("parent_id/name")
        prop_val = map_selection(row.get("property_valuation"), valuation_map, "property_valuation")
        prop_cost = map_selection(row.get("property_cost_method"), cost_method_map, "property_cost_method")

        # Verificar si ya existe
        existing = models.execute_kw(db, uid, password, 'product.category', 'search', [[['name','=',name]]], {'limit':1})
        if existing:
            logging.info(f"Fila {index}: categoría '{name}' ya existe, no se crea.")
            continue

        # Padre
        parent_id = get_or_create_parent(parent_name) if parent_name else False

        # Preparar batch
        vals = {'name': name}
        if parent_id: vals['parent_id'] = parent_id
        if prop_val: vals['property_valuation'] = prop_val
        if prop_cost: vals['property_cost_method'] = prop_cost

        batch_vals.append(vals)
        ok_count += 1

        # Crear batch si alcanza tamaño
        if len(batch_vals) >= batch_size:
            created_ids = models.execute_kw(db, uid, password, 'product.category', 'create', [batch_vals])
            logging.info(f"Batch de {len(batch_vals)} categorías creado. IDs: {created_ids}")
            batch_vals = []

    except Exception as e:
        logging.error(f"Fila {index}: error al importar '{row}': {e}")
        fail_count += 1

# Crear registros restantes
if batch_vals:
    created_ids = models.execute_kw(db, uid, password, 'product.category', 'create', [batch_vals])
    logging.info(f"Último batch de {len(batch_vals)} categorías creado. IDs: {created_ids}")

csvfile.close()
elapsed_time = time.time() - start_time

print(f"✅ Importación BULK ULTRA de categorías finalizada.")
print(f"Registros importados correctamente: {ok_count}")
print(f"Registros fallidos: {fail_count}")
print(f"Tiempo de ejecución: {elapsed_time:.2f} segundos")
print(f"Revisa el archivo {log_file} para detalles.")
