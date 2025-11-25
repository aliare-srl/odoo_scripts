#!/usr/bin/env bash
set -euo pipefail

# Se debe establecer la variable BD_A_PURGAR en el entorno. 
: "${BD_A_PURGAR:?ERROR: Debe especificar variable BD_A_PURGAR}"

# Valores predeterminados si no se reciben desde el entorno.
FECHA_CORTE="${FECHA_CORTE:-2025-07-01}" 
BATCH_SIZE="${BATCH_SIZE:-50000}"
# LOCK_TIMEOUT: Tiempo a esperar si hay algún bloqueo
# que impida el delete. 60s es un valor prudencial
LOCK_TIMEOUT="${LOCK_TIMEOUT:-60s}"

/usr/bin/psql -d "$BD_A_PURGAR" -t -A <<SQL
SET statement_timeout = 0;
SET lock_timeout = '${LOCK_TIMEOUT}';
WITH lote AS (
    SELECT id
    FROM mail_message
    WHERE create_date < '$FECHA_CORTE'
    ORDER BY id
    LIMIT $BATCH_SIZE
),
del AS (
    DELETE FROM mail_message m
    USING lote
    WHERE m.id = lote.id
    RETURNING m.create_date
)
SELECT
    'Borrados: ' || COUNT(*) ||
    ' | Última fecha: ' || COALESCE(MAX(create_date)::text, 'ninguna') AS resultado
FROM del;
SQL
