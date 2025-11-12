#!/usr/bin/env python3
import subprocess
import sys
import os
import time
import threading
import signal

# --- 🔧 CONFIGURACIÓN SIN PASSWORD ---
DB_NAME = "demo"                         # Nombre de tu BD Odoo
DB_HOST = "localhost"                    # Host de la BD
DB_PORT = "5432"                         # Puerto de PostgreSQL

# Rutas comunes del filestore de Odoo
FILESTORE_PATHS = [
    f"/var/lib/odoo/filestore/{DB_NAME}",
    f"/home/odoo/.local/share/Odoo/filestore/{DB_NAME}", 
    f"/opt/odoo/filestore/{DB_NAME}",
    f"/home/odoo/odoo/filestore/{DB_NAME}",
]

# --- ⚡ CONFIGURACIÓN OPTIMIZADA ---
BATCH_SIZE = 10000
MAX_BATCHES = 1000
SLEEP_BETWEEN_BATCHES = 0.1
STATS_INTERVAL = 10

# Variables globales para estadísticas
stats = {
    'total_eliminados': 0,
    'lotes_procesados': 0,
    'inicio_tiempo': 0,
    'ejecutando': True
}

def ejecutar_sql_como_postgres(comando_sql):
    """Ejecuta SQL como usuario postgres (sin password)"""
    try:
        comando = [
            'sudo', '-u', 'postgres',
            'psql', '-d', DB_NAME, '-t', '-A', '-c', comando_sql
        ]
        
        resultado = subprocess.run(comando, capture_output=True, text=True, check=True)
        return resultado.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"❌ Error ejecutando SQL: {e.stderr.strip()}")
        return None

def encontrar_filestore():
    """Encuentra la ruta del filestore"""
    print("🔍 Buscando filestore...")
    
    for path in FILESTORE_PATHS:
        if os.path.exists(path):
            print(f"   ✅ Filestore encontrado: {path}")
            return path
    
    # Búsqueda recursiva
    try:
        resultado = subprocess.run([
            'find', '/var/lib', '/home', '/opt', '-name', 'filestore', '-type', 'd'
        ], capture_output=True, text=True)
        
        if resultado.stdout:
            paths = resultado.stdout.strip().split('\n')
            for path in paths:
                if path and DB_NAME in path:
                    print(f"   ✅ Filestore encontrado: {path}")
                    return path
    except:
        pass
    
    print("   ❌ No se encontró el filestore")
    return None

def obtener_rutas_archivos_filestore():
    """Obtiene las rutas de los archivos en el filestore"""
    filestore_path = encontrar_filestore()
    if not filestore_path:
        return []
    
    print("📁 Obteniendo rutas de archivos en el filestore...")
    
    # Obtener los store_fname de la base de datos
    archivos_db = ejecutar_sql_como_postgres("""
        SELECT store_fname FROM ir_attachment 
        WHERE name ILIKE '%factur-x.xml%' 
        AND store_fname IS NOT NULL
    """)
    
    rutas_archivos = []
    if archivos_db:
        archivos = [fname.strip() for fname in archivos_db.split('\n') if fname.strip()]
        for archivo in archivos:
            ruta_completa = os.path.join(filestore_path, archivo)
            if os.path.exists(ruta_completa):
                rutas_archivos.append(ruta_completa)
        
        print(f"   📦 {len(rutas_archivos)} archivos encontrados en filestore")
    else:
        print("   ✅ No hay referencias a archivos en el filestore")
    
    return rutas_archivos

def eliminar_archivos_filestore():
    """Elimina los archivos físicos del filestore"""
    print("🗑️  Eliminando archivos del filestore...")
    
    rutas_archivos = obtener_rutas_archivos_filestore()
    if not rutas_archivos:
        print("   ✅ No hay archivos para eliminar del filestore")
        return 0
    
    eliminados = 0
    for i, ruta_archivo in enumerate(rutas_archivos, 1):
        try:
            os.remove(ruta_archivo)
            eliminados += 1
            if i % 100 == 0:
                print(f"   🔄 {i}/{len(rutas_archivos)} archivos eliminados...")
        except Exception as e:
            print(f"   ❌ Error eliminando {ruta_archivo}: {e}")
    
    print(f"   ✅ {eliminados} archivos eliminados del filestore")
    return eliminados

def preguntar_eliminacion_filestore():
    """Pregunta si eliminar archivos del filestore"""
    print(f"\n📁 ELIMINACIÓN DEL FILESTORE")
    print("=" * 50)
    print("¿Deseas eliminar también los archivos físicos del filestore?")
    print()
    print("📍 Los archivos se encuentran en:")
    filestore_path = encontrar_filestore()
    if filestore_path:
        print(f"   {filestore_path}")
    print()
    print("✅ RECOMENDADO: Libera espacio en disco")
    print("❌ PELIGROSO: No se puede deshacer")
    print()
    
    respuesta = input("   ¿Eliminar archivos del filestore? (s/N): ").strip().lower()
    
    if respuesta in ['s', 'si', 'y', 'yes']:
        return True
    else:
        print("   ⚠️  Eliminación del filestore omitida")
        return False

