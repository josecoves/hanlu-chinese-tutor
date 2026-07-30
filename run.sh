#!/bin/sh
set -eu
cd "$(dirname "$0")"
if [ -f .env.local ]; then
  set -a
  . ./.env.local
  set +a
fi
if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
  .venv/bin/pip install -r requirements.txt
fi
exec .venv/bin/uvicorn app.web:app --host 127.0.0.1 --port 8000
