"""
Script BULK ULTRA de importación de marcas a Odoo 15 vía XML-RPC
Lee: marcas.csv
Genera log de errores: import_log_marcas.txt
Importación por lotes (batch) para mayor velocidad
"""

import xmlrpc.client
import csv
import logging
import time

# ---------------------------
# CONFIGURACIÓN
# ---------------------------
url = "http://localhost:8073"
db = "test"
username = "admin"
password = "admin"

csv_file = "marcas.csv"
log_file = "import_log_marcas.txt"
batch_size = 50  # número de registros a crear por batch

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
# LECTURA DEL CSV
# ---------------------------
try:
    csvfile = open(csv_file, newline='', encoding='utf-8', errors='replace')
except UnicodeDecodeError:
    csvfile = open(csv_file, newline='', encoding='latin-1', errors='replace')

reader = csv.DictReader(csvfile)
fieldnames = reader.fieldnames
if "name" not in fieldnames:
    logging.error("El CSV no contiene la columna 'name'")
    raise Exception("El CSV no tiene la columna 'name'")

# ---------------------------
# IMPORTACIÓN BULK ULTRA
# ---------------------------
start_time = time.time()
ok_count = 0
fail_count = 0
batch_vals = []

for index, row in enumerate(reader, start=1):
    try:
        name = str(row.get("name") or "").strip()

        if not name:
            logging.warning(f"Fila {index}: marca vacía, saltada.")
            fail_count += 1
            continue

        # Verificar si ya existe la marca
        existing = models.execute_kw(
            db, uid, password,
            'product.brand', 'search',
            [[['name', '=', name]]]
        )

        if existing:
            logging.info(f"Fila {index}: marca '{name}' ya existe, no se crea.")
            continue

        # Preparar registro para batch
        vals = {'name': name}
        batch_vals.append(vals)
        ok_count += 1

        # Ejecutar batch
        if len(batch_vals) >= batch_size:
            created_ids = models.execute_kw(db, uid, password, 'product.brand', 'create', [batch_vals])
            logging.info(f"Batch de {len(batch_vals)} marcas creado. IDs: {created_ids}")
            batch_vals = []

    except Exception as e:
        logging.error(f"Fila {index}: error al importar '{row}': {e}")
        fail_count += 1

# Crear registros restantes
if batch_vals:
    created_ids = models.execute_kw(db, uid, password, 'product.brand', 'create', [batch_vals])
    logging.info(f"Último batch de {len(batch_vals)} marcas creado. IDs: {created_ids}")

csvfile.close()
elapsed_time = time.time() - start_time

print(f"✅ Importación BULK ULTRA de marcas finalizada.")
print(f"Registros importados correctamente: {ok_count}")
print(f"Registros fallidos: {fail_count}")
print(f"Tiempo de ejecución: {elapsed_time:.2f} segundos")
print(f"Revisa el archivo {log_file} para detalles.")
