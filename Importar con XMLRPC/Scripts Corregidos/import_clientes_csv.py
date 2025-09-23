"""
Script BULK optimizado de importación de clientes a Odoo 15
Lee: clientes.csv
Genera log de errores: import_log_clientes.txt
Optimizado para mayor velocidad y validación de CUIT/DNI
"""

import xmlrpc.client
import csv
import logging
import re
import time
import requests
import json

# ---------------------------
# CONFIGURACIÓN
# ---------------------------
url = "http://localhost:8073"
db = "test"
username = "admin"
password = "admin"

csv_file = "clientes.csv"
log_file = "import_log_clientes.txt"
batch_size = 200   # tamaño de batch recomendado
use_jsonrpc = False  # True = usar JSON-RPC (más rápido), False = usar XML-RPC

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
if use_jsonrpc:
    def call_jsonrpc(service, method, args):
        payload = {
            "jsonrpc": "2.0",
            "method": "call",
            "params": {
                "service": service,
                "method": method,
                "args": args,
            },
            "id": 1,
        }
        headers = {"Content-Type": "application/json"}
        resp = requests.post(f"{url}/jsonrpc", headers=headers, data=json.dumps(payload)).json()
        if "error" in resp:
            raise Exception(resp["error"])
        return resp["result"]

    uid = call_jsonrpc("common", "authenticate", [db, username, password, {}])
else:
    common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
    uid = common.authenticate(db, username, password, {})
    models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")

if not uid:
    logging.error("Error de autenticación en Odoo.")
    raise Exception("No se pudo autenticar en Odoo")

# ---------------------------
# FUNCIÓN DE EJECUCIÓN SEGÚN PROTOCOLO
# ---------------------------
def execute_kw(model, method, args, kwargs=None):
    if use_jsonrpc:
        return call_jsonrpc("object", "execute_kw", [db, uid, password, model, method, args, kwargs or {}])
    else:
        return models.execute_kw(db, uid, password, model, method, args, kwargs or {})

# ---------------------------
# MAPAS PRECALCULADOS
# ---------------------------
# Tipos de identificación
id_types = execute_kw("l10n_latam.identification.type", "search_read", [[]], {"fields": ["id", "name"]})
id_type_map = {rec["name"].replace(" ", "").upper(): rec["id"] for rec in id_types}

# Responsabilidades AFIP
afip_types = execute_kw("l10n_ar.afip.responsibility.type", "search_read", [[]], {"fields": ["id", "name"]})
afip_map = {rec["name"].strip().upper(): rec["id"] for rec in afip_types}

# Clientes existentes (nombres y VAT en memoria)
existing_partners = execute_kw("res.partner", "search_read", [[]], {"fields": ["name", "vat"]})
existing_names = {p["name"].strip().upper() for p in existing_partners if p.get("name")}
existing_vats = {p["vat"] for p in existing_partners if p.get("vat")}

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

        # Tipo de identificación
        id_type_name = str(row.get("l10n_latam_identification_type_id/name") or "").strip().upper()
        id_type_id = id_type_map.get(id_type_name.replace(" ", "")) if id_type_name else None

        # VAT / Número de identificación
        vat = str(row.get("vat") or "").strip()
        vat = re.sub(r'\D', '', vat)  # solo números

        # Validar longitud según tipo
        if id_type_name.replace(" ", "") == "CUIT":
            if vat and len(vat) != 11:
                logging.warning(f"Fila {index}: CUIT inválido '{vat}', se omite VAT")
                vat = False
        elif id_type_name.replace(" ", "") == "DNI":
            if vat and len(vat) != 8:
                logging.warning(f"Fila {index}: DNI inválido '{vat}', se omite VAT")
                vat = False
        else:
            vat = False  # otros tipos no gestionados

        # AFIP responsabilidad
        afip_type_id = None
        if row.get("l10n_ar_afip_responsibility_type_id"):
            afip_name = str(row["l10n_ar_afip_responsibility_type_id"]).strip().upper()
            afip_type_id = afip_map.get(afip_name)

        if not name:
            logging.warning(f"Fila {index}: cliente vacío, saltado.")
            fail_count += 1
            continue

        # Validación duplicados en memoria
        if name.upper() in existing_names or (vat and vat in existing_vats):
            logging.info(f"Fila {index}: cliente '{name}' ya existe, no se crea.")
            continue

        # Preparar registro
        vals = {"name": name, "company_type": company_type}

        # customer_rank
        customer_rank = row.get("customer_rank")
        if customer_rank and customer_rank.strip().isdigit():
            vals["customer_rank"] = int(customer_rank)
        else:
            vals["customer_rank"] = 1

        # supplier_rank
        supplier_rank = row.get("supplier_rank")
        if supplier_rank and supplier_rank.strip().isdigit():
            vals["supplier_rank"] = int(supplier_rank)

        if vat:
            vals["vat"] = vat
        if street:
            vals["street"] = street
        if phone:
            vals["phone"] = phone
        if id_type_id:
            vals["l10n_latam_identification_type_id"] = id_type_id
        if afip_type_id:
            vals["l10n_ar_afip_responsibility_type_id"] = afip_type_id

        batch_vals.append(vals)
        ok_count += 1

        # Ejecutar batch
        if len(batch_vals) >= batch_size:
            created_ids = execute_kw("res.partner", "create", [batch_vals])
            logging.info(f"Batch de {len(batch_vals)} clientes creado. IDs: {created_ids}")
            batch_vals = []

    except Exception as e:
        logging.error(f"Fila {index}: error al importar '{row}': {e}")
        fail_count += 1

# Crear los últimos registros
if batch_vals:
    created_ids = execute_kw("res.partner", "create", [batch_vals])
    logging.info(f"Último batch de {len(batch_vals)} clientes creado. IDs: {created_ids}")

csvfile.close()
elapsed_time = time.time() - start_time

print(f"✅ Importación BULK optimizada de clientes finalizada.")
print(f"Registros importados correctamente: {ok_count}")
print(f"Registros fallidos: {fail_count}")
print(f"Tiempo de ejecución: {elapsed_time:.2f} segundos")
print(f"Revisa el archivo {log_file} para detalles.")
