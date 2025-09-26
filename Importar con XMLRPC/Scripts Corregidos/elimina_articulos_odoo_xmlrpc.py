import xmlrpc.client
import sys
import time
import logging
from http.client import RemoteDisconnected

# ----------------------------------------
# ---------- CONFIGURACIÓN ODOO ----------
# ----------------------------------------
url = "http://localhost:8073"  # Cambia a tu URL
db = "test"  # Cambia al nombre de tu base de datos
username = "admin"  # Usuario con permisos de administrador
password = "admin"  # Contraseña del usuario

# Modelo a eliminar (product.template = Plantillas de Producto)
MODEL_NAME = 'product.template'

# 🛠️ AJUSTES DE OPTIMIZACIÓN
BATCH_SIZE = 500  # Número de IDs a eliminar por cada llamada 'unlink'
MAX_RETRIES = 3    # Máximo de reintentos por lote
# ----------------------------------------

# ---------------------------
# LOGGING (para errores y progreso detallado)
# ---------------------------
LOG_FILE = "delete_products_log.txt"
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# ---------------------------
# FUNCIONES AUXILIARES
# ---------------------------
def chunks_with_data(lst, n):
    """Genera chunks de tamaño n a partir de una lista, devolviendo el índice de inicio."""
    for i in range(0, len(lst), n):
        yield i, lst[i:i + n]

def delete_all_products():
    """Conecta a Odoo y elimina todos los registros del modelo product.template en lotes."""
    start_time = time.time()
    total_deleted = 0
    
    print(f"Iniciando eliminación masiva para: {MODEL_NAME} en lotes de {BATCH_SIZE}")

    # 1. Conexión y Autenticación
    try:
        common = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/common')
        uid = common.authenticate(db, username, password, {})
        
        if not uid:
            raise Exception("Autenticación fallida.")
            
        models = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/object')
        print("✅ Conexión a Odoo exitosa.")
        
    except Exception as e:
        print(f"❌ Error de conexión/autenticación: {e}")
        logging.error(f"Error de conexión/autenticación: {e}")
        sys.exit(1)

    # 2. Búsqueda de todos los IDs
    try:
        # Busca TODOS los IDs del modelo.
        print("🔍 Buscando todos los IDs de artículos...")
        product_ids = models.execute_kw(db, uid, password, MODEL_NAME, 'search', [[]])
        
        if not product_ids:
            print("ℹ️ No se encontraron artículos para eliminar. Proceso finalizado.")
            return

        count = len(product_ids)
        print(f"Encontrados {count} artículos (IDs) para eliminar.")
        
    except Exception as e:
        print(f"❌ Error al buscar IDs de artículos: {e}")
        logging.error(f"Error al buscar IDs de artículos: {e}")
        return

    # 3. Eliminación Masiva por Lotes (Bulk Unlink)
    print("\n⚠️ **INICIANDO ELIMINACIÓN PERMANENTE POR LOTES**...")
    
    for start_index, batch_ids in chunks_with_data(product_ids, BATCH_SIZE):
        batch_size = len(batch_ids)
        
        for attempt in range(MAX_RETRIES):
            try:
                t0 = time.time()
                # El método 'unlink' de Odoo toma la lista de IDs para el borrado
                success = models.execute_kw(db, uid, password, MODEL_NAME, 'unlink', [batch_ids])
                dt = time.time() - t0
                
                if success:
                    total_deleted += batch_size
                    log_message = f"Batch ELIMINADO [{start_index}..{start_index + batch_size - 1}] de {batch_size} IDs en {dt:.2f}s. Total eliminados: {total_deleted}"
                    logging.info(log_message)
                    print(f"[BULK UNLINK] {log_message}")
                    break # Lote exitoso, pasar al siguiente
                else:
                    raise Exception("El servidor no devolvió éxito en la eliminación.")
            
            except RemoteDisconnected:
                logging.error(f"Desconexión remota durante unlink (Intento {attempt + 1}/{MAX_RETRIES}).")
                if attempt == MAX_RETRIES - 1:
                    print(f"❌ Fallo persistente por Desconexión. Batch en índice {start_index} no eliminado.")
                    break # Batch fallido
                time.sleep(2 * (attempt + 1)) # Espera incremental antes del reintento
                continue

            except Exception as e:
                logging.error(f"Error crítico en unlink del batch {start_index}: {e}")
                print(f"\n❌ Error crítico en el batch {start_index}: {e}. Proceso detenido.")
                break # Batch fallido y grave, detener todo

        # Si el lote falló en todos los reintentos, detenemos el proceso general.
        if attempt == MAX_RETRIES - 1 and not success:
             break


    # 4. Informe Final
    end_time = time.time()
    print("\n" + "="*70)
    print(f"🏁 Eliminación de Artículos Finalizada.")
    print(f"Total artículos encontrados: {count}")
    print(f"Total artículos ELIMINADOS con éxito: {total_deleted}")
    print(f"Tiempo total: {end_time - start_time:.2f} segundos.")
    print(f"Revisá el log para errores: {LOG_FILE}")
    print("="*70)


if __name__ == '__main__':
    # -----------------------------------------------------------------------
    # ⚠️ Descomenta la siguiente línea para permitir la eliminación real.
    # -----------------------------------------------------------------------
    # sys.exit("Cancelado por seguridad. Descomenta la línea de 'sys.exit' si estás seguro.")
    
    delete_all_products()
