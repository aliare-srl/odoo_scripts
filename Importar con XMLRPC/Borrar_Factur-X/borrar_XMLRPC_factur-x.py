import xmlrpc.client
import math
import sys
import time

# -------------------------------------------------------------------
# CONFIGURACIÓN
# -------------------------------------------------------------------
url = "http://localhost:8069"
db = "full24"
username = "desarrolloaliare@gmail.com"
password = "ai102030abc"

MAX_DELETE = 10000     # máximo total a eliminar
BATCH_SIZE = 1000     # tamaño de lote
SLEEP_BETWEEN = 1    # pausa entre lotes (segundos)

# -------------------------------------------------------------------
# AUTENTICACIÓN
# -------------------------------------------------------------------
common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
uid = common.authenticate(db, username, password, {})
if not uid:
    raise Exception("❌ No se pudo autenticar con Odoo.")

models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")

# -------------------------------------------------------------------
# FUNCIÓN AUXILIAR DE PROGRESO
# -------------------------------------------------------------------
def progress(current, total):
    percent = (current / total) * 100 if total else 0
    bar = "#" * int(percent / 2)
    sys.stdout.write(f"\r[{bar:<50}] {percent:5.1f}% ({current}/{total})")
    sys.stdout.flush()

# -------------------------------------------------------------------
# BUSCAR LOS ADJUNTOS FACTUR-X
# -------------------------------------------------------------------
print("🔎 Buscando adjuntos 'factur-x.xml'...")

attachment_ids = models.execute_kw(
    db, uid, password,
    "ir.attachment", "search",
    [[("name", "ilike", "factur-x.xml")]],
    {"limit": MAX_DELETE}
)

total = len(attachment_ids)
if total == 0:
    print("✅ No se encontraron adjuntos 'factur-x.xml'.")
    sys.exit(0)

print(f"Se encontraron {total} adjuntos. Comenzando eliminación por lotes...\n")

# -------------------------------------------------------------------
# ELIMINAR EN LOTES
# -------------------------------------------------------------------
deleted_total = 0
batches = math.ceil(total / BATCH_SIZE)

for i in range(batches):
    start = i * BATCH_SIZE
    end = start + BATCH_SIZE
    batch_ids = attachment_ids[start:end]

    try:
        models.execute_kw(
            db, uid, password,
            "ir.attachment", "unlink",
            [batch_ids]
        )
        deleted_total += len(batch_ids)
        progress(deleted_total, total)
    except Exception as e:
        print(f"\n⚠️  Error en el lote {i+1}: {e}")
    time.sleep(SLEEP_BETWEEN)

print("\n\n✅ Proceso completado.")
print(f"Total de adjuntos eliminados: {deleted_total}")
print("=====================================================")
