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

BATCH_SIZE = 500  # Ajustable: 200 / 500 / 1000

# -------------------------------------------------------------------
# AUTENTICACIÓN
# -------------------------------------------------------------------
common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
uid = common.authenticate(db, username, password, {})

if not uid:
    raise Exception("No se pudo autenticar.")

models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")

# -------------------------------------------------------------------
# BUSCAR SOLO IDs (rápido y liviano)
# -------------------------------------------------------------------
domain = [("name", "ilike", "factur-x.xml")]

attachment_ids = models.execute_kw(
    db, uid, password,
    "ir.attachment", "search",
    [domain],
    {"limit": 0}  # devuelve todos los IDs sin cargar objetos
)

total = len(attachment_ids)
print(f"Encontrados: {total} adjuntos factur-x.xml")

if total == 0:
    print("Nada para borrar.")
    exit()

# -------------------------------------------------------------------
# BORRAR POR LOTES
# -------------------------------------------------------------------
batches = math.ceil(total / BATCH_SIZE)

print(f"Eliminando en {batches} lotes de {BATCH_SIZE}...")

for i in range(batches):
    start = i * BATCH_SIZE
    end = start + BATCH_SIZE
    batch_ids = attachment_ids[start:end]

    print(f"Lote {i+1}/{batches} - IDs: {len(batch_ids)}")

    models.execute_kw(
        db, uid, password,
        "ir.attachment", "unlink",
        [batch_ids]
    )

    # Pausa leve para no saturar el server en instalaciones chicas
    time.sleep(0.2)

print("Proceso completado.")
