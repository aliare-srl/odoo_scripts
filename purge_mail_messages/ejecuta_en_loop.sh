#!/usr/bin/env bash
set -euo pipefail

: "${BD_A_PURGAR:?ERROR: Debe especificar la variable de entorno BD_A_PURGAR}"
BATCH_SIZE="${BATCH_SIZE:-10000}"

SCRIPT_PATH="$(dirname "$0")"

contador_bucles=0
TOTAL_ELIMINADOS=0

cleanup() {
  echo ""
  echo "--- FINALIZACIÓN DEL PROCESO ---"
  echo "Motivo: $1"
  echo "Bucles completados: $contador_bucles"
  echo "TOTAL DE REGISTROS ELIMINADOS: $TOTAL_ELIMINADOS"
  exit 0
}

trap 'cleanup "Señal (Ctrl+C o Timeout) recibida."' SIGTERM SIGINT

echo "Iniciando ejecución. BD: $BD_A_PURGAR | Lote: $BATCH_SIZE"
echo "Para detener, use Ctrl+C."

while true; do

  contador_bucles=$((contador_bucles + 1))
  echo "Bucle: $contador_bucles"

  # Ejecutar el script y capturar toda la salida (resiliencia con || true).
  SALIDA=$( { time -p BD_A_PURGAR="$BD_A_PURGAR" BATCH_SIZE="$BATCH_SIZE" "$SCRIPT_PATH/mail_message_purge.sh" 2>&1; } 2>&1 || true)

  EXIT_STATUS=$?
  echo "Salida del llamado: ${SALIDA}"

  # Procesamiento si la ejecución fue exitosa.
  if [[ $EXIT_STATUS -eq 0 ]]; then

    # Extraer conteo.
    COUNT=$(echo "$SALIDA" | grep -oP 'Borrados: \K[0-9]+' || true)

    if [[ -n "$COUNT" ]]; then
      TOTAL_ELIMINADOS=$((TOTAL_ELIMINADOS + COUNT))
    fi

    # Condición de salida por agotamiento.
    if [[ "$COUNT" -eq 0 ]]; then
      cleanup "Registros agotados."
    fi
  else
    # Registrar error de lock timeout.
    echo "Error en purga (código $EXIT_STATUS). Reintentando."
  fi

  sleep 3
done

