import xmlrpc.client
import math
import time

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
# BUSCAR SOLO IDs (lo más liviano posible)
# -------------------------------------------------------------------
domain = [("name", "ilike", "factur-x.xml")]

attachment_ids = models.execute_kw(
    db, uid, password,
    "ir.attachment", "search",
    [domain],
    {"limit": 0}
)

total = len(attachment_ids)
print(f"Encontrados: {total} adjuntos factur-x.xml para eliminar.")

if total == 0:
    print("Nada para borrar.")
    exit()

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

    # ejecutar eliminación
    models.execute_kw(
        db, uid, password,
        "ir.attachment", "unlink",
        [batch_ids]
    )

    deleted_total += len(batch_ids)

    print(f"Lote {i+1}/{batches}: eliminados {len(batch_ids)} adjuntos. Total acumulado: {deleted_total}")

    time.sleep(0.2)  # Pausa suave para evitar saturar el server

# -------------------------------------------------------------------
# RESULTADO FINAL
# -------------------------------------------------------------------
print("\n=====================================================")
print(f"Proceso completado. Total de adjuntos eliminados: {deleted_total}")
print("=====================================================")
