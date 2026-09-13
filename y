#!/usr/bin/env bash
echo '=== 12b00 Marketplace Auto-Launcher y ==='
export PYTHONUNBUFFERED=1
export PORT=${PORT:-5890}
echo '[*] Checking Python dependencies...'
python3 -m pip install --break-system-packages -r requirements.txt 2>/dev/null || python3 -m pip install -r requirements.txt 2>/dev/null || pip install -r requirements.txt 2>/dev/null || true
echo '[*] Launching server on port' $PORT '...'
exec python3 server.py
