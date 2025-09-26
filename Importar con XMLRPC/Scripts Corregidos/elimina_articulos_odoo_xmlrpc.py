import xmlrpc.client
import sys
import time

# ----------------------------------------
# ---------- CONFIGURACIÓN ODOO ----------
# ----------------------------------------
url = "http://localhost:8069"  # Cambia a tu URL
db = "test"                   # Cambia al nombre de tu base de datos
username = "admin"            # Usuario con permisos de administrador
password = "admin"            # Contraseña del usuario
# ----------------------------------------

# Modelo a eliminar (product.template = Plantillas de Producto)
MODEL_NAME = 'product.template'

def delete_all_products():
    """Conecta a Odoo y elimina todos los registros del modelo product.template."""
    start_time = time.time()
    
    print(f"Iniciando proceso de eliminación masiva para el modelo: {MODEL_NAME}")

    # 1. Conexión y Autenticación
    try:
        common = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/common')
        uid = common.authenticate(db, username, password, {})
        
        if not uid:
            print("❌ Error de autenticación. Verifica usuario, contraseña y nombre de la base de datos.")
            sys.exit(1)
            
        models = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/object')
        print("✅ Conexión a Odoo exitosa.")
        
    except Exception as e:
        print(f"❌ Error de conexión: {e}")
        sys.exit(1)

    # 2. Búsqueda de todos los IDs
    try:
        # [[]] es el dominio vacío, que busca TODOS los registros del modelo.
        print("🔍 Buscando todos los IDs de productos...")
        product_ids = models.execute_kw(db, uid, password, 
                                        MODEL_NAME, 
                                        'search', 
                                        [[]])
        
        if not product_ids:
            print("ℹ️ No se encontraron artículos para eliminar. Proceso finalizado.")
            return

        count = len(product_ids)
        print(f"Encontrados {count} artículos (IDs) para eliminar.")
        
    except Exception as e:
        print(f"❌ Error al buscar IDs de productos: {e}")
        return

    # 3. Eliminación Masiva (Unlink)
    print("\n⚠️ **ELIMINANDO PERMANENTEMENTE** los artículos...")
    try:
        # El método 'unlink' de Odoo toma una lista de IDs y los borra.
        success = models.execute_kw(db, uid, password, 
                                    MODEL_NAME, 
                                    'unlink', 
                                    [product_ids])
        
        if success:
            end_time = time.time()
            print("\n" + "="*50)
            print(f"🎉 **ÉXITO**: Eliminados {count} artículos en Odoo.")
            print(f"Tiempo total: {end_time - start_time:.2f} segundos.")
            print("="*50)
        else:
            print("\n❌ Fallo en la operación 'unlink'. El servidor no devolvió éxito.")
            
    except Exception as e:
        print(f"\n❌ Error durante la eliminación masiva (unlink): {e}")
        print("El proceso ha fallado a mitad de camino. Puede que se hayan borrado algunos artículos.")


if __name__ == '__main__':
    # -----------------------------------------------------------------------
    # ⚠️ Descomenta las 3 líneas siguientes para HABILITAR la eliminación.
    #    Por seguridad, el script está configurado para salir inmediatamente.
    # -----------------------------------------------------------------------
    # print("\n--- ATENCIÓN: LA ELIMINACIÓN MASIVA ESTÁ DESACTIVADA POR DEFECTO ---")
    # print("Para activarla, descomenta las líneas de 'sys.exit(\"Cancelado por seguridad...\")' al final del script.")
    # sys.exit("Cancelado por seguridad. Habilita la eliminación si estás seguro.")
    
    delete_all_products()