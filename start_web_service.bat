@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
cd /d "%~dp0"
title SICK Gaming & Nitro Marketplace
color 0B
echo ========================================================
echo   SICK ⚡ GAMING & NITRO MARKETPLACE
echo   14x Server Boosts  |  Automated Cloud  |  Litecoin (LTC)
echo ========================================================
echo.
echo [*] Checking Python dependencies...
python -m pip install aiohttp requests >nul 2>&1

echo [*] Starting Web Server on http://localhost:5890...
start "" http://localhost:5890

echo.
echo [!] Server is running! Press Ctrl+C in this console to stop.
echo.
python server.py
pause
