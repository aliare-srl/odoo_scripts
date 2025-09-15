#!/bin/bash

# Endpoint y token
URL="https://full24-main-448ub9.laravel.cloud/api/admin/sync-csv"
TOKEN="m0W4z+h5senXDRlEQUQIbumSsPNbVMJWDJP6MXoCo1k="

# Archivos CSV
PRODUCTOS="/opt/odoo/csv/productos.csv"
CATEGORIAS="/opt/odoo/csv/category.csv"

# Carpeta de logs
LOG_DIR="/opt/odoo/csv/log-envio"
LOG_FILE="$LOG_DIR/sync.log"

# Crear carpeta de logs si no existe
mkdir -p "$LOG_DIR"

# Escribir fecha al inicio del log (sobrescribe cada vez)
echo "==== Ejecución: $(date '+%Y-%m-%d %H:%M:%S') ====" > "$LOG_FILE"

# Llamada a la API y guardar respuesta en el log
curl --location "$URL" \
  --header "X-Admin-Token: $TOKEN" \
  --form "productos=@\"$PRODUCTOS\"" \
  --form "categorias=@\"$CATEGORIAS\"" \
  --silent --show-error \
  >> "$LOG_FILE"

echo "Ejecución finalizada. Log guardado en $LOG_FILE"
