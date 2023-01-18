# Estos son scripts para el mantenimiento de una instalación de Odoo

Habrá que clonarlos en el servidor y habilitar su ejecución de ser necesario (Usar chmod)

## backup_ftp.sh - Subir backups a nuestro servidor

1. Tener instalado lftp (sudo apt install lftp)
2. Modificar las variables dentro del script `backup_ftp.sh`
3. Programar la ejecución del script `backup_ftp.sh` en cron (Usar crontab -e)
   Para establecer los valores de cron se puede utlizar el sitio [crontab.guru](https://crontab.guru/#0_10_*_*_*)

   Ejemplo: 0 10 * * * se ejecutaría todos los días a las 10:00Hs

   El script debe ejecutarse bajo un usuario con permiso de lectura/escritura sobre los archivos de backup.

	3.1 Suponemos que el script se encuentra en `/home/admin/odoo_scripts/backup_ftp.sh` y el usuario con permiso de R/W es `odoo`
	3.2 `$ sudo su -- odoo -c "crontab -e"` -> Se abre el editor de tareas cron del usuario odoo
	3.3 Agregamos la programación
	`0 10 * * * * /home/admin/odoo_scripts/backupftp.sh
	3.4 Guardamos los cambios. Se ha programado que todos los días a las 10:00HS se ejecute el el script de backup como el usuario odoo

