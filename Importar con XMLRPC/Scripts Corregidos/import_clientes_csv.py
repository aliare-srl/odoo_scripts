import xmlrpc.client
import csv
import logging
import re
import time

# ---------------------------
# CONFIGURACIÓN
# ---------------------------
url = "http://localhost:8073"
db = "test"
username = "admin"
password = "admin"

csv_file = "clientes.csv"
log_file = "import_log_clientes.txt"
batch_size = 50

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

def execute_kw(model, method, args, kwargs=None):
    return models.execute_kw(db, uid, password, model, method, args, kwargs or {})

# ---------------------------
# FUNCIONES DE VALIDACIÓN
# ---------------------------
def validar_cuit(cuit):
    if not cuit or not cuit.isdigit():
        return False
    if len(cuit) == 11:  # CUIT
        mult = [5,4,3,2,7,6,5,4,3,2]
        suma = sum([int(cuit[i])*mult[i] for i in range(10)])
        dv = 11 - (suma % 11)
        if dv == 11: dv = 0
        if dv == 10: dv = 9
        return dv == int(cuit[10])
    elif len(cuit) == 8:  # DNI
        return True
    return False

def corregir_cuit(cuit):
    if not cuit or not cuit.isdigit():
        return None
    if len(cuit) == 11:
        mult = [5,4,3,2,7,6,5,4,3,2]
        suma = sum([int(cuit[i])*mult[i] for i in range(10)])
        dv = 11 - (suma % 11)
        if dv == 11: dv = 0
        if dv == 10: dv = 9
        return cuit[:10] + str(dv)
    elif len(cuit) == 8:
        return cuit
    return None

# ---------------------------
# MAPAS PRECALCULADOS
# ---------------------------
id_types = execute_kw("l10n_latam.identification.type", "search_read", [[]], {"fields": ["id", "name"]})
id_type_map = {rec["name"].replace(" ", "").upper(): rec["id"] for rec in id_types}

afip_types = execute_kw("l10n_ar.afip.responsibility.type", "search_read", [[]], {"fields": ["id", "name"]})
afip_map = {rec["name"].strip().upper(): rec["id"] for rec in afip_types}

existing_partners = execute_kw("res.partner", "search_read", [[]], {"fields": ["name", "vat"]})
existing_names = {p["name"].strip().upper() for p in existing_partners if p.get("name")}
existing_vats = {p["vat"] for p in existing_partners if p.get("vat")}

# ---------------------------
# LECTURA DEL CSV
# ---------------------------
csvfile = open(csv_file, newline='', encoding='utf-8', errors='replace')
reader = csv.DictReader(csvfile)

# ---------------------------
# IMPORTACIÓN BULK
# ---------------------------
batch_vals = []
ok_count = 0
fail_count = 0

start_total = time.time()  # inicio tiempo total

for index, row in enumerate(reader, start=1):
    start_batch = time.time()  # inicio tiempo fila
    try:
        name = str(row.get("name") or "").strip()
        street = str(row.get("street") or "").strip()
        phone = str(row.get("phone_mobile_search") or "").strip()
        company_type = str(row.get("company_type") or "company").strip()

        id_type_name = str(row.get("l10n_latam_identification_type_id/name") or "").strip().upper()
        id_type_id = id_type_map.get(id_type_name.replace(" ", "")) if id_type_name else None

        vat = re.sub(r'\D', '', str(row.get("vat") or ""))  # solo números

        # ---------------------------
        # Validar longitud según tipo
        # ---------------------------
        if vat and id_type_name:
            if (id_type_name == "DNI" and len(vat) != 8) or (id_type_name == "CUIT" and len(vat) != 11):
                logging.warning(f"Fila {index}: {id_type_name} inválido '{vat}', se omite VAT y l10n_latam_identification_type_id")
                vat = None
                id_type_id = None
            else:
                # Validar CUIT/DNI
                if not validar_cuit(vat):
                    vat_corregido = corregir_cuit(vat)
                    if vat_corregido and validar_cuit(vat_corregido):
                        vat = vat_corregido
                        logging.info(f"Fila {index}: CUIT/DNI corregido a {vat}")
                    else:
                        logging.warning(f"Fila {index}: {id_type_name} inválido '{vat}', se omite l10n_latam_identification_type_id")
                        id_type_id = None

        afip_type_id = None
        if row.get("l10n_ar_afip_responsibility_type_id"):
            afip_name = str(row["l10n_ar_afip_responsibility_type_id"]).strip().upper()
            afip_type_id = afip_map.get(afip_name)

        if not name:
            logging.warning(f"Fila {index}: cliente vacío, saltado.")
            fail_count += 1
            continue

        if name.upper() in existing_names or (vat and vat in existing_vats):
            logging.info(f"Fila {index}: cliente '{name}' ya existe, no se crea.")
            continue

        vals = {"name": name, "company_type": company_type}

        customer_rank = row.get("customer_rank")
        vals["customer_rank"] = int(customer_rank) if customer_rank and customer_rank.strip().isdigit() else 1

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

        if len(batch_vals) >= batch_size:
            try:
                created_ids = execute_kw("res.partner", "create", [batch_vals])
                batch_time = time.time() - start_batch
                logging.info(f"Batch de {len(batch_vals)} clientes creado en {batch_time:.2f} s. IDs: {created_ids}")
            except Exception as e:
                logging.error(f"Error al crear batch en fila {index}: {e}")
            batch_vals = []
            time.sleep(1)

    except Exception as e:
        logging.error(f"Fila {index}: error al importar '{row}': {e}")
        fail_count += 1

if batch_vals:
    try:
        created_ids = execute_kw("res.partner", "create", [batch_vals])
        batch_time = time.time() - start_batch
        logging.info(f"Último batch de {len(batch_vals)} clientes creado en {batch_time:.2f} s. IDs: {created_ids}")
    except Exception as e:
        logging.error(f"Error al crear último batch: {e}")

csvfile.close()
total_time = time.time() - start_total

print(f"✅ Importación finalizada. Correctos: {ok_count}, Fallidos: {fail_count}")
print(f"Tiempo total de importación: {total_time:.2f} segundos")
print(f"Revisá el log: {log_file}")
