import pandas as pd
import xmlrpc.client
import logging

# ---------------------------
# CONFIGURACIÓN
# ---------------------------
url = "http://localhost:8069"   # URL de tu Odoo
db = "nombre_de_tu_base"        # Base de datos
username = "admin"              # Usuario
password = "admin"              # Contraseña

excel_file = "categorias_tpv.xlsx"
log_file = "import_log.txt"

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
# FUNCIÓN: obtener o crear categoría padre
# ---------------------------
def get_or_create_parent(parent_name):
    """Busca el ID de la categoría padre, y si no existe, la crea."""
    try:
        parent = models.execute_kw(
            db, uid, password,
            'pos.category', 'search',
            [[['name', '=', parent_name]]],
            {'limit': 1}
        )
        if parent:
            return parent[0]

        # Crear la categoría padre
        parent_id = models.execute_kw(
            db, uid, password,
            'pos.category', 'create',
            [{'name': parent_name}]
        )
        logging.info(f"Categoría padre '{parent_name}' creada con ID {parent_id}.")
        return parent_id

    except Exception as e:
        logging.error(f"Error al crear/buscar categoría padre '{parent_name}': {e}")
        return False


# ---------------------------
# IMPORTACIÓN
# ---------------------------
for index, row in df.iterrows():
    try:
        name = str(row["name"]).strip()
        parent_name = str(row["parent_id/id"]).strip() if pd.notna(row["parent_id/id"]) else None

        if not name or name.lower() == "nan":
            logging.warning(f"Fila {index+1}: categoría vacía, saltada.")
            continue

        # Verificar si ya existe
        existing = models.execute_kw(
            db, uid, password,
            'pos.category', 'search',
            [[['name', '=', name]]]
        )

        if existing:
            logging.info(f"Fila {index+1}: categoría '{name}' ya existe, no se crea.")
            continue

        # Obtener o crear categoría padre
        parent_id = False
        if parent_name:
            parent_id = get_or_create_parent(parent_name)

        # Crear la categoría
        vals = {'name': name}
        if parent_id:
            vals['parent_id'] = parent_id

        new_id = models.execute_kw(
            db, uid, password,
            'pos.category', 'create',
            [vals]
        )
        logging.info(f"Fila {index+1}: categoría '{name}' creada con ID {new_id}.")

    except Exception as e:
        logging.error(f"Fila {index+1}: error al importar '{row.to_dict()}': {e}")

print("✅ Importación finalizada. Revisa el archivo import_log.txt para detalles.")
