# Replicación de una instancia de Odoo a un servidor de respaldo.

Una instancia de Odoo se compone de 
1. La base de datos
2. El filestore
Esto significa que para replicar una instancia de Odoo debemos trasladar tanto la BD como el filestore a un servidor secundario. Con ambas copias es posible recrear la instancia original en caso de catástrofe.

Utilizar el mismo “nombre” tanto para el clúster de posgresql como para la carpeta donde se replicarán los archivos de odoo. Por ejemplo vps_clientes_1

## Replicación de la BD.

Una instancia o cluster de Postgresql contiene todas y cada una de las bases de datos creadas dentro de la misma. En nuestro caso tenemos varios clientes utilizando el mismo cluster de Postgresql, cada uno con su propia base de datos.

Debemos entonces replicar el clúster principal o Main a un servidor o clúster secundario o de stand-by.

### Configuración Clúster Principal para permitir la replicación:

Como usuario postgres editar los siguientes archivos ubicados en /etc/postgresql/12/main/:

postgresql.conf:
```txt
listen_addresses = ‘*’
wal_level = replica
full_page_writes = on
wal_log_hints = on
hot_standby = on        
```
pg_hba.conf:
```txt
# Usuarios para la replicación y para pg_rewind
# type        database        user        address        method
host        replication        replica_user        0.0.0.0/0        md5
hostssl replication        replica_user        0.0.0.0/0        md5
host        all        replica_rewind                0.0.0.0/0        md5
hostssl all        replica_rewind                0.0.0.0/0        md5
```

Crear los usuarios *replica_user* y *replica_rewind* con sus respectivos passwords en el cluster principal utilizando psql ejecutandolo como el usuario postgres:
```bash
admin@vps1:~$ sudo -u postgres – psql
```
```sql
CREATE USER replica_user WITH REPLICATION PASSWORD ‘st0ngpa$$word’;
CREATE USER replica_rewind WITH PASSWORD ‘st0ngpa$$word2’;
GRANT EXECUTE on FUNCTION pg_catalog.pg_ls_dir(text, boolean, boolean) to replica_rewind;
GRANT EXECUTE on FUNCTION pg_catalog.pg_stat_file(text, boolean) to replica_rewind;
GRANT EXECUTE on FUNCTION pg_catalog.pg_read_binary_file (text) to replica_rewind ;
GRANT EXECUTE ON FUNCTION pg_catalog.pg_read_binary_file (text, bigint, bigint, boolean) to replica_rewind ;
```
Salir de psql con el comando \q y reiniciar el servicio de postgresql:
```bash
admin@vps1:~$ sudo systemctl restart postgresql@12-main.service
```
El usuario *replica_user* será utilizado para para la replicación propiamente dicha, mientras que el usuario *replica_rewind* será utilizado para el backup inicial y el fail over llegado el caso.
El puerto de postgresql debe ser accesible desde Internet. Verificar que esto sea así.

### Configuración del Server secundario:

