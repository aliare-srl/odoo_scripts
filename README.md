# Estos son scripts para el mantenimiento de una instalación de Odoo

Habrá que clonarlos en el servidor y habilitar su ejecución de ser necesario (Usar chmod)

## backup_ftp.sh - Subir backups a nuestro servidor

1. Tener instalado lftp (sudo apt install lftp
2. Modificar las variables dentro del script `backup_ftp.sh`
3. Programar la ejecución del script `backup_ftp.sh` en cron (Usar crontab -e)
   Para establecer los valores de cron se puede utliizar el sitio [crontab.guru](https://crontab.guru/#0_10_*_*_*)

   Ejemplo: 0 10 * * * se ejecutaría todos los días a las 10:00Hs

   El script debe ejecutarse bajo un usuario con permiso de lectura/escritura sobre los archivos de backup.

Ejemplo completo: Suponemos que el script se encuentra en /home/admin/odoo_scripts/backup_ftp.sh
`$ crontab -e`
Se abre el editor de tareas cron, ingresamos ls siguiente línea:
`0 10 * * * * sudo su -- odoo -c "/home/admin/odoo_scripts/backupftp.sh"`
Guardamos los cambios. Se ha programado que todos los días a las 10:00HS se ejecute el el script de backup como el usuario odoo

