import xmlrpc.client
import math
import time
import sys

# ---------------------------------------------------------
# CONFIGURACIÓN
# ---------------------------------------------------------
url = "http://localhost:8073"        # Ej: https://miempresa.odoo.com
db = "test"
username = "admin"
password = "admin"

BATCH_SIZE = 500  # Ajustable según la fuerza del servidor

# -------------------------------------------------------------------
# AUTENTICACIÓN
# -------------------------------------------------------------------
common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
uid = common.authenticate(db, username, password, {})

if not uid:
    raise Exception("No se pudo autenticar.")

models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")

# -------------------------------------------------------------------
# BUSCAR SOLO IDs
# -------------------------------------------------------------------
domain = [("name", "ilike", "factur-x.xml")]

attachment_ids = models.execute_kw(
    db, uid, password,
    "ir.attachment", "search",
    [domain],
    {"limit": 0}
)

total = len(attachment_ids)
print(f"Encontrados: {total} adjuntos factur-x.xml para eliminar.\n")

if total == 0:
    print("Nada para borrar.")
    exit()

# -------------------------------------------------------------------
# FUNCIÓN: BARRA DE PROGRESO
# -------------------------------------------------------------------
def progress_bar(current, total, bar_length=40):
    percent = current / total
    completed = int(bar_length * percent)
    bar = "█" * completed + "-" * (bar_length - completed)
    sys.stdout.write(f"\r[{bar}] {percent*100:5.1f}%  ({current}/{total})")
    sys.stdout.flush()

# -------------------------------------------------------------------
# BORRAR POR LOTES
# -------------------------------------------------------------------
batches = math.ceil(total / BATCH_SIZE)
deleted_total = 0

print(f"Eliminando en {batches} lotes de hasta {BATCH_SIZE} registros cada uno...\n")

for i in range(batches):
    start = i * BATCH_SIZE
    end = start + BATCH_SIZE
    batch_ids = attachment_ids[start:end]

    models.execute_kw(
        db, uid, password,
        "ir.attachment", "unlink",
        [batch_ids]
    )

    deleted_total += len(batch_ids)

    # actualizar progreso
    progress_bar(deleted_total, total)

    time.sleep(0.1)

print("\n\n=====================================================")
print(f"Proceso completado. Total de adjuntos eliminados: {deleted_total}")
print("=====================================================")
