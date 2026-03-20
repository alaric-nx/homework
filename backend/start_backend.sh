#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="${SCRIPT_DIR}"
CONFIG_FILE="${BACKEND_DIR}/config.env"

if [[ ! -f "${CONFIG_FILE}" ]]; then
  echo "Missing config file: ${CONFIG_FILE}"
  echo "Create it first, then retry."
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "${CONFIG_FILE}"
set +a

cd "${BACKEND_DIR}"

HOST="${SERVER_HOST:-127.0.0.1}"
PORT="${SERVER_PORT:-8000}"
RELOAD="${SERVER_RELOAD:-true}"

echo "Starting backend on ${HOST}:${PORT} (reload=${RELOAD})"
if [[ "${RELOAD}" == "true" ]]; then
  exec uvicorn app.main:app --host "${HOST}" --port "${PORT}" --reload
else
  exec uvicorn app.main:app --host "${HOST}" --port "${PORT}"
fi
