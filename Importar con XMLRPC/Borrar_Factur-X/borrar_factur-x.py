import xmlrpc.client
import math
import time
import sys
import logging
from datetime import datetime

# -------------------------------------------------------------------
# CONFIGURACIÓN
# -------------------------------------------------------------------
url = "http://localhost:8069"
db = "full24"
username = "desarrolloaliare@gnmail.com"
password = "ai102030abc"

PAGE_SIZE = 5000        # Cuántos IDs traer por lote (búsqueda)
DELETE_BATCH = 500      # Tamaño inicial del lote de borrado
SLEEP_BETWEEN = 0.2     # Pausa entre lotes
MAX_RETRIES = 3         # Reintentos por lote
MIN_BATCH = 10          # Tamaño mínimo si se reduce por error

# -------------------------------------------------------------------
# LOGGING
# -------------------------------------------------------------------
logging.basicConfig(
    filename="delete_attachments.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logging.info("=== INICIO DEL PROCESO ===")

# -------------------------------------------------------------------
# AUTENTICACIÓN
# -------------------------------------------------------------------
common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
uid = common.authenticate(db, username, password, {})

if not uid:
    raise Exception("❌ No se pudo autenticar.")

models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")

# -------------------------------------------------------------------
# FUNCIÓN AUXILIAR PARA MOSTRAR PROGRESO
# -------------------------------------------------------------------
def progress(current, total, start_time):
    percent = (current / total) * 100 if total else 0
    elapsed = time.time() - start_time
    rate = current / elapsed if elapsed > 0 else 0
    remaining = (total - current) / rate if rate > 0 else 0
    bar = "#" * int(percent / 2)
    sys.stdout.write(
        f"\r[{bar:<50}] {percent:5.1f}% ({current}/{total}) "
        f"ETA: {remaining/60:5.1f} min"
    )
    sys.stdout.flush()

# -------------------------------------------------------------------
# BUSCAR TODAS LAS IDs POR PÁGINAS
# -------------------------------------------------------------------
print("🔎 Buscando adjuntos 'factur-x.xml'...")
domain = [("name", "ilike", "factur-x.xml")]
attachment_ids = []
offset = 0

while True:
    try:
        batch = models.execute_kw(
            db, uid, password,
            "ir.attachment", "search",
            [domain],
            {"offset": offset, "limit": PAGE_SIZE}
        )
    except Exception as e:
        print(f"\n⚠️ Error recuperando IDs, reintentando en 5s... ({e})")
        logging.warning(f"Error recuperando IDs: {e}")
        time.sleep(5)
        continue

    if not batch:
        break

    attachment_ids.extend(batch)
    offset += PAGE_SIZE
    print(f"  → Cargados {len(attachment_ids)} IDs hasta ahora...")

total = len(attachment_ids)
if total == 0:
    print("✅ No se encontraron adjuntos 'factur-x.xml'.")
    sys.exit(0)

print(f"\nSe encontraron {total} adjuntos. Comenzando eliminación...\n")
logging.info(f"Total de adjuntos encontrados: {total}")

# -------------------------------------------------------------------
# FUNCIÓN PARA BORRAR UN LOTE CON REINTENTOS Y DIVISIÓN AUTOMÁTICA
# -------------------------------------------------------------------
def delete_batch(batch_ids, attempt=1):
    global DELETE_BATCH
    try:
        start = time.time()
        models.execute_kw(db, uid, password, "ir.attachment", "unlink", [batch_ids])
        elapsed = time.time() - start
        logging.info(f"Borrado exitoso de {len(batch_ids)} adjuntos en {elapsed:.2f}s")
        return True
    except Exception as e:
        msg = f"⚠️ Error al borrar {len(batch_ids)} adjuntos: {e}"
        print(f"\n{msg}")
        logging.error(msg)

        if len(batch_ids) > MIN_BATCH:
            # Si el lote es grande, dividir y reintentar
            mid = len(batch_ids) // 2
            logging.info(f"Dividiendo lote en 2 de tamaño {mid}")
            delete_batch(batch_ids[:mid], attempt)
            delete_batch(batch_ids[mid:], attempt)
        elif attempt < MAX_RETRIES:
            # Reintentar con backoff exponencial
            wait = 5 * (2 ** (attempt - 1))
            logging.warning(f"Reintentando en {wait}s (intento {attempt})...")
            time.sleep(wait)
            delete_batch(batch_ids, attempt + 1)
        else:
            logging.error(f"Lote fallido definitivamente: {batch_ids}")
        return False

# -------------------------------------------------------------------
# ELIMINAR POR LOTES
# -------------------------------------------------------------------
deleted_total = 0
start_time = time.time()
batches = math.ceil(total / DELETE_BATCH)

for i in range(batches):
    start = i * DELETE_BATCH
    end = start + DELETE_BATCH
    batch_ids = attachment_ids[start:end]

    success = delete_batch(batch_ids)
    if success:
        deleted_total += len(batch_ids)

    progress(deleted_total, total, start_time)
    time.sleep(SLEEP_BETWEEN)

print("\n\n✅ Proceso completado.")
print(f"Total de adjuntos eliminados: {deleted_total}")
logging.info(f"Total de adjuntos eliminados: {deleted_total}")
logging.info("=== FIN DEL PROCESO ===")
print("=====================================================")