Dentro del home del usuario postgres, debe existir el archivo `~/.pgpass. Debe perteneces al usuario postgres y tener permisos 0600. 
De no existir, crearlo y establecer los permisos correctos:
```bash
postgres@respaldo:~$ touch .pgpass
postgres@respaldo:~$ chmod 0600 .pgpass
```

### Replicación del cluster de la VPS:

Agregar al archivo `~/.pgpass` la información de conexión al cluster principal para los usuarios `replica_user` y `replica_rewind`. 
Dentro de este archivo se debe indicar los datos de conexión con el formato `ip:puerto:base de datos:nombre de usuario:password` en cada línea del mismo. 
Los : separan los campos, el # se utiliza para los comentarios y el * se utiliza como comodín para cualquiera de los campos exceptuando el password.

Por ejemplo:
```txt
# hostname:port:database:username:password
200.58.98.56:5432:*:replica_user:str0ngp@$$word
200.58.98.56:5432:template1:replica_rewind:str0ngp@$$word2
```
Donde `200.58.98.56` es la IP del clúster principal, `5432` el puerto del mismo y los paswords corresponden a los establecidos al crear los usuarios en el postgres Main.

Si ejecutamos `postgres@respaldo:~$ psql -h 200.58.98.56 -U replica_rewind`, psql se conectará al Main usando el puerto 5432, el usuario `replica_rewind`, la BD `template1` y el password `str0ngp@$$word2` según indica la segunda línea del archivo `~/.pgpass`.

**Nota**: Se utiliza la BD `template1` que siempre existe en postgresql porque de forma predeterminada se asume que cada usuario tiene una BD con su mismo nombre, lo cual no es cierto para los usuarios que utilizamos para la replicación.

Como usuario postgres crear un nuevo cluster de postgresql:
```bash
postgres@respaldo:~$ pg_createcluster 12 vps_clientes_1
```
Donde `12` es la versión de postgresql y `vps_clientes_1` el nombre del nuevo cluster. El comando lista el `data_dir` y el `puerto` del nuevo cluster.
También se se puede utilizar el comando `pg_lsclusters` para obtener esta información.
El cúster se crea detenido, proceder a eliminar el contenido de su data_dir:
```bash
postgresql@respaldo:~$ rm -r /var/lib/postgresql/12/vps_clientes_1/*
```
Realizar la copia inicial de datos realizando un backup del cluster principal utilizando `pg_basebackup`:
```bash
postgres@respaldo:~$ pg_basebackup -D /var/lib/postgresql/12/vps_odoo_clientes_1/ -PXs -cfast -Svps_odoo_clientes_1 -C -R -Ureplica_user -h200.58.98.56
```
Los parámetros para el pg_basebackup son:
* -D se indica el directorio del cluster réplica.
* -U se indica el usuario del cluster principal a utilizar, en este caso se usa replica_user que es el mismo que se usará para la replicación y fue configurado en el archivo .pgpass
* -h hostname o ip del clúster principal. Utilizar lo configurado en el archivo .pgpass
* -PXs muestra el progreso y realiza el streaming de WAL mientras se realiza el backup.
* -R IMPORTANTE: Genera el archivo standby.signal y coloca los datos de conexión
en el archivo postgresql.auto.conf del clúster secundario.
* -C indica que se debe crear, en el clúster principal, el replication slot indicado con el parámetro -S
* -S indica el nombre del replication slot a utilizar. En el ejemplo es vps_odoo_clientes_1
* -cfast indica que se realice un checkpoint lo más pronto posible en él principal. De esta forma el backup iniciará lo más rápido posible.

Al especificar el host y usuario, los demás datos necesarios para la conexión serán obtenidos del archivo ~/.pgpass de forma automática.
Una vez finalizado el backup, desde un usuario con permisos de sudo iniciar el cluster réplica:
```bash
odoouser@respaldo:~$ sudo systemctl start vps_odoo_clientes_1.services
```

Puntos importantes:
* Al indicar el host y el usuario para conectarse al postgres principal, los demás datos de conexión se obtienen desde el archivo ~/.pgpass.
* pg_basebackup crea un slot en el postgres principal con el nombre indicado en el parámetro -S. Este slot asegura que los archivos WAL necesarios para la réplica no sean borrados antes de que hayan sido aplicados correctamente.
* pg_basebackup crea un archivo con los datos de conexión de la réplica hacia el main llamado /var/lib/postgresql/12/main/postgresql.auto.conf en el cual se indican el archivo .pgpass y el slot a utilizar.

Para verificar que la replicación está activa se puede consular la misma en el main con las siguientes queries:
```sql 
select * from pg_stat_replication;
select * from pg_replication_slots;
```
En el caso del replication slot este figurará como activo.

## Replicación del Filestore.

Para la copia de los archivos del filestore desde el servidor principal al servidor de respaldo, es necesario configurar que el usuario odoorespaldo tenga acceso a los archivos del usuario odoo de la vps a replicar.
Para ello se configurará el acceso ssh y las llaves pública y privada correspondientes. Estas llaves son simples archivos de texto cuyo contenido es generado criptográficamente y representa la “identidad” de un usuario.
Estos archivos se guardan de forma predeterminada el directorio ~/.ssh de cada usuario. El contenido usual de dicho directorio es:
* id_rsa -> clave privada del usuario. Nunca debe ser compartida y sólo puede ser leída por el usuario al que pertenece.
* id_rsa.pub -> clave pública. Esta llave es compartida con quienes necesiten confirmar la identidad del usuario. Está asociada a la clave privada. 
* authorized_keys -> Opcional: contiene las claves públicas de los usuario que están autorizados para acceder a un servidor remoto.
* config -> Opcional: contiene los parámetros de conexión ssh a distintos servidores remotos para así no tener que escribir/recordar los mismos cada vez que se quiere acceder.

### En el servidor de respaldo:

De ser necesario crear el par de claves pùblico/privada para el usuario a utilizar. En nuestro caso odoouser:
```bash 
# cambiar al usuario que ejecuta odoo
odoo@respaldo:~$ sudo su - odoouser
# generar el par de claves públicas privadas, en este caso se indica 4096 bits de longitud
# No es conveniente sobreescribir las llaves, si ya existieran utilizar las existentes.
odoouser@respaldo:~$ ssh-keygen -b 4096
# Copiar la llave pública al servidor remoto en el home de un usuario con clave, en este
# caso “admin”. El `./` luego de : indica directorio home del usuario remoto.
odoouser@respaldo:~$ scp -P 5253 /opt/odoouser/.ssh/id_rsa.pub admin@200.58.98.56:./
# conectarse al servidor remoto (ssh admin@<ip-servidor-remoto>):
odoouser@respaldo:~$ ssh admin@200.58.98.56
# cambiarse al usuario que ejecuta odoo
admin@200.58.98.56:~$ sudo su - odoo
# si no existiera crear el directorio .ssh en el home del usuario odoo
odoo@200.58.98.56:~$ mkdir -p ~/.ssh
# volcar el contenido de la llave pública copiada del respaldo al archivo authorized_keys del usuario odoo:
odoo@200.58.98.56:~$ cat /home/admin/id_rsa.pub >> ~/.ssh/authorized_keys
# verificar la conexión desde el **servidor de respaldo**:
odoouser@respaldo:~$ ssh odoo@200.58.98.56 -p5253
```

Para facilitar las posteriores conexiones crear/editar el archivo ~/.ssh/config como el usuario odoo. El formato de este archivo es :
```txt 
Host <nombre_host_remoto_1>
    HostName <ip_1>
    Port <puerto-ssh-vps_1>
    User <user-odoo-vps_1>
Host <nombre_host_remoto_2>
    HostName <ip_2>
    Port <puerto-ssh-vps_2>
    User <user-odoo-vps_2>
…
Host <nombre_host_remoto_n>
    HostName <ip_n>
    Port <puerto-ssh-vps_n>
    User <user-odoo-vps_n>
```

En nuestro caso llamaremos al nuestro Host vps_clientes_1 con la ip 200.58.98.56, el puerto 5253 y el usuario odoo
```bash
odoo@respaldo:~$ sudo su - odoouser
odoouser@respaldo:~$ nano ~/.ssh/config
```
```txt
# Agregamos lo siguiente
Host vps_clientes_1
    HostName 200.58.98.56
    Port 5253
    User odoo
```
Presionamos Ctrl+O para guardar y Ctrl+X para salir del editor de texto *nano*.
Ahora deberíamos poder conectarnos desde odoorespaldo a la vps como el user odoo usando el nombre de Host configurado:
```bash
odoouser@respaldo:~$ ssh vps_clientes_1
```
Asimismo, cualquier comando ejecutado use ssh para conectarse tendrá los parámetros correctos.

### Estructura de directorio para los archivos replicados de Odoo:
Dentro del home del usuario odoouser tenemos dos directorios:
* odoo -> contiene el código fuente de odoo clonado del mismo modo que en el script de instalación.
* respaldo_filestore -> contiene una carpeta por vps replicada, dentro de cada una existen lo siguiente:
   * data_dir -> directorio con la copia “replicada” del filestore.
   * odoo -> enlace a la directorio del código fuente de odoo.
   * odoo.conf -> archivo de configuración para la instancia replicada de odoo. Deberá tener ajustados los paths a los addons y los datos del clúster de postgresql.
   * odoo_vps_clientes_1.service -> archivo usado para crear el daemon de la réplica de odoo.
   * requirement.txt -> archivo con las dependencias de python instaladas en la vps con pip.
   * sources -> directorio con la copia “replicada” de los módulos disponibles en la vps.

Crear una carpeta para la réplica de archivos de la vps, por ejemplo vps-clientes-1:
```bash
odoouser@respaldo:~$ mkdir -p replica_filestore/vps-clientes-1
```
Crear un enlace a la carpeta del código fuente de odoo:
```bash
odoouser@respaldo:~$ ln -s ~/odoo ~/replica_filestore/vps-clientes-1/
```
Copiar el filestore del odoo de la vps, usando rsync:
```bash
odoouser@respaldo:~$ rsync -azvP vps_clientes_1:/var/opt/odoo/data_dir /opt/odoouser/respaldo_filestore/vps-clientes-1/
```
Copiar la carpeta de módulos de odoo:
```bash
odoouser@respaldo:~$rsync -azvPvps_clientes_1:/opt/odoo/sources /opt/odoouser/respaldo_filestore/vps-clientes-1/
```
Copiar el archivo odoo.conf del odoo de la vps:
```bash
odoouser@respaldo:~$ scp vps_clientes_1:/etc/odoo.conf .
```
Editar el archivo `odoo.conf` recién copiado para ajustar los path de todos y cada uno de los addons a la ruta correspondiente dentro de la carpeta replicada. Por ejemplo: `/opt/odoouser/respaldo_filestore/vps-clientes-1/sources`. También configurar el path al data_dir correspondiente al filestor replicado. Ej `/opt/odoouser/respaldo_filestore/vps-clientes-1/data_dir`.
También configurar el puerto del clúster de postgresql correspondiente. Se pueden listar los clústeres existentes con el comando `pg_lsclusters`.
Crear y configurar el archivo odoo_vps_clientes_1.service:
```bash
odoouser@respaldo:~$ nano respaldo_filestore/vps-clientes-1/odoo_vps_clientes_1.service
```
```txt
# Agregar el siguiente contenido ajustandolo según corresponda:
[Unit]
  Description=Odoo ERP - Aliare SRL - Respaldo VPS_CLIENTES_1
  Documentation=http://www.odoo.com
  Requires=postgresql.service
  After=network.target postgresql.service
[Service]
  SyslogIdentifier=odoo15VPS_CLIENTES_1
  User=odoouser
  Group=odoouser
  StandarOuput=journal+console
  Restart=always
  RestartSec=3
  Type=exec
  User=odoouser
  ExecStart=/usr/bin/env python3 /opt/odoouser/respaldo_filestore/vps-clientes-1/odoo/odoo-bin -c /opt/odoouser/respaldo_filestore/vps-clientes-1/odoo.conf
[Install]
  WantedBy=default.target
```

Programar la copia del filestore y de los sources en el cron de odoouser:
```bash
odouser@respaldo:~$ crontab -e
```
```txt
# Agregar una línea especificando que el filestore se actualizarán cada 5 minutos
*/5 * * * * rsync -azv --delete --partial --timeout=15 vps_clientes_1:/var/opt/odoo/data_dir /opt/odoouser/respaldo_filestore/vps-clientes-1/ 2>&1 | logger -et VPS_CLIENTES_1_FILESTORE
# Agregar una línea especificado que los sources se copiarán una vez cada 12 horas
* */12 * * * rsync -azv --delete --partial --timeout=15 vps_clientes_1:/opt/odoo/sources /opt/odoouser/respaldo_filestore/vps-clientes-1/ 2>&1 | logger -et VPS_CLIENTES_1_SOURCES
```

Ajustar el path de destino de la copia así como la etiqueta del logger, VPS_CLIENTES_1_SOURCES. Esta etiqueta podrá ser buscada en el syslog de Ubuntu.
**Importante**: al realizar la copia el origen se refiere al directorio de la vps, no al contenido del mismo. Por eso *NO* se colora una / final “vps_clientes_1:/opt/odoo/sources”. Mientras que el destino de la copia es dentro del directorio “/opt/odoouser/respaldo_filestore/vps-clientes-1/” por lo que *SÍ* se coloca la barra final.

Generar archivo requirement.txt cada 12 horas mediante cron en la VPS:
```bash
odoo@vps_clientes_1:~$ crontab -e
```
```txt
# agregar una línea especificado la creación del requirement.txt cada 12 horas dentro del home
# Genera requirement.txt cada 12 horas para ser copiado al server de respaldo
* */12 * * * /usr/bin/pip freeze > /opt/odoo/requirement.txt
```

Programar la copia del archivo requirement.txt cada 12 horas en el servidor de respaldo:
```bash
odoouser@respaldo:~$ crontab -e
```
```txt
# Cada 12 horas sincroniza requirement.txt
* */12 * * * rsync -azv --partial --timeout=15 vps_clientes_1:/opt/odoo/requirement.txt /opt/odoouser/respaldo_filestore/vps-clientes-1/ 2>&1 | logger -et VPS_CLIENTES_1_REQUIREMENT
```
## Failover

En caso de catastrofe en el servidor de una vps quedando esta inaccesible, será necesario hacer disponible la replica de dicah vps realizando el proceso de Failover. Para ello habrá que promover el servidor postgresql standby de la vps correspondiente y utilizar el arvchivo de configuración de servicio correspondiente, por ejemplo `odoo_vps_clientes_1.service` para ejecutar odoo como daemon en el servidor de respaldo.

En el servidor de respaldo existen los siguientes usuarios de interés:
- odoo -> usuario con permiso de sudo (administrador)
- odoouser -> usuario bajo el cual se encuentran disponibles los archivos de los filestores replicados y del código de odoo. También es quien "ejecuta" una instancia de odoo promovida.
- postgres -> usuario administrador de los clústeres de postgresql replicados.

### Failover de Postgresql
Cambiar al usuario postgres y listar los clústeres para obtener los datos necesarios como la versión, el nombre, el puerto y el data directory:
```bash
odoo@respaldo:~$ sudo su - postgres
postgres@respaldo:~$ pg_lsclusters
```
Promover el cluster, por ejemplo vps_clientes_1:
```bash
postgres@respaldo:~$ pg_ctlcluster 12 vps_clientes_1 promote
```
Verificar en el log que el cluster esté disponible para conexiónes de lectura/escritura:
```bash
postgres@respaldo:~$ tail -fn 500 /var/log/postgresql/postgresql-12-vps_clientes_1.log
```
Una ves confirmado la disponibiblidad del clúster, percionar Ctrl+C para salir del listado del log.

