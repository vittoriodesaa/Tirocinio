#!/usr/bin/env bash
# Avvia il server dalla root backend (dopo aver attivato il venv).
set -euo pipefail
cd "$(dirname "$0")/.."
if [ -d .venv ]; then
  source .venv/bin/activate
elif [ -d venv ]; then
  source venv/bin/activate
fi
exec python main.py
