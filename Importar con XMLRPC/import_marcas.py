import pandas as pd
import xmlrpc.client
import logging

# ---------------------------
# CONFIGURACIÓN
# ---------------------------
url = "http://localhost:8069"   # URL de tu Odoo
db = "nombre_de_tu_base"        # Nombre de la base de datos
username = "admin"              # Usuario
password = "admin"              # Contraseña

excel_file = "marcas.xlsx"
log_file = "import_log_marcas.txt"

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
# LECTURA DEL EXCEL
# ---------------------------
df = pd.read_excel(excel_file)

# Validar que exista la columna 'name'
if "name" not in df.columns:
    logging.error("El Excel no contiene la columna 'name'")
    raise Exception("El Excel no tiene la columna 'name'")

# ---------------------------
# IMPORTACIÓN DE MARCAS
# ---------------------------
for index, row in df.iterrows():
    try:
        name = str(row["name"]).strip()

        if not name or name.lower() == "nan":
            logging.warning(f"Fila {index+1}: marca vacía, saltada.")
            continue

        # Verificar si ya existe la marca
        existing = models.execute_kw(
            db, uid, password,
            'product.brand', 'search',
            [[['name', '=', name]]]
        )

        if existing:
            logging.info(f"Fila {index+1}: marca '{name}' ya existe, no se crea.")
            continue

        # Crear la marca
        vals = {'name': name}

        new_id = models.execute_kw(
            db, uid, password,
            'product.brand', 'create',
            [vals]
        )
        logging.info(f"Fila {index+1}: marca '{name}' creada con ID {new_id}.")

    except Exception as e:
        logging.error(f"Fila {index+1}: error al importar '{row.to_dict()}': {e}")

print("✅ Importación de marcas finalizada. Revisa el archivo import_log_marcas.txt para detalles.")
