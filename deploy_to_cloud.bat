@echo off
chcp 65001 >nul
title SICK MARKETPLACE - 24/7 CLOUD HOSTING DEPLOYMENT
color 0b
cls
echo ====================================================================
echo   ⚡ SICK MARKETPLACE — 24/7 DAUERHAFT ONLINE BRINGEN
echo   (Auch wenn dein PC komplett ausgeschaltet ist!)
echo ====================================================================
echo.
echo Wenn dein PC aus ist, hat dein Computer keinen Strom.
echo Damit deine Kunden 24/7 rund um die Uhr einkaufen koennen,
echo laeuft die Webseite kostenlos auf einem Cloud-Server (z.B. Render.com).
echo.
echo --------------------------------------------------------------------
echo SCHRITT 1: Erstelle ein kostenloses GitHub-Repository:
echo    1. Oeffne im Browser: https://github.com/new
echo    2. Gib als Name ein: sick-marketplace
echo    3. Waehle "Private" oder "Public"
echo    4. Klicke unten auf "Create repository"
echo --------------------------------------------------------------------
echo.
set /p REPO_URL="Gib hier die GitHub Repository URL ein (z.B. https://github.com/deinname/sick-marketplace.git): "

if "%REPO_URL%"=="" (
    echo [!] Keine URL eingegeben. Abbruch.
    pause
    exit /b
)

echo.
echo [*] Verbinde lokales Projekt mit GitHub: %REPO_URL%...
git remote remove origin 2>nul
git remote add origin %REPO_URL%
git branch -M main
git add .
git commit -m "Update SICK Marketplace 24/7" 2>nul

echo [*] Lade Projekt auf GitHub hoch...
git push -u origin main

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ====================================================================
    echo   🎉 ERFOLGREICH AUF GITHUB HOCHGELADEN!
    echo ====================================================================
    echo.
    echo Jetzt der letzte Klick auf Render.com (100%% Kostenlos):
    echo   1. Oeffne: https://dashboard.render.com/web/new
    echo   2. Waehle dein GitHub-Repository "sick-marketplace" aus
    echo   3. Klicke auf "Deploy Web Service"
    echo.
    echo   Fertig! Render gibt dir deine dauerhafte 24/7 URL!
    echo   Deine Seite bleibt online, egal ob dein PC an oder aus ist!
    echo ====================================================================
) else (
    echo.
    echo [!] Fehler beim Push. Bitte pruefe, ob du bei GitHub eingeloggt bist.
)

echo.
pause
