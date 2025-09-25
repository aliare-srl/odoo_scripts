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

csv_file = "lista_precios.csv"
log_file = "import_log_pricelists.txt"
batch_size = 50

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

def execute_kw(model, method, args, kwargs=None):
    return models.execute_kw(db, uid, password, model, method, args, kwargs or {})

# ---------------------------
# MAPAS PRECALCULADOS
# ---------------------------
existing_pricelists = execute_kw("product.pricelist", "search_read", [[]], {"fields": ["name"]})
existing_pricelist_names = {pl["name"].strip().upper() for pl in existing_pricelists if pl.get("name")}

# ---------------------------
# LECTURA DEL CSV
# ---------------------------
csvfile = open(csv_file, newline='', encoding='utf-8', errors='replace')
reader = csv.DictReader(csvfile)

# ---------------------------
# IMPORTACIÓN BULK
# ---------------------------
batch_vals = []
ok_count = 0
fail_count = 0

start_total = time.time()

for index, row in enumerate(reader, start=1):
    start_row = time.time()
    try:
        name = str(row.get("descripcion_lista") or "").strip()
        currency = str(row.get("currency_id") or "").strip()

        if not name:
            logging.warning(f"Fila {index}: lista sin nombre, saltada.")
            fail_count += 1
            continue

        if name.upper() in existing_pricelist_names:
            logging.info(f"Fila {index}: lista '{name}' ya existe, no se crea.")
            continue

        vals = {
            "name": name,
        }

        if currency:
            # Buscar moneda
            currency_id = execute_kw("res.currency", "search", [[("name", "=", currency)]], {"limit": 1})
            if currency_id:
                vals["currency_id"] = currency_id[0]

        batch_vals.append(vals)
        ok_count += 1

        if len(batch_vals) >= batch_size:
            try:
                created_ids = execute_kw("product.pricelist", "create", [batch_vals])
                batch_time = time.time() - start_row
                logging.info(f"Batch de {len(batch_vals)} listas creado en {batch_time:.2f} s. IDs: {created_ids}")
            except Exception as e:
                logging.error(f"Error al crear batch en fila {index}: {e}")
            batch_vals = []
            time.sleep(1)

    except Exception as e:
        logging.error(f"Fila {index}: error al importar '{row}': {e}")
        fail_count += 1

if batch_vals:
    try:
        created_ids = execute_kw("product.pricelist", "create", [batch_vals])
        logging.info(f"Último batch de {len(batch_vals)} listas creado. IDs: {created_ids}")
    except Exception as e:
        logging.error(f"Error al crear último batch: {e}")

csvfile.close()
total_time = time.time() - start_total

print(f"✅ Importación finalizada. Correctos: {ok_count}, Fallidos: {fail_count}")
print(f"Tiempo total de importación: {total_time:.2f} segundos")
print(f"Revisá el log: {log_file}")
