#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="${SCRIPT_DIR}"
# Prefer relative config from current working directory, then fallback to script directory.
if [[ -f "./config.env" ]]; then
  CONFIG_FILE="./config.env"
else
  CONFIG_FILE="${BACKEND_DIR}/config.env"
fi
if [[ -f "./.env" ]]; then
  DOTENV_FILE="./.env"
else
  DOTENV_FILE="${BACKEND_DIR}/.env"
fi

if [[ -f "${CONFIG_FILE}" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "${CONFIG_FILE}"
  set +a
else
  echo "Config file not found, start with defaults: ${CONFIG_FILE}"
fi

# Higher priority local overrides.
if [[ -f "${DOTENV_FILE}" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "${DOTENV_FILE}"
  set +a
fi

cd "${BACKEND_DIR}"

HOST="${SERVER_HOST:-127.0.0.1}"
PORT="${SERVER_PORT:-3000}"
RELOAD="${SERVER_RELOAD:-true}"

kill_existing_listener() {
  local pids=""
  if command -v lsof >/dev/null 2>&1; then
    pids="$(lsof -tiTCP:"${PORT}" -sTCP:LISTEN 2>/dev/null || true)"
  fi
  if [[ -z "${pids}" ]] && command -v fuser >/dev/null 2>&1; then
    pids="$(fuser "${PORT}"/tcp 2>/dev/null || true)"
  fi

  if [[ -z "${pids}" ]]; then
    return
  fi

  echo "Port ${PORT} is in use, stopping existing process(es): ${pids}"
  kill ${pids} 2>/dev/null || true

  for _ in {1..20}; do
    sleep 0.2
    if command -v lsof >/dev/null 2>&1; then
      if ! lsof -tiTCP:"${PORT}" -sTCP:LISTEN >/dev/null 2>&1; then
        return
      fi
    fi
  done

  echo "Force killing process(es) on port ${PORT}: ${pids}"
  kill -9 ${pids} 2>/dev/null || true
}

kill_existing_listener

echo "Starting backend on ${HOST}:${PORT} (reload=${RELOAD})"
if [[ "${RELOAD}" == "true" ]]; then
  exec uvicorn app.main:app --host "${HOST}" --port "${PORT}" --reload
else
  exec uvicorn app.main:app --host "${HOST}" --port "${PORT}"
fi
