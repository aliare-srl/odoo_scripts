#!/usr/bin/env bash

FTP_SERVER="18.228.213.149"
FTP_USER="full24ftp"
FTP_PASS='$Full24-2022$'
LOCAL_DIR="/opt/odoo/csv/"
REMOTE_DIR="/"
FILES=("productos.csv" "category.csv")

lftp -c "open -u ${FTP_USER},${FTP_PASS} ${FTP_SERVER};
lcd ${LOCAL_DIR};
cd ${REMOTE_DIR};
$(for file in "${FILES[@]}"; do echo "put -e ${file};"; done)"
