#!/usr/bin/env bash
#Se hizo este archivo sh para ejecutarlo en el crontab cada una hora, primero crea los csv despues lo sube al ftp de dattadream y luego a nuestro ftp
/home/admin/odoo_scripts/en_uso/csv_full24express.py
/home/admin/odoo_scripts/en_uso/csv_ftp_full24express.sh
/home/admin/odoo_scripts/en_uso/csv_api_full24express.sh
/home/admin/odoo_scripts/en_uso/csv_ftp_testftpaliare.sh





