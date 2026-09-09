@echo off
chcp 65001 >nul
title SICK MARKETPLACE - 1-KLICK GITHUB UPLOAD
color 0a
cd /d "%~dp0"
cls
echo ====================================================================
echo   ⚡ SICK MARKETPLACE — UPLOAD TO GITHUB
echo   Ziel: https://github.com/OmarGibHub/sick-marketplace
echo ====================================================================
echo.
echo [*] Lade alle Shop-Dateien auf dein GitHub hoch...
echo.

git remote remove origin 2>nul
git remote add origin https://github.com/OmarGibHub/sick-marketplace.git
git branch -M main
git add .
git commit -m "Deploy SICK Marketplace to GitHub" 2>nul
git push -u origin main

echo.
if %ERRORLEVEL% EQU 0 (
    echo ====================================================================
    echo   🎉 ERFOLG! ALLE DATEIEN SIND JETZT AUF GITHUB!
    echo ====================================================================
    echo.
    echo Gehe jetzt einfach zurueck in deinen Browser auf Render.com und
    echo klicke oben rechts auf:
    echo    "Manual Deploy" -^> "Deploy latest commit"!
    echo.
    echo Deine Seite ist ab sofort 24/7 dauerhaft online!
) else (
    echo ====================================================================
    echo   [!] Falls sich ein kleines Browser-Fenster geoeffnet hat:
    echo       Klicke einfach auf "Authorize" / "Sign in with browser"!
    echo ====================================================================
)
echo.
pause
