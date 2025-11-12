import xmlrpc.client
import math
import time
import sys

# -------------------------------------------------------------------
# CONFIGURACIÓN
# -------------------------------------------------------------------
url = "http://localhost:8069"      # Cambiá según tu instalación
db = "full24"
username = "desarrolloaliare@gnmail.com"
password = "ai102030abc"

PAGE_SIZE = 5000    # Cuántos IDs traer por lote (búsqueda)
DELETE_BATCH = 500  # Cuántos borrar por llamada
SLEEP_BETWEEN = 0.2 # Pausa entre llamadas

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
def progress(current, total):
    percent = (current / total) * 100 if total else 0
    bar = "#" * int(percent / 2)
    sys.stdout.write(f"\r[{bar:<50}] {percent:5.1f}% ({current}/{total})")
    sys.stdout.flush()

# -------------------------------------------------------------------
# BUSCAR TODAS LAS IDs POR PAGINAS
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

# -------------------------------------------------------------------
# ELIMINAR POR LOTES
# -------------------------------------------------------------------
deleted_total = 0
batches = math.ceil(total / DELETE_BATCH)

for i in range(batches):
    start = i * DELETE_BATCH
    end = start + DELETE_BATCH
    batch_ids = attachment_ids[start:end]

    # Intentar eliminar con control de errores
    try:
        models.execute_kw(
            db, uid, password,
            "ir.attachment", "unlink",
            [batch_ids]
        )
    except Exception as e:
        print(f"\n⚠️ Error al borrar lote {i+1}: {e}")
        continue

    deleted_total += len(batch_ids)
    progress(deleted_total, total)
    time.sleep(SLEEP_BETWEEN)

print("\n\n✅ Proceso completado.")
print(f"Total de adjuntos eliminados: {deleted_total}")
print("=====================================================")
