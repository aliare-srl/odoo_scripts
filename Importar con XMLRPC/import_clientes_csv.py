"""
Script BULK ULTRA de importación de proveedores a Odoo 15 vía XML-RPC
Lee: proveedores.csv
Genera log de errores: import_log_proveedores.txt
Importación por lotes (batch) para mayor velocidad
"""

import xmlrpc.client
import csv
import logging
import re
import time

# ---------------------------
# CONFIGURACIÓN
# ---------------------------
url = "http://localhost:8069"
db = "nombre_de_tu_base"
username = "admin"
password = "admin"

csv_file = "clientes.csv"
log_file = "import_log_clientes.txt"
batch_size = 50  # número de registros a crear por batch

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
# CARGAR MAPA DE TIPOS DE IDENTIFICACIÓN
# ---------------------------
id_types = models.execute_kw(
    db, uid, password,
    "l10n_latam.identification.type", "search_read",
    [[]],
    {"fields": ["id", "name"]}
)
id_type_map = {rec["name"].replace(" ", "").upper(): rec["id"] for rec in id_types}

# ---------------------------
# LECTURA DEL CSV
# ---------------------------
try:
    csvfile = open(csv_file, newline='', encoding='utf-8', errors='replace')
except UnicodeDecodeError:
    csvfile = open(csv_file, newline='', encoding='latin-1', errors='replace')

reader = csv.DictReader(csvfile)
fieldnames = reader.fieldnames
if "name" not in fieldnames:
    logging.error("El CSV no contiene la columna 'name'")
    raise Exception("El CSV no tiene la columna 'name'")

# ---------------------------
# IMPORTACIÓN BULK
# ---------------------------
start_time = time.time()
ok_count = 0
fail_count = 0
batch_vals = []

for index, row in enumerate(reader, start=1):
    try:
        name = str(row.get("name") or "").strip()
        street = str(row.get("street") or "").strip()
        phone = str(row.get("phone_mobile_search") or "").strip()
        company_type = str(row.get("company_type") or "company").strip()

        # NUEVAS COLUMNAS: supplier_rank y customer_rank
        supplier_rank = row.get("supplier_rank")
        customer_rank = row.get("customer_rank")

        try:
            supplier_rank = int(supplier_rank) if supplier_rank not in [None, ""] else 1
        except ValueError:
            supplier_rank = 1

        try:
            customer_rank = int(customer_rank) if customer_rank not in [None, ""] else 0
        except ValueError:
            customer_rank = 0

        # Tipo de identificación
        id_type_name = str(row.get("l10n_latam_identification_type_id/name") or "").strip().upper()
        id_type_id = None
        if row.get("l10n_latam_identification_type_id/id"):
            id_type_id = int(row["l10n_latam_identification_type_id/id"])
        elif id_type_name:
            id_type_id = id_type_map.get(id_type_name.replace(" ", ""))

        # VAT: limpiar caracteres no numéricos
        vat = str(row.get("vat") or "").strip()
        vat = re.sub(r'\D', '', vat)

        if id_type_name.replace(" ", "") == "CUIT" and vat and len(vat) != 11:
            logging.warning(f"Fila {index}: CUIT inválido '{vat}', se omite VAT")
            vat = False

        # Responsabilidad AFIP
        afip_type_id = None
        if row.get("l10n_ar_afip_responsibility_type_id/id"):
            afip_type_id = int(row["l10n_ar_afip_responsibility_type_id/id"])
        elif row.get("l10n_ar_afip_responsibility_type_id"):
            afip_name = str(row["l10n_ar_afip_responsibility_type_id"]).strip()
            res = models.execute_kw(
                db, uid, password,
                "l10n_ar.afip.responsibility.type", "search",
                [[["name", "=", afip_name]]], {"limit": 1}
            )
            if res:
                afip_type_id = res[0]

        if not name:
            logging.warning(f"Fila {index}: proveedor vacío, saltado.")
            fail_count += 1
            continue

        # Verificar duplicados
        domain = [['name', '=', name]]
        if vat:
            domain = ['|', ['name', '=', name], ['vat', '=', vat]]
        existing = models.execute_kw(db, uid, password, 'res.partner', 'search', [domain])

        if existing:
            logging.info(f"Fila {index}: proveedor '{name}' ya existe, no se crea.")
            continue

        # Preparar registro para batch
        vals = {
            'name': name,
            'supplier_rank': supplier_rank,
            'customer_rank': customer_rank,
            'company_type': company_type,
        }
        if vat: vals['vat'] = vat
        if street: vals['street'] = street
        if phone: vals['phone'] = phone
        if id_type_id: vals['l10n_latam_identification_type_id'] = id_type_id
        if afip_type_id: vals['l10n_ar_afip_responsibility_type_id'] = afip_type_id

        batch_vals.append(vals)
        ok_count += 1

        if len(batch_vals) >= batch_size:
            created_ids = models.execute_kw(db, uid, password, 'res.partner', 'create', [batch_vals])
            logging.info(f"Batch de {len(batch_vals)} proveedores creado. IDs: {created_ids}")
            batch_vals = []

    except Exception as e:
        logging.error(f"Fila {index}: error al importar '{row}': {e}")
        fail_count += 1

# Crear registros restantes
if batch_vals:
    created_ids = models.execute_kw(db, uid, password, 'res.partner', 'create', [batch_vals])
    logging.info(f"Último batch de {len(batch_vals)} proveedores creado. IDs: {created_ids}")

csvfile.close()
elapsed_time = time.time() - start_time

print(f"✅ Importación BULK ULTRA de proveedores finalizada.")
print(f"Registros importados correctamente: {ok_count}")
print(f"Registros fallidos: {fail_count}")
print(f"⏱ Tiempo de ejecución: {elapsed_time:.2f} segundos")
print(f"📄 Revisa el archivo {log_file} para detalles.")
