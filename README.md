# Estos son scripts para el mantenimiento de una instalación de Odoo

Habrá que clonarlos en el servidor y habilitar su ejecución de ser necesario (Usar chmod)

Se tiene la subcarpeta `en_uso` donde se copiará el script a personalizar dejando el original intacto.

## backup_ftp.sh - Subir backups a nuestro servidor

1. Tener instalado lftp (sudo apt install lftp)
2. Copiar el archivo `backup_ftp.sh` con un nombre distintivo dentro de la carpeta en_uso
`~/odoo_scripts$ cp backup_ftp.sh en_uso/backup_ftp_full24.sh`
3. Modificar las variables dentro del script `backup_ftp_full24.sh`
4. Programar la ejecución del script `backup_ftp_full24.sh` en cron (Usar crontab -e)
   Para establecer los valores de cron se puede utlizar el sitio [crontab.guru](https://crontab.guru/#0_10_*_*_*)

   Ejemplo: `0 10 * * *` se ejecutaría todos los días a las 10:00Hs

   *El script debe ejecutarse bajo un usuario con permiso de lectura/escritura sobre los archivos de backup.*

	4.1 Suponemos que el script se encuentra en `/home/admin/odoo_scripts/en_uso/backup_ftp_full24.sh` y el usuario con permiso de R/W es `odoo`
	4.2 `$ sudo su -- odoo -c "crontab -e"` -> Se abre el editor de tareas cron del usuario odoo
	4.3 Agregamos la programación
	`0 10 * * * * /home/admin/odoo_scripts/en_uso/backup_ftp_full24.sh`
	4.4 Guardamos los cambios. Se ha programado que todos los días a las 10:00HS se ejecute el el script de backup como el usuario odoo

## backup_odoo_instance.sh

1. Copiar el archivo `backup_odoo_instance.sh` con un nombre distintivo dentro del subdir en_uso. Ej. cp backup_odoo_instance.sh en_uso/backup_full24_instance.sh
2. Modificar las variables dentro del script copiado
3. Programar la ejecución del script en cron (Usar crontab -e)
   Para establece los valores del cron se puede utilizar el sition [crontab.guru](https://crontab.guru)
   3.1 Tener en cuenta los horarios ejecución del script de backup_ftp.sh para coordinarlos.

## analizar_server.sh
   Permite calcular los valores "idóneos" para la configuración de odoo. Ejecutar con el parámetro -h para ver su forma de uso.
