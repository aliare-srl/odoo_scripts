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

excel_file = "proveedores.xlsx"
log_file = "import_log_proveedores.txt"

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

if "name" not in df.columns:
    logging.error("El Excel no contiene la columna 'name'")
    raise Exception("El Excel no tiene la columna 'name'")

# ---------------------------
# CARGAR MAPA DE TIPOS DE IDENTIFICACIÓN
# ---------------------------
id_types = models.execute_kw(
    db, uid, password,
    "l10n_latam.identification.type", "search_read",
    [[]],
    {"fields": ["id", "name"]}
)
id_type_map = {rec["name"].strip().upper(): rec["id"] for rec in id_types}

# ---------------------------
# IMPORTACIÓN DE PROVEEDORES
# ---------------------------
for index, row in df.iterrows():
    try:
        name = str(row["name"]).strip() if pd.notna(row.get("name")) else None
        vat = str(row["vat"]).strip() if pd.notna(row.get("vat")) else None
        street = str(row["street"]).strip() if pd.notna(row.get("street")) else None
        phone = str(row["phone_mobile_search"]).strip() if pd.notna(row.get("phone_mobile_search")) else None
        company_type = str(row["company_type"]).strip() if pd.notna(row.get("company_type")) else "company"

        # Tipo de identificación
        id_type_id = None
        if pd.notna(row.get("l10n_latam_identification_type_id/id")):
            id_type_id = int(row["l10n_latam_identification_type_id/id"])
        elif pd.notna(row.get("l10n_latam_identification_type_id/name")):
            name_val = str(row["l10n_latam_identification_type_id/name"]).strip().upper()
            id_type_id = id_type_map.get(name_val)
            if not id_type_id:
                logging.warning(f"Fila {index+1}: Tipo identificación '{name_val}' no encontrado en Odoo")

        # Responsabilidad AFIP
        afip_type_id = None
        if pd.notna(row.get("l10n_ar_afip_responsibility_type_id/id")):
            afip_type_id = int(row["l10n_ar_afip_responsibility_type_id/id"])
        elif pd.notna(row.get("l10n_ar_afip_responsibility_type_id")):
            afip_name = str(row["l10n_ar_afip_responsibility_type_id"]).strip()
            res = models.execute_kw(
                db, uid, password,
                "l10n_ar.afip.responsibility.type", "search",
                [[["name", "=", afip_name]]], {"limit": 1}
            )
            if res:
                afip_type_id = res[0]
            else:
                logging.warning(f"Fila {index+1}: Responsabilidad AFIP '{afip_name}' no encontrada en Odoo")

        if not name:
            logging.warning(f"Fila {index+1}: proveedor vacío, saltado.")
            continue

        # Verificar si ya existe (por VAT o nombre)
        domain = [['name', '=', name]]
        if vat:
            domain = ['|', ['name', '=', name], ['vat', '=', vat]]

        existing = models.execute_kw(
            db, uid, password,
            'res.partner', 'search',
            [domain]
        )

        if existing:
            logging.info(f"Fila {index+1}: proveedor '{name}' ya existe, no se crea.")
            continue

        # Crear proveedor
        vals = {
            'name': name,
            'supplier_rank': 1,  # marcar como proveedor
            'company_type': company_type,
        }
        if vat: vals['vat'] = vat
        if street: vals['street'] = street
        if phone: vals['phone'] = phone
        if id_type_id: vals['l10n_latam_identification_type_id'] = id_type_id
        if afip_type_id: vals['l10n_ar_afip_responsibility_type_id'] = afip_type_id

        new_id = models.execute_kw(
            db, uid, password,
            'res.partner', 'create',
            [vals]
        )
        logging.info(f"Fila {index+1}: proveedor '{name}' creado con ID {new_id}.")

    except Exception as e:
        logging.error(f"Fila {index+1}: error al importar '{row.to_dict()}': {e}")

print("✅ Importación de proveedores finalizada. Revisa el archivo import_log_proveedores.txt para detalles.")
