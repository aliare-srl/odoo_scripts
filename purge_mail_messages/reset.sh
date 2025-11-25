#!/usr/bin/env bash

# Debe ejecutarse al finalizar la ventana de ejecución del script principal.

psql -d"$BD_A_PURGAR" <<SQL
ALTER TABLE mail_message RESET (autovacuum_enabled);
ALTER SYSTEM RESET wal_compression;
SELECT pg_reload_conf();
SQL
