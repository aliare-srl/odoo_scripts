#!/usr/bin/env bash
lftp -c "open mochipa.com.ar -u backupcliente,'backupcliente';
lcd /opt/odoo/csv/;
cd /odoo/testcsvfull24/;
put -e productos.csv;
put -e category.csv;"
