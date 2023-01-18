# Estos son script para el mantenimiento de una instalación de Odoo

## backup_ftp.sh - Subir backups a nuestro servidor

1. Tener instalado lftp (sudo apt install lftp
2. Modificar las variables dentro del script `backup_ftp.sh`
3. Programar la ejecución del script `backup_ftp.sh` en cron (Usar crontab -e)
   Para establecer los valores de cron se puede utliizar el sitio https://crontab.guru/#0_10_*_*_*
   Ejemplo 0 10 * * * se ejecutaría todos los días a las 10:00Hs

