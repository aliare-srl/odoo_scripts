#!/usr/bin/env python3
import subprocess
import sys
import os
import time
import threading
import signal

# --- 🔧 CONFIGURACIÓN SIN PASSWORD ---
DB_NAME = "demo"                         # Nombre de tu BD Odoo
DB_USER = "odoo"                         # Usuario de la BD 
DB_HOST = "localhost"                    # Host de la BD
DB_PORT = "5432"                         # Puerto de PostgreSQL

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

def ejecutar_sql_sin_password(comando_sql):
    """Ejecuta SQL sin password usando diferentes métodos"""
    métodos = [
        # Método 1: Conectar directamente (si los permisos lo permiten)
        lambda: subprocess.run([
            'psql', '-h', DB_HOST, '-p', DB_PORT, '-U', DB_USER, '-d', DB_NAME,
            '-t', '-A', '-c', comando_sql
        ], capture_output=True, text=True, check=True),
        
        # Método 2: Usar sudo -u postgres
        lambda: subprocess.run([
            'sudo', '-u', 'postgres', 'psql', '-d', DB_NAME,
            '-t', '-A', '-c', comando_sql
        ], capture_output=True, text=True, check=True),
        
        # Método 3: Conectar como postgres directamente
        lambda: subprocess.run([
            'psql', '-h', DB_HOST, '-p', DB_PORT, '-U', 'postgres', '-d', DB_NAME,
            '-t', '-A', '-c', comando_sql
        ], capture_output=True, text=True, check=True),
    ]
    
    for i, método in enumerate(métodos):
        try:
            resultado = método()
            if i > 0:  # Si no fue el primer método, mostrar cuál funcionó
                métodos_nombres = ["directo", "sudo postgres", "usuario postgres"]
                print(f"   🔑 Conectado usando: {métodos_nombres[i]}")
            return resultado.stdout.strip()
        except subprocess.CalledProcessError as e:
            if i == len(métodos) - 1:  # Último método falló
                print(f"❌ Todos los métodos de conexión fallaron")
                print(f"   Error: {e.stderr.strip()}")
            continue
        except FileNotFoundError:
            print("❌ El comando 'psql' no está instalado.")
            print("   💡 Instálalo con: sudo apt install postgresql-client")
            return None
    
    return None

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

def preguntar_y_ejecutar_vacuum():
    """PREGUNTA antes de ejecutar VACUUM"""
    print(f"\n🧹 VACUUM - RECUPERACIÓN DE ESPACIO")
    print("-" * 40)
    print("El VACUUM recupera espacio en disco y optimiza la BD")
    print("¿Deseas ejecutar VACUUM ahora?")
    print("   • ✅ RECOMENDADO: Libera espacio inmediatamente")
    print("   • ⏰ Duración: 1-3 minutos")
    print("   • 🔒 NO BLOQUEANTE: No afecta operaciones")
    
    respuesta = input("\n   ¿Ejecutar VACUUM? (s/N): ").strip().lower()
    
    if respuesta in ['s', 'si', 'y', 'yes']:
        ejecutar_vacuum_optimizado()
        return True
    else:
        print("   ⚠️  VACUUM omitido")
        print("   💡 Puedes ejecutarlo después con:")
        print("      VACUUM; VACUUM ir_attachment; ANALYZE ir_attachment;")
        return False

def ejecutar_vacuum_optimizado():
    """Ejecuta VACUUM optimizado"""
    print("🧹 Ejecutando VACUUM optimizado...")
    
    comandos_vacuum = [
        "VACUUM;",
        "VACUUM ir_attachment;", 
        "ANALYZE ir_attachment;"
    ]
    
    nombres_vacuum = [
        "VACUUM básico (rápido)",
        "VACUUM en tabla ir_attachment", 
        "ANALYZE para estadísticas"
    ]
    
    for i, (comando, nombre) in enumerate(zip(comandos_vacuum, nombres_vacuum), 1):
        print(f"   {i}. {nombre}...")
        resultado = ejecutar_sql_sin_password(comando)
        if resultado is not None:
            print(f"      ✅ Completado")
        else:
            print(f"      ⚠️  Error")
        time.sleep(1)

