#!/usr/bin/env bash
set -euo pipefail
: "${BD_A_PURGAR:?ERROR: Debe especificar la variable de entorno BD_A_PURGAR}"
BATCH_SIZE=${BATCH_SIZE:-10000}

SCRIPT_PATH="$(dirname "$0")"

finalizar=0
contador_bucles=0
eliminados=0
# Captura SIGTERM (enviada por timeout) para terminar limpiamente después del batch actual.
trap 'finalizar=1' SIGTERM SIGINT

echo "Iniciando ejecución en ${SCRIPT_PATH}"
echo "Salir con CTRL+C o SIGTERM"

while true; do
  
  if [[ $finalizar -ne 0 ]]; then
    echo "Finalizando por trap."
    break
  fi

  contador_bucles=$((contador_bucles + 1))
  echo "Bucle: $contador_bucles"

  # '|| true' asegura que el bucle continúe aunque haya un lock timeout.
  SALIDA=$( { time -p BD_A_PURGAR="$BD_A_PURGAR" BATCH_SIZE="$BATCH_SIZE" ${SCRIPT_PATH}/mail_message_purge.sh 2>&1; } 2>&1 || true)

  echo "Salida del llamado: ${SALIDA}"

  # Extraer el número de borrados. Si falla por error de psql, COUNT será nulo.
  COUNT=$(echo "$SALIDA" | grep -oP 'Borrados: \K[0-9]+' || true)
  
  # Condición de salida: Si COUNT es 0 (no hay más registros a borrar).
  if [[ "$COUNT" -eq 0 ]]; then
    echo "Finalizado bucle, no hay más registros para borrar";
    break;
  fi

  sleep 3
done

echo "Fin. Bucles completados: $contador_bucles"
