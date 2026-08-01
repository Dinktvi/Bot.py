#!/usr/bin/env bash
set -e

# Load .env if present
if [ -f .env ]; then
  set -a
  . ./.env
  set +a
fi

export PYTHONPATH="$(pwd):${PYTHONPATH}"

python3 -m pip install -q --break-system-packages -r requirements.txt

exec python3 -m bot.main
