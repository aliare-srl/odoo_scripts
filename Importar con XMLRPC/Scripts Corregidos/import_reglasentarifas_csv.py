import xmlrpc.client
import csv
import logging
import time
from http.client import RemoteDisconnected

# ---------------------------
# CONFIGURACIÓN
# ---------------------------
url = "http://localhost:8073"
db = "test"
username = "admin"
password = "admin"

csv_file = "lista_diferida.csv"
log_file = "import_log_pricelist_items.txt"
BATCH_SIZE = 200 # Aumentado a 200 para mayor velocidad
SLEEP_BETWEEN_BATCHES = 0.3 # Pequeño respiro, reducido un poco
PROGRESS_REPORT_INTERVAL = 1000 # Reportar progreso cada 1000 filas
# ---------------------------

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
# MAPAS PRECALCULADOS (Caché Rápido)
# ---------------------------
try:
    start_cache = time.time()
    
    # 1. Caché de Listas de Precios (Tarifas)
    pricelists = execute_kw("product.pricelist", "search_read", [[]], {"fields": ["id", "name"]})
    pricelist_map = {pl["name"].strip().upper(): pl["id"] for pl in pricelists}
    
    # 2. Caché de Productos (Plantillas)
    # Buscamos en 'product.template' (Plantilla) ya que applied_on="1_product" lo requiere.
    products = execute_kw("product.template", "search_read", [[]], {"fields": ["id", "barcode"]})
    # Mapeamos por barcode, si el barcode está en la plantilla
    product_map = {p["barcode"]: p["id"] for p in products if p.get("barcode")}
    
    logging.info(f"Caché cargado en {time.time() - start_cache:.2f} segundos.")
except Exception as e:
    logging.error(f"Error al cargar caché de Odoo: {e}")
    raise

# ---------------------------
# FUNCIONES AUXILIARES
# ---------------------------
def chunks_with_data(lst, n):
    """Genera chunks de tamaño n a partir de una lista."""
    for i in range(0, len(lst), n):
        yield i, lst[i:i + n]

# ---------------------------
# PROCESAMIENTO
# ---------------------------
all_vals_to_create = [] 
ok_count = 0
fail_count = 0

start_total = time.time()
print(f"\n[INICIO] Lectura del CSV iniciada. Reporte cada {PROGRESS_REPORT_INTERVAL} filas.")


try:
    with open(csv_file, newline='', encoding='utf-8', errors='replace') as csvfile:
        reader = csv.DictReader(csvfile)
        
        # 1. RECOLECCIÓN DE DATOS (El bucle más rápido posible)
        for index, row in enumerate(reader, start=1):
            
            # 🌟 Muestra de Progreso en Consola
            if index % PROGRESS_REPORT_INTERVAL == 0:
                elapsed = time.time() - start_total
                print(f"[PROGRESSO CSV] Fila: {index} | Recolectadas: {len(all_vals_to_create)} reglas | Tiempo: {elapsed:.2f}s")
            
            try:
                # Normalización y limpieza de datos
                pricelist_name = str(row.get("descripcion_lista") or "").strip().upper()
                barcode = str(row.get("cod_barra") or "").strip()
                price = row.get("precio_segun_lista")

                pricelist_id = pricelist_map.get(pricelist_name)
                # Obtenemos el ID de la plantilla
                product_tmpl_id = product_map.get(barcode)

                # Validaciones (usando el caché rápido)
                if not pricelist_id:
                    logging.warning(f"Fila {index}: Tarifa '{pricelist_name}' no encontrada.")
                    fail_count += 1
                    continue

                if not product_tmpl_id:
                    logging.warning(f"Fila {index}: Producto (Plantilla) con código de barra '{barcode}' no encontrado.")
                    fail_count += 1
                    continue

                if not price or not str(price).replace('.', '', 1).replace('-', '', 1).isdigit():
                    logging.warning(f"Fila {index}: Precio inválido '{price}'.")
                    fail_count += 1
                    continue
                
                # CREACIÓN DEL VALS
                vals = {
                    "pricelist_id": pricelist_id,
                    # 🌟 CAMPO CLAVE: Se aplica a la Plantilla de Producto
                    "applied_on": "1_product", 
                    "product_tmpl_id": product_tmpl_id, # Usamos product_tmpl_id
                    "compute_price": "fixed",
                    "fixed_price": float(price),
                }

                all_vals_to_create.append(vals)
                ok_count += 1

            except Exception as e:
                logging.error(f"Fila {index}: Error al procesar '{row}': {e}")
                fail_count += 1

    # 2. EJECUCIÓN BULK (Llamadas RPC agrupadas y espaciadas)
    logging.info(f"Iniciando creación BULK de {len(all_vals_to_create)} reglas en batches de {BATCH_SIZE}.")
    
    print(f"\n[INFO] Iniciando creación BULK de {len(all_vals_to_create)} reglas.")

    for start_index, batch_vals in chunks_with_data(all_vals_to_create, BATCH_SIZE):
        try:
            t0 = time.time()
            created_ids = execute_kw("product.pricelist.item", "create", [batch_vals])
            dt = time.time() - t0
            
            log_message = f"Batch CREADO [{start_index}..{start_index + len(batch_vals) - 1}] de {len(batch_vals)} reglas en {dt:.2f}s."
            logging.info(log_message)
            print(f"[BULK CREATE] {log_message}")
            
            # 🌟 Pausa para prevenir la sobrecarga del servidor
            time.sleep(SLEEP_BETWEEN_BATCHES) 
            
        except RemoteDisconnected:
             logging.error("Desconexión remota durante el bulk. Intenta reducir BATCH_SIZE o aumentar SLEEP_BETWEEN_BATCHES.")
             print("[ERROR] Desconexión remota. Revisa el servidor Odoo o la red.")
             break
        except Exception as e:
            logging.error(f"Error crítico al crear batch en índice {start_index}: {e}")
            print(f"[ERROR CRÍTICO] Falló el batch en el índice {start_index}. Revisar log.")
            break 

except Exception as e:
    logging.error(f"Error general en la lectura del archivo o proceso principal: {e}")

total_time = time.time() - start_total

print("\n" + "="*70)
print(f"✅ Importación de Reglas de Tarifa finalizada.")
print(f"Total filas procesadas: {ok_count + fail_count}, Correctas (enviadas a bulk): {ok_count}, Fallidas/Saltadas: {fail_count}")
print(f"Tiempo total de importación: {total_time:.2f} segundos")
print(f"Revisá el log para detalles: {log_file}")
print("="*70)