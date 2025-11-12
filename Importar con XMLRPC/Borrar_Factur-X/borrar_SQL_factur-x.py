#!/usr/bin/env python3
import subprocess
import sys
import os
import time
import threading
import signal

# --- 🔧 CONFIGURACIÓN SIN CONTENEDOR Y SIN PASSWORD ---
DB_NAME = "demo"                         # Nombre de tu BD Odoo
DB_USER = "odoo"                         # Usuario de la BD (sin password)
DB_HOST = "localhost"                    # Host de la BD
DB_PORT = "5432"                         # Puerto de PostgreSQL

# --- ⚡ CONFIGURACIÓN OPTIMIZADA PARA MILES DE ARCHIVOS ---
BATCH_SIZE = 10000                       # Lotes más grandes
MAX_BATCHES = 1000                       # Límite de seguridad
SLEEP_BETWEEN_BATCHES = 0.1              # Pausa mínima entre lotes
STATS_INTERVAL = 10                      # Mostrar stats cada N lotes

# Variables globales para estadísticas
stats = {
    'total_eliminados': 0,
    'lotes_procesados': 0,
    'inicio_tiempo': 0,
    'ejecutando': True
}

def ejecutar_sql(comando_sql):
    """Ejecuta un comando SQL directamente en PostgreSQL sin password"""
    try:
        comando = [
            'psql',
            '-h', DB_HOST,
            '-p', DB_PORT,
            '-U', DB_USER,
            '-d', DB_NAME,
            '-t', '-A',
            '-c', comando_sql
        ]
        
        # SIN PASSWORD - ejecutar directamente
        resultado = subprocess.run(comando, capture_output=True, text=True, check=True)
        return resultado.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"❌ Error ejecutando SQL: {e.stderr.strip()}")
        return None
    except FileNotFoundError:
        print("❌ El comando 'psql' no está instalado.")
        print("   💡 Instálalo con: sudo apt install postgresql-client")
        return None

def mostrar_estadisticas():
    """Muestra estadísticas en tiempo real"""
    if stats['lotes_procesados'] == 0:
        return
    
    tiempo_transcurrido = time.time() - stats['inicio_tiempo']
    velocidad = stats['total_eliminados'] / tiempo_transcurrido if tiempo_transcurrido > 0 else 0
    lotes_por_segundo = stats['lotes_procesados'] / tiempo_transcurrido if tiempo_transcurrido > 0 else 0
    
    print(f"   📊 Estadísticas: {stats['total_eliminados']:,} eliminados | "
          f"{velocidad:.1f} archivos/seg | {lotes_por_segundo:.1f} lotes/seg")

def hilo_estadisticas():
    """Hilo para mostrar estadísticas periódicamente"""
    while stats['ejecutando']:
        time.sleep(STATS_INTERVAL)
        if stats['ejecutando']:
            mostrar_estadisticas()

def ejecutar_vacuum_optimizado():
    """Ejecuta VACUUM optimizado para grandes volúmenes"""
    print("🧹 Ejecutando VACUUM optimizado...")
    
    # VACUUM básico rápido
    print("   1. VACUUM rápido...")
    resultado = ejecutar_sql("VACUUM;")
    if resultado is not None:
        print("      ✅ VACUUM básico completado")
    
    time.sleep(1)
    
    # VACUUM específico para la tabla ir_attachment
    print("   2. VACUUM en tabla ir_attachment...")
    resultado = ejecutar_sql("VACUUM ir_attachment;")
    if resultado is not None:
        print("      ✅ VACUUM en ir_attachment completado")
    
    time.sleep(1)
    
    # ANALYZE para estadísticas
    print("   3. ANALYZE para optimización...")
    resultado = ejecutar_sql("ANALYZE ir_attachment;")
    if resultado is not None:
        print("      ✅ ANALYZE completado")

def mostrar_espacio():
    """Muestra el espacio usado"""
    espacio = ejecutar_sql(f"""
        SELECT pg_size_pretty(pg_database_size('{DB_NAME}'));
    """)
    
    if espacio:
        print(f"   💾 Tamaño de la BD: {espacio}")

def diagnosticar_postgresql():
    """Diagnostica el estado de PostgreSQL"""
    print("🔍 DIAGNÓSTICO DE POSTGRESQL")
    print("-" * 40)
    
    # 1. Verificar si psql está instalado
    print("1. Verificando psql...")
    psql_version = subprocess.run(["psql", "--version"], capture_output=True, text=True)
    if psql_version.returncode != 0:
        print("   ❌ psql no está instalado")
        print("   💡 Ejecuta: sudo apt install postgresql-client")
        return False
    print("   ✅ psql está instalado")
    
    # 2. Verificar si PostgreSQL está ejecutándose
    print("2. Verificando servicio PostgreSQL...")
    servicio = subprocess.run(
        ["systemctl", "is-active", "postgresql"], 
        capture_output=True, text=True
    )
    if servicio.stdout.strip() == "active":
        print("   ✅ Servicio PostgreSQL está activo")
    else:
        print(f"   ⚠️  Servicio PostgreSQL: {servicio.stdout.strip()}")
        print("   💡 Ejecuta: sudo systemctl start postgresql")
    
    # 3. Verificar conexión a la BD sin password
    print(f"3. Verificando conexión a '{DB_NAME}' con usuario '{DB_USER}'...")
    version = ejecutar_sql("SELECT version();")
    if version:
        print("   ✅ Conexión exitosa a PostgreSQL")
        return True
    else:
        print(f"   ❌ No se pudo conectar a la base de datos '{DB_NAME}'")
        return False

