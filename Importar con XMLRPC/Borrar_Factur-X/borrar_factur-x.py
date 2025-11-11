import xmlrpc.client
import math
import time
import os
import sys

# ---------------------------------------------------------
# CONFIGURACIÓN
# ---------------------------------------------------------
url = "http://localhost:8073"
db = "test"
username = "admin"
password = "admin"

BATCH_SIZE = 500

# Ruta del filestore de la base
FILESTORE_PATH = f"/var/lib/odoo/.local/share/Odoo/filestore/{db}"


# ---------------------------------------------------------
# FUNCIÓN PARA MEDIR TAMAÑO DEL FILESTORE
# ---------------------------------------------------------
def get_filestore_size(path):
    total_bytes = 0
    for root, dirs, files in os.walk(path):
        for f in files:
            fp = os.path.join(root, f)
            total_bytes += os.path.getsize(fp)
    return total_bytes


def fmt(size_bytes):
    mb = size_bytes / (1024 * 1024)
    gb = size_bytes / (1024 * 1024 * 1024)
    return f"{mb:.2f} MB ({gb:.2f} GB)"


# ---------------------------------------------------------
# FUNCIÓN BARRA DE PROGRESO
# ---------------------------------------------------------
def progress_bar(current, total, bar_length=40):
    percent = current / total
    filled = int(bar_length * percent)
    bar = "█" * filled + "░" * (bar_length - filled)
    sys.stdout.write(f"\r[{bar}] {percent*100:6.2f}% ({current}/{total})")
    sys.stdout.flush()


# ---------------------------------------------------------
# MEDIR TAMAÑO INICIAL
# ---------------------------------------------------------
print("Midiendo espacio usado del filestore...")
size_before = get_filestore_size(FILESTORE_PATH)
print(f"Filestore inicial: {fmt(size_before)}\n")


# ---------------------------------------------------------
# AUTENTICACIÓN
# ---------------------------------------------------------
common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
uid = common.authenticate(db, username, password, {})
if not uid:
    raise Exception("No se pudo autenticar.")

models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")

# ---------------------------------------------------------
# BUSCAR ADJUNTOS factur-x.xml
# ---------------------------------------------------------
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

# ---------------------------------------------------------
# BORRADO POR LOTES CON BARRA DE PROGRESO
# ---------------------------------------------------------
batches = math.ceil(total / BATCH_SIZE)
deleted_total = 0

print(f"Eliminando en {batches} lotes de {BATCH_SIZE}...\n")

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

    # actualizar barra
    progress_bar(deleted_total, total)

    time.sleep(0.1)

print("\n")


# ---------------------------------------------------------
# MEDIR ESPACIO FINAL
# ---------------------------------------------------------
print("Midiendo espacio final del filestore...")
size_after = get_filestore_size(FILESTORE_PATH)

freed = size_before - size_after

print("\n=====================================================")
print(f"Filestore antes:   {fmt(size_before)}")
print(f"Filestore después: {fmt(size_after)}")
print(f"Espacio liberado:  {fmt(freed)}")
print(f"Adjuntos eliminados: {deleted_total}")
print("=====================================================")
