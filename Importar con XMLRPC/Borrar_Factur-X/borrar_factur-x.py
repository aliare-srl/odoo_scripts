import xmlrpc.client

# ---------------------------------------------------------
# CONFIGURACIÓN
# ---------------------------------------------------------
url = "http://localhost:8073"        # Ej: https://miempresa.odoo.com
db = "test"
username = "admin"
password = "admin"

# ---------------------------------------------------------
# AUTENTICACIÓN
# ---------------------------------------------------------
common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
uid = common.authenticate(db, username, password, {})

if not uid:
    raise Exception("No se pudo autenticar. Revisá usuario/contraseña.")

models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")

# ---------------------------------------------------------
# BUSCAR ADJUNTOS factur-x.xml
# ---------------------------------------------------------
domain = [
    ("name", "ilike", "factur-x.xml")
]

attachment_ids = models.execute_kw(
    db, uid, password,
    "ir.attachment", "search",
    [domain]
)

print(f"Adjuntos encontrados: {len(attachment_ids)}")

if attachment_ids:
    # ---------------------------------------------------------
    # BORRAR ADJUNTOS
    # ---------------------------------------------------------
    deleted = models.execute_kw(
        db, uid, password,
        "ir.attachment", "unlink",
        [attachment_ids]
    )
    print("Adjuntos eliminados:", deleted)
else:
    print("No se encontraron adjuntos para borrar.")
