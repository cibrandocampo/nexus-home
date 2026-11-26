#!/bin/sh
# Production entrypoint: check the configuration, migrate, then serve.
set -eu

python -m app.preflight
alembic upgrade head

# One worker: rate limits and the clean-up task live in the process.
# --no-proxy-headers: client addresses come only from the app's TRUSTED_PROXIES (client_ip()).
exec uvicorn app.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --no-proxy-headers \
  --no-server-header \
  --log-level "$(printf '%s' "${LOG_LEVEL:-INFO}" | tr '[:upper:]' '[:lower:]')"