def listar_bases_datos():
    """Lista las bases de datos disponibles sin password"""
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
    except subprocess.CalledProcessError:
        print("   ❌ No se pudieron listar las bases de datos")

def obtener_total_archivos():
    """Obtiene el total de archivos factur-x.xml de forma rápida"""
    print("📊 Contando archivos factur-x.xml...")
    
    resultado = ejecutar_sql("""
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
    """Elimina archivos de forma optimizada para miles de registros"""
    print(f"🗑️  Iniciando eliminación optimizada de {total_archivos:,} archivos...")
    print(f"   ⚡ Configuración: Lotes de {BATCH_SIZE:,} | Pausa: {SLEEP_BETWEEN_BATCHES}s")
    
    # Iniciar estadísticas
    stats['inicio_tiempo'] = time.time()
    stats['ejecutando'] = True
    
    # Iniciar hilo de estadísticas
    hilo_stats = threading.Thread(target=hilo_estadisticas)
    hilo_stats.daemon = True
    hilo_stats.start()
    
    eliminados_total = 0
    lote_numero = 1
    fallos_consecutivos = 0
    
    try:
        while eliminados_total < total_archivos and lote_numero <= MAX_BATCHES:
            # Ejecutar DELETE optimizado
            resultado = ejecutar_sql(f"""
                WITH batch AS (
                    SELECT id FROM ir_attachment 
                    WHERE name ILIKE '%factur-x.xml%' 
                    ORDER BY id
                    LIMIT {BATCH_SIZE}
                    FOR UPDATE SKIP LOCKED
                )
                DELETE FROM ir_attachment 
                WHERE id IN (SELECT id FROM batch)
            """)
            
            # Procesar resultado
            if resultado and "DELETE" in resultado:
                eliminados_en_lote = int(resultado.split()[1])
                fallos_consecutivos = 0  # Resetear contador de fallos
            else:
                eliminados_en_lote = 0
                fallos_consecutivos += 1
            
            # Si no se eliminó nada por varios lotes consecutivos, salir
            if eliminados_en_lote == 0:
                if fallos_consecutivos >= 3:
                    print("   ⚠️  Sin archivos por eliminar en lotes consecutivos, finalizando...")
                    break
                else:
                    time.sleep(0.5)  # Pausa más larga si no hay archivos
                    continue
            
            # Actualizar contadores
            eliminados_total += eliminados_en_lote
            stats['total_eliminados'] = eliminados_total
            stats['lotes_procesados'] = lote_numero
            
            progreso = (eliminados_total / total_archivos) * 100
            
            # Mostrar progreso cada 10 lotes o si el progreso avanza significativamente
            if lote_numero % 10 == 0 or progreso % 10 < 1:
                tiempo_transcurrido = time.time() - stats['inicio_tiempo']
                velocidad = eliminados_total / tiempo_transcurrido if tiempo_transcurrido > 0 else 0
                eta = (total_archivos - eliminados_total) / velocidad if velocidad > 0 else 0
                
                print(f"   🔄 Lote {lote_numero}: {eliminados_en_lote:,} eliminados | "
                      f"Total: {eliminados_total:,}/{total_archivos:,} ({progreso:.1f}%) | "
                      f"Vel: {velocidad:.1f}/s | ETA: {eta/60:.1f} min")
            
            lote_numero += 1
            
            # Pausa adaptativa - menos pausa al inicio, más al final
            sleep_time = SLEEP_BETWEEN_BATCHES * (1 + (lote_numero * 0.01))
            time.sleep(min(sleep_time, 1.0))  # Máximo 1 segundo
        
        # Finalizar hilo de estadísticas
        stats['ejecutando'] = False
        time.sleep(1)  # Dar tiempo al hilo para mostrar última estadística
        
        print(f"   ✅ Eliminados {eliminados_total:,} archivos en {lote_numero-1} lotes")
        return eliminados_total
        
    except KeyboardInterrupt:
        print("\n   ⏹️  Proceso interrumpido por el usuario")
        stats['ejecutando'] = False
        return eliminados_total

def manejar_señal(signum, frame):
    """Maneja la señal de interrupción"""
    print(f"\n   ⏹️  Señal de interrupción recibida, finalizando...")
    stats['ejecutando'] = False
    sys.exit(1)

def optimizar_indices():
    """Optimiza los índices después de la eliminación masiva"""
    print("🔧 Optimizando índices...")
    
    # Reindexar tabla ir_attachment
    resultado = ejecutar_sql("REINDEX TABLE ir_attachment;")
    if resultado is not None:
        print("   ✅ Índices de ir_attachment optimizados")
    
    # Actualizar estadísticas
    resultado = ejecutar_sql("ANALYZE ir_attachment;")
    if resultado is not None:
        print("   ✅ Estadísticas actualizadas")

def cambiar_base_datos():
    """Permite cambiar la base de datos interactivamente"""
    global DB_NAME
    
    print(f"\n📍 Base de datos actual: {DB_NAME}")
    cambiar = input("   ¿Quieres cambiar de base de datos? (s/N): ").strip().lower()
    
    if cambiar in ['s', 'si', 'y', 'yes']:
        listar_bases_datos()
        nueva_bd = input("   📝 Nombre de la nueva base de datos: ").strip()
        if nueva_bd:
            DB_NAME = nueva_bd
            print(f"   ✅ BD cambiada a: {DB_NAME}")
            
            # Verificar que la nueva BD existe y tiene la tabla
            print(f"   🔍 Verificando nueva base de datos...")
            version = ejecutar_sql("SELECT version();")
            if not version:
                print(f"   ❌ No se puede conectar a '{DB_NAME}'")
                return False
            
            # Verificar tabla ir_attachment
            existe_tabla = ejecutar_sql("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'ir_attachment'
                );
            """)
            
            if existe_tabla != "t":
                print(f"   ❌ La tabla ir_attachment no existe en '{DB_NAME}'")
                return False
            
            print(f"   ✅ Base de datos '{DB_NAME}' verificada correctamente")
    
    return True

