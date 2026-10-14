#!/usr/bin/env bash
# One-command start: creates the Python environment on first run, then serves
# the app at http://localhost:8000. Node is not needed — the site is prebuilt.
set -euo pipefail
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
  .venv/bin/pip install -q -r requirements.txt
fi
echo "Open http://localhost:8000  (Ctrl+C to stop)"
exec .venv/bin/python -m uvicorn app.main:app --port 8000
