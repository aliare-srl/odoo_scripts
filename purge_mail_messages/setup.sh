#!/usr/bin/env bash

set -euo pipefail

# Debe ejecutarse unos minutos antes del script principal
psql -d"$BD_A_PURGAR" -t -A <<SQL
ALTER SYSTEM SET wal_compression = on;
SELECT pg_reload_conf();
ALTER TABLE mail_message SET (autovacuum_enabled = false);
SQL