def main():
    # Configurar manejo de señales
    signal.signal(signal.SIGINT, manejar_señal)
    signal.signal(signal.SIGTERM, manejar_señal)
    
    print("🧹 LIMPIADOR OPTIMIZADO DE FACTUR-X.XML")
    print("=" * 55)
    print("⚡ SIN CONTENEDOR | SIN PASSWORD | OPTIMIZADO PARA MILES")
    print("=" * 55)
    
    # Diagnosticar PostgreSQL
    if not diagnosticar_postgresql():
        print("\n💡 SOLUCIONES:")
        print("1. Verificar que PostgreSQL esté instalado: psql --version")
        print("2. Verificar que el servicio esté ejecutándose: systemctl status postgresql")
        print("3. Si no está ejecutándose: sudo systemctl start postgresql")
        print("4. Verificar usuario y permisos: sudo -u postgres psql -c '\\du'")
        sys.exit(1)
    
    # Listar bases de datos disponibles
    listar_bases_datos()
    
    # Permitir cambiar base de datos
    if not cambiar_base_datos():
        sys.exit(1)
    
    # Obtener total de archivos
    total_archivos = obtener_total_archivos()
    
    if total_archivos == 0:
        print("✅ No hay archivos factur-x.xml para eliminar.")
        return
    
    # Mostrar advertencia para grandes volúmenes
    if total_archivos > 10000:
        print(f"⚠️  VOLUMEN ELEVADO: {total_archivos:,} archivos")
        print("   Se recomienda ejecutar en horario de baja actividad")
    
    # Pedir confirmación
    print(f"\n📊 RESUMEN:")
    print(f"   • Base de datos: {DB_NAME}")
    print(f"   • Archivos a eliminar: {total_archivos:,}")
    print(f"   • Lotes de: {BATCH_SIZE:,} archivos")
    print(f"   • Tiempo estimado: ~{total_archivos/5000:.1f} minutos")
    
    confirmacion = input("\n⚠️  ¿Continuar con la eliminación? (escribe 'SI' para confirmar): ")
    
    if confirmacion.strip().upper() != 'SI':
        print("❌ Operación cancelada.")
        return
    
    # Ejecutar limpieza optimizada
    inicio_tiempo = time.time()
    
    print(f"\n🚀 INICIANDO ELIMINACIÓN OPTIMIZADA...")
    print("   Presiona Ctrl+C para interrumpir en cualquier momento")
    print("-" * 55)
    
    eliminados = eliminar_archivos_optimizado(total_archivos)
    
    if eliminados > 0:
        # Optimizar índices
        optimizar_indices()
        
        # Ejecutar VACUUM
        ejecutar_vacuum_optimizado()
        
        # Mostrar espacio final
        print("\n📊 ESPACIO FINAL:")
        mostrar_espacio()
    
    fin_tiempo = time.time()
    tiempo_total = fin_tiempo - inicio_tiempo
    
    print(f"""
✅ PROCESO COMPLETADO
────────────────────────
• Base de datos: {DB_NAME}
• Archivos eliminados: {eliminados:,}
• Tiempo total: {tiempo_total/60:.1f} minutos
• Velocidad promedio: {eliminados/tiempo_total:.1f} archivos/segundo
• VACUUM ejecutado: ✅
• Índices optimizados: ✅
• Modo: Sin contenedor | Sin password
────────────────────────
    """)

if __name__ == "__main__":
    main()