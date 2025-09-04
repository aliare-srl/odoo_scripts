import pandas as pd
import xmlrpc.client
import logging

# ---------------------------
# CONFIGURACIÓN
# ---------------------------
url = "http://localhost:8069"   # URL de tu Odoo (¡incluí el puerto!)
db = "nombre_de_tu_base"        # Base de datos
username = "admin"              # Usuario
password = "admin"              # Contraseña

excel_file = "categorias_inventarios.xlsx"
log_file = "import_log_inventario.txt"

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

# Validaciones mínimas
required_cols = ["name"]
for c in required_cols:
    if c not in df.columns:
        logging.error(f"El Excel no contiene la columna obligatoria '{c}'")
        raise Exception(f"El Excel no tiene la columna '{c}'")

# Helper: normalizar texto
def _norm(s):
    if pd.isna(s):
        return ""
    s = str(s).strip()
    return s.lower().replace("á","a").replace("é","e").replace("í","i").replace("ó","o").replace("ú","u")

# Mapeos a valores de Odoo
valuation_map = {
    "manual": "manual_periodic",
    "manual periodico": "manual_periodic",
    "manual (periodico)": "manual_periodic",
    "manual (periodico/periodic)": "manual_periodic",
    "manual_periodic": "manual_periodic",
    "real_time": "real_time",
    "real time": "real_time",
    "automatico": "real_time",
    "automatico (en tiempo real)": "real_time",
    "automatico/real time": "real_time",
    "automatico (real time)": "real_time",
    "automatico (real-time)": "real_time",
    "automatico (automatic)": "real_time",
    "automatic": "real_time",
    "automatico (automatico)": "real_time",
    "automatico (automatizado)": "real_time",
    "automatico (en linea)": "real_time"
}

cost_method_map = {
    "precio estandar": "standard",
    "precio estándar": "standard",
    "estandar": "standard",
    "estándar": "standard",
    "standard": "standard",
    "precio standard": "standard",
    "fifo": "fifo",
    "precio medio": "average",
    "promedio": "average",
    "average": "average",
    "costo promedio": "average"
}

def map_selection(value, mapping, field_name):
    """Mapea un valor legible a la constante técnica de Odoo. Devuelve None si no reconoce."""
    if pd.isna(value):
        return None
    key = _norm(value)
    mapped = mapping.get(key)
    if not mapped:
        logging.warning(f"Valor no reconocido para {field_name}: '{value}'. Se omite ese campo.")
    return mapped

# ---------------------------
# FUNCIÓN: obtener o crear categoría padre
# ---------------------------
def get_or_create_parent(parent_name):
    """Busca el ID de la categoría padre, y si no existe, la crea (sin propiedades)."""
    try:
        parent_name = str(parent_name).strip()
        if not parent_name:
            return False

        parent = models.execute_kw(
            db, uid, password,
            'product.category', 'search',
            [[['name', '=', parent_name]]],
            {'limit': 1}
        )
        if parent:
            return parent[0]

        parent_id = models.execute_kw(
            db, uid, password,
            'product.category', 'create',
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
        parent_name = None
        if "parent_id/id" in df.columns and pd.notna(row.get("parent_id/id")):
            parent_name = str(row.get("parent_id/id")).strip()

        # Campos extra (opcionales)
        prop_val = None
        prop_cost = None
        if "property_valuation" in df.columns:
            prop_val = map_selection(row.get("property_valuation"), valuation_map, "property_valuation")
        if "property_cost_method" in df.columns:
            prop_cost = map_selection(row.get("property_cost_method"), cost_method_map, "property_cost_method")

        if not name or _norm(name) in ("", "nan"):
            logging.warning(f"Fila {index+1}: categoría vacía, saltada.")
            continue

        # ¿Ya existe?
        existing = models.execute_kw(
            db, uid, password,
            'product.category', 'search',
            [[['name', '=', name]]],
            {'limit': 1}
        )
        if existing:
            logging.info(f"Fila {index+1}: categoría '{name}' ya existe, no se crea.")
            continue

        # Padre
        parent_id = False
        if parent_name:
            parent_id = get_or_create_parent(parent_name)

        # Valores a crear
        vals = {'name': name}
        if parent_id:
            vals['parent_id'] = parent_id
        if prop_val:
            vals['property_valuation'] = prop_val
        if prop_cost:
            vals['property_cost_method'] = prop_cost

        new_id = models.execute_kw(
            db, uid, password,
            'product.category', 'create',
            [vals]
        )
        logging.info(f"Fila {index+1}: categoría '{name}' creada con ID {new_id}. vals={vals}")

    except Exception as e:
        logging.error(f"Fila {index+1}: error al importar '{row.to_dict()}': {e}")

print("✅ Importación finalizada. Revisa el archivo import_log_inventario.txt para detalles.")
