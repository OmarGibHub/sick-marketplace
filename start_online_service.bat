@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
cd /d "%~dp0"
title SICK Gaming & Nitro Marketplace - Online Cloud Launcher
color 0B
echo ========================================================
echo   SICK ⚡ GAMING & NITRO MARKETPLACE — ONLINE LAUNCHER
echo   DDoS Protection  |  Automated HTTPS  |  gg/NitroHQ
echo ========================================================
echo.
echo [*] Checking Python dependencies...
python -m pip install aiohttp requests >nul 2>&1

echo [*] Starting SICK Web Platform and Cloudflare Tunnel...
python online_launcher.py
pause