def mostrar_espacio():
    """Muestra el espacio usado"""
    espacio = ejecutar_sql_sin_password(f"""
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
    
    # Verificar servicio PostgreSQL
    print("2. Verificando servicio PostgreSQL...")
    try:
        servicio = subprocess.run(["systemctl", "is-active", "postgresql"], capture_output=True, text=True)
        if servicio.stdout.strip() == "active":
            print("   ✅ Servicio PostgreSQL activo")
        else:
            print(f"   ⚠️  Servicio: {servicio.stdout.strip()}")
    except:
        print("   ⚠️  No se pudo verificar el servicio")
    
    # Probar conexión
    print("3. Probando conexión a PostgreSQL...")
    version = ejecutar_sql_sin_password("SELECT version();")
    if version:
        print("   ✅ Conexión exitosa")
        print(f"   ℹ️  {version.split(chr(10))[0]}")
        return True
    else:
        print("   ❌ No se pudo conectar")
        return False

def listar_bases_datos():
    """Lista las bases de datos disponibles"""
    print("\n📊 Bases de datos disponibles:")
    
    resultado = ejecutar_sql_sin_password("SELECT datname FROM pg_database WHERE datistemplate = false ORDER BY datname;")
    
    if resultado:
        bases = [bd.strip() for bd in resultado.split('\n') if bd.strip()]
        for bd in bases:
            if bd not in ['postgres', 'template0', 'template1']:
                print(f"   📁 {bd}")
        return bases
    else:
        print("   ❌ No se pudieron listar las bases de datos")
        return []

def obtener_total_archivos():
    """Obtiene el total de archivos factur-x.xml"""
    print("📊 Contando archivos factur-x.xml...")
    
    resultado = ejecutar_sql_sin_password("""
        SELECT COUNT(*) FROM ir_attachment 
        WHERE name ILIKE '%factur-x.xml%'
    """)
    
    if resultado and resultado.isdigit():
        total = int(resultado)
        print(f"   📦 {total:,} archivos encontrados")
        return total
    else:
        print("   ❌ No se pudieron contar los archivos")
        return 0

def eliminar_archivos_optimizado(total_archivos):
    """Elimina archivos de forma optimizada"""
    print(f"🗑️  Iniciando eliminación de {total_archivos:,} archivos...")
    print(f"   ⚡ Lotes de {BATCH_SIZE:,} | Pausa: {SLEEP_BETWEEN_BATCHES}s")
    
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
            resultado = ejecutar_sql_sin_password(f"""
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
        
        print(f"   ✅ Eliminados {eliminados_total:,} archivos")
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
        bases = listar_bases_datos()
        if bases:
            nueva_bd = input("   📝 Nueva base de datos: ").strip()
            if nueva_bd in bases or nueva_bd == "":
                if nueva_bd:
                    DB_NAME = nueva_bd
                    print(f"   ✅ BD cambiada a: {DB_NAME}")
            else:
                print("   ❌ Base de datos no válida")
    
    return True

def main():
    # Configurar señales
    signal.signal(signal.SIGINT, manejar_señal)
    signal.signal(signal.SIGTERM, manejar_señal)
    
    print("🧹 LIMPIADOR DE FACTUR-X.XML")
    print("=" * 50)
    print("⚡ SIN PASSWORD | CON VACUUM OPCIONAL")
    print("=" * 50)
    
    # Diagnosticar
    if not diagnosticar_conexion():
        print("\n💡 SOLUCIONES:")
        print("1. sudo apt install postgresql-client")
        print("2. sudo systemctl start postgresql")
        print("3. Verificar usuario: sudo -u postgres psql -c '\\du'")
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
    print(f"   • Archivos: {total_archivos:,}")
    print(f"   • Tiempo estimado: ~{total_archivos/5000:.1f} min")
    
    confirmacion = input("\n⚠️  ¿Continuar con la eliminación? (escribe 'SI'): ")
    
    if confirmacion.strip().upper() != 'SI':
        print("❌ Cancelado.")
        return
    
    # Ejecutar eliminación
    print(f"\n🚀 INICIANDO ELIMINACIÓN...")
    print("   Ctrl+C para interrumpir")
    print("-" * 50)
    
    inicio = time.time()
    eliminados = eliminar_archivos_optimizado(total_archivos)
    fin = time.time()
    
    # Mostrar espacio después de eliminar
    if eliminados > 0:
        print("\n📊 ESPACIO DESPUÉS DE ELIMINACIÓN:")
        mostrar_espacio()
        
        # ✅ AHORA PREGUNTA ANTES DE VACUUM
        vacuum_ejecutado = preguntar_y_ejecutar_vacuum()
        
        # Mostrar espacio final si se ejecutó VACUUM
        if vacuum_ejecutado:
            print("\n📊 ESPACIO FINAL (CON VACUUM):")
            mostrar_espacio()
    
    tiempo_total = fin - inicio
    
    print(f"""
✅ COMPLETADO
────────────────────
• BD: {DB_NAME}
• Eliminados: {eliminados:,}
• Tiempo: {tiempo_total/60:.1f} min
• Velocidad: {eliminados/tiempo_total:.1f}/s
• VACUUM: {'✅' if vacuum_ejecutado else '❌'}
────────────────────
    """)

if __name__ == "__main__":
    main()