def mostrar_estadisticas():
    """Muestra estadísticas en tiempo real"""
    if stats['lotes_procesados'] == 0:
        return
    
    tiempo_transcurrido = time.time() - stats['inicio_tiempo']
    velocidad = stats['total_eliminados'] / tiempo_transcurrido if tiempo_transcurrido > 0 else 0
    
    print(f"   📊 {stats['total_eliminados']:,} eliminados | {velocidad:.1f} archivos/seg")

def hilo_estadisticas():
    """Hilo para mostrar estadísticas periódicamente"""
    while stats['ejecutando']:
        time.sleep(STATS_INTERVAL)
        if stats['ejecutando']:
            mostrar_estadisticas()

def preguntar_vacuum():
    """PREGUNTA si quiere ejecutar VACUUM"""
    print(f"\n🧹 VACUUM - RECUPERACIÓN DE ESPACIO")
    print("=" * 50)
    print("¿Deseas ejecutar VACUUM para recuperar espacio en disco?")
    print()
    print("✅ BENEFICIOS:")
    print("   • Libera espacio inmediatamente")
    print("   • Optimiza el rendimiento de la BD")
    print()
    
    respuesta = input("   ¿Ejecutar VACUUM? (s/N): ").strip().lower()
    
    if respuesta in ['s', 'si', 'y', 'yes']:
        return True
    else:
        print("   ⚠️  VACUUM omitido")
        return False

def ejecutar_vacuum_optimizado():
    """Ejecuta VACUUM optimizado"""
    print("🧹 Ejecutando VACUUM optimizado...")
    
    comandos_vacuum = [
        "VACUUM;",
        "VACUUM ir_attachment;", 
    ]
    
    for i, comando in enumerate(comandos_vacuum, 1):
        print(f"   {i}. Ejecutando...")
        resultado = ejecutar_sql_como_postgres(comando)
        if resultado is not None:
            print(f"      ✅ Completado")
        time.sleep(1)

def mostrar_espacio():
    """Muestra el espacio usado"""
    espacio = ejecutar_sql_como_postgres(f"""
        SELECT pg_size_pretty(pg_database_size('{DB_NAME}'));
    """)
    
    if espacio:
        print(f"   💾 Tamaño de la BD: {espacio}")

def diagnosticar_conexion():
    """Diagnostica la conexión a PostgreSQL"""
    print("🔍 DIAGNÓSTICO DE CONEXIÓN")
    print("-" * 40)
    
    # Verificar psql
    print("1. Verificando psql...")
    try:
        subprocess.run(["psql", "--version"], capture_output=True, check=True)
        print("   ✅ psql está instalado")
    except:
        print("   ❌ psql no está instalado")
        return False
    
    # Probar conexión
    print("2. Probando conexión a PostgreSQL...")
    version = ejecutar_sql_como_postgres("SELECT version();")
    if version:
        print("   ✅ Conexión exitosa como usuario postgres")
        return True
    else:
        print("   ❌ No se pudo conectar")
        return False

def listar_bases_datos():
    """Lista las bases de datos disponibles"""
    print("\n📊 Bases de datos disponibles:")
    
    try:
        resultado = subprocess.run([
            'sudo', '-u', 'postgres', 'psql',
            '-c', "SELECT datname FROM pg_database WHERE datistemplate = false ORDER BY datname;"
        ], capture_output=True, text=True, check=True)
        
        if resultado.stdout:
            lineas = [line.strip() for line in resultado.stdout.split('\n') if line.strip()]
            for linea in lineas:
                if linea and not linea.startswith('(') and linea not in ['datname', '----------']:
                    print(f"   📁 {linea}")
    except:
        print("   ❌ No se pudieron listar las bases de datos")

def obtener_total_archivos():
    """Obtiene el total de archivos factur-x.xml"""
    print("📊 Contando archivos factur-x.xml...")
    
    resultado = ejecutar_sql_como_postgres("""
        SELECT COUNT(*) FROM ir_attachment 
        WHERE name ILIKE '%factur-x.xml%'
    """)
    
    if resultado and resultado.isdigit():
        total = int(resultado)
        print(f"   📦 {total:,} archivos encontrados en BD")
        return total
    else:
        print("   ❌ No se pudieron contar los archivos")
        return 0

def eliminar_archivos_bd_optimizado(total_archivos):
    """Elimina archivos de forma optimizada de la BD"""
    print(f"🗑️  Eliminando {total_archivos:,} archivos de la BD...")
    
    # Iniciar estadísticas
    stats['inicio_tiempo'] = time.time()
    stats['ejecutando'] = True
    
    # Iniciar hilo de estadísticas
    hilo_stats = threading.Thread(target=hilo_estadisticas)
    hilo_stats.daemon = True
    hilo_stats.start()
    
    eliminados_total = 0
    lote_numero = 1
    
    try:
        while eliminados_total < total_archivos and lote_numero <= MAX_BATCHES:
            # DELETE optimizado
            resultado = ejecutar_sql_como_postgres(f"""
                DELETE FROM ir_attachment 
                WHERE id IN (
                    SELECT id FROM ir_attachment 
                    WHERE name ILIKE '%factur-x.xml%' 
                    LIMIT {BATCH_SIZE}
                )
            """)
            
            # Procesar resultado
            if resultado and "DELETE" in resultado:
                eliminados_en_lote = int(resultado.split()[1])
            else:
                eliminados_en_lote = 0
            
            if eliminados_en_lote == 0:
                break
            
            # Actualizar contadores
            eliminados_total += eliminados_en_lote
            stats['total_eliminados'] = eliminados_total
            stats['lotes_procesados'] = lote_numero
            
            progreso = (eliminados_total / total_archivos) * 100
            
            # Mostrar progreso
            if lote_numero % 10 == 0 or progreso % 10 < 1:
                tiempo_transcurrido = time.time() - stats['inicio_tiempo']
                velocidad = eliminados_total / tiempo_transcurrido
                eta = (total_archivos - eliminados_total) / velocidad if velocidad > 0 else 0
                
                print(f"   🔄 Lote {lote_numero}: {eliminados_en_lote:,} | "
                      f"Total: {eliminados_total:,}/{total_archivos:,} ({progreso:.1f}%) | "
                      f"ETA: {eta/60:.1f} min")
            
            lote_numero += 1
            time.sleep(SLEEP_BETWEEN_BATCHES)
        
        # Finalizar hilo
        stats['ejecutando'] = False
        time.sleep(1)
        
        print(f"   ✅ {eliminados_total:,} archivos eliminados de la BD")
        return eliminados_total
        
    except KeyboardInterrupt:
        print("\n   ⏹️  Interrumpido por el usuario")
        stats['ejecutando'] = False
        return eliminados_total

def manejar_señal(signum, frame):
    """Maneja la señal de interrupción"""
    print(f"\n⏹️  Interrumpiendo...")
    stats['ejecutando'] = False
    sys.exit(1)

def cambiar_base_datos():
    """Permite cambiar la base de datos"""
    global DB_NAME
    
    print(f"\n📍 Base de datos actual: {DB_NAME}")
    cambiar = input("   ¿Cambiar de base de datos? (s/N): ").strip().lower()
    
    if cambiar in ['s', 'si', 'y', 'yes']:
        nueva_bd = input("   📝 Nueva base de datos: ").strip()
        if nueva_bd:
            DB_NAME = nueva_bd
            print(f"   ✅ BD cambiada a: {DB_NAME}")
    
    return True

def main():
    # Configurar señales
    signal.signal(signal.SIGINT, manejar_señal)
    signal.signal(signal.SIGTERM, manejar_señal)
    
    print("🧹 LIMPIADOR COMPLETO DE FACTUR-X.XML")
    print("=" * 50)
    print("⚡ BASE DE DATOS + FILESTORE + VACUUM OPCIONAL")
    print("=" * 50)
    
    # Diagnosticar
    if not diagnosticar_conexion():
        return
    
    # Listar BD y permitir cambiar
    listar_bases_datos()
    cambiar_base_datos()
    
    # Obtener total
    total_archivos = obtener_total_archivos()
    
    if total_archivos == 0:
        print("✅ No hay archivos para eliminar.")
        return
    
    # Mostrar info
    if total_archivos > 10000:
        print(f"⚠️  VOLUMEN ALTO: {total_archivos:,} archivos")
    
    print(f"\n📊 RESUMEN:")
    print(f"   • BD: {DB_NAME}")
    print(f"   • Archivos en BD: {total_archivos:,}")
    
    confirmacion = input("\n⚠️  ¿Continuar con la eliminación? (escribe 'SI'): ")
    
    if confirmacion.strip().upper() != 'SI':
        print("❌ Cancelado.")
        return
    
    # Ejecutar eliminación de BD
    print(f"\n🚀 INICIANDO ELIMINACIÓN...")
    print("-" * 50)
    
    inicio = time.time()
    eliminados_bd = eliminar_archivos_bd_optimizado(total_archivos)
    fin_bd = time.time()
    
    tiempo_bd = fin_bd - inicio
    eliminados_filestore = 0
    vacuum_ejecutado = False
    
    if eliminados_bd > 0:
        # ✅ PREGUNTA por eliminación del filestore
        print("\n" + "=" * 50)
        eliminar_filestore = preguntar_eliminacion_filestore()
        
        if eliminar_filestore:
            eliminados_filestore = eliminar_archivos_filestore()
        
        # ✅ PREGUNTA por VACUUM
        print("\n" + "=" * 50)
        quiere_vacuum = preguntar_vacuum()
        
        if quiere_vacuum:
            ejecutar_vacuum_optimizado()
            vacuum_ejecutado = True
    
    tiempo_total = time.time() - inicio
    
    print(f"""
✅ PROCESO COMPLETADO
────────────────────
• Base de datos: {DB_NAME}
• Archivos BD: {eliminados_bd:,}
• Archivos filestore: {eliminados_filestore:,}
• Tiempo total: {tiempo_total/60:.1f} min
• VACUUM: {'✅' if vacuum_ejecutado else '❌'}
────────────────────
    """)

if __name__ == "__main__":
    main()
