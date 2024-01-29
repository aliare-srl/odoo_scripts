Usar `sudo -H -u postgresql <comando> <parámetros>` cuando sea necesario
ejecutar un comando bajo el usuaro postgres Ej `sudo -H -u postgres mkdir /var/lib/postgresql/nuevo_directorio`
creará el *nuevo_directorio* como el usuario *postgres*
También puede ser útil cambiarse al usuario postgres con `sudo su - postgres`.

Las partes a personalizar de los comandos y parámetros se encierran entre <>. Reemplazarlos con el mismo valor cada vez que se encuentren estas variables.
Ejemplo: *ls /var/lib/postgresql/<version>*, si se tratara de la versión 12 se conviertiría a *ls /var/lib/postgresql/12*

# Replica en entre clústeres en un mismo servidor.

En cluster Master:
1. Crear usuario posgresql para la replicación:
    - `createuser <usuario_replicacion> --replication -c 1 -p <puerto>`
2. Editar postgresql.conf: `sudo -H -u postgres vim /etc/postgresql/<version>/main/postgresql.conf`
    - `wal_level = replica`
    - `wal_log_hints = on`
    - `max_wal_senders = 10`
    - `max_keep_segments = 64`
    - `archive_mode = on`
    - `archive_command = 'test ! -f /var/lib/postgresql/archivado_wal/main/%f && cp %p /var/lib/postgresql/archivado_wal/main/%f'`
    - `hot_standby = on`
    - `archive_timeout = 120 # para que el retraso sea de hasta 2 minutos`
    Nota : La configuración max_keep_segments se encuentra deprecated aparentemente desde 
    la versión 12 o 13 de postgresql. Es reemplazada por `wal_keep_size`. Donde el valor está en megabytes
    así que si se configura 64 en wal_keep_segments se debe colocar 64 * 16 = 1024en wal_keep_size.
    Si el servicio no llegara a iniciar por el parámetro wal_keep_segments, cambiaro por wal_keep_size.
3. Editar /var/lib/postgresql/<version>/main/pg_hba.conf:
    - `host replication <usuario_replicacion> <ip/24> trust` #Esto hay que investigar más, en este caso solo sirve para clusteres en el mismo servidor. NO DEBE USARSE EN PRODUCCION
4. Crear si es necesario un nuevo cluster. Tener en cuenta que se eliminarán los archivos de este cluster. OJO
   `pg_createcluster <version> <nombre_replica>`
5. Crear el subdirectorio para el archivado wal del cluster main y <nombre_replica>
   - `sudo -H -u postgres mkdirk /var/lib/postgresql/archivado_wal/main -p`
   - `sudo -H -u postgres mkdirk /var/lib/postgresql/archivado_wal/<nombre_replica> -p`
6. Eliminar los archivos del cluster replica:
    - sudo su - postgres
    - `rm /var/lib/postgresql/<version>/<nombre_replica> -r` (hacerlo en el secundario, borra los datos del cluster secundario OJO)
8. Copiar el cluster Master al cluster de Standby, se utiliza pg_basebackup como usuario postgres (ya se había ejecutado `sudo su - postgres`):
    - `pg_basebackup -D /var/lib/postgresql/<nombre_secundario> -U <usuario_replicacion> -w -P # -X`
    NOTA: El parámetro-X está comentado, es necesario para versiones de postgresql anteriores a la 10, ahora ya está predeterminado.
9. Modificar postgresql.conf del cluster standby:
   - Abrir con un editor de texto, ejemplo `nano /etc/postgresql/<version>/<nombre_replica>/postgresql.conf'
   - Modificar los siguientes parámetros:
     - wal_level = replica
     - wal_log_hints = on
     - archive_mode = on
     - archive_command = 'test ! -f /var/lib/postgresql/archivado_wal/<nombre_replica>/%f && cp %p /var/lib/postgresql/archivado_wal/<nombre_replica>/%f'
     - max_wal_senders = 10
     - wal_keep_segments = 64 # si da error, cambiar por `wal_keep_size = 1024`
     - hot_standby = on
     - primary_conninfo = 'user=<usuario_replicacion> passfile=''/var/lib/postgresql/.pgpass'' host=''/var/run/postgresql'' port=5432 sslmode=prefer sslcompression=1 krbsrvname=postgres target_session_attrs=any'
     - archive_cleanup_command = 'pg_archivecleanup /var/lib/postgresql/pg_log_archive/<nombre_replica> %r'

     Nota: primary_conninfo es el string de conexión que usara el cluster de standby para conectarse
           con el cluster master. Ajustarlo según sea necesario [conninfo](https://www.postgresql.org/docs/12/runtime-config-replication.html#GUC-PRIMARY-CONNINFO)
10. Crear un archivo vacío con el nombre standby.signal en el cluster <nombre_replica>:
    - touch /var/lib/postgresql/14/<nombre_replica>/standby.signal

11. Reiniciar el cluster master:
    - `sudo systemctl restart postgresql@<version>-main.service`
12. Iniciar el cluster de Standby:
    - `sudo systemctl start postgresql@<version>-<nombre_replica>.service`
