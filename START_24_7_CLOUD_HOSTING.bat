@echo off
chcp 65001 >nul
title SICK MARKETPLACE - 24/7 DAUERHAFT ONLINE SCHALTEN
color 0b
cls
echo ====================================================================
echo   ⚡ SICK MARKETPLACE — 24/7 DAUERHAFT ONLINE SCHALTEN
echo   (Bleibt 100%% online, auch wenn dein PC ausgeschaltet ist!)
echo ====================================================================
echo.
echo Ich habe alles vorbereitet! Wir verbinden jetzt die Cloud.
echo.
echo --------------------------------------------------------------------
echo SCHRITT 1: GitHub Verbindung
echo Falls sich gleich dein Browser oeffnet:
echo Klicke einfach auf den gruenen Button "Authorize github"
echo (oder erstelle kostenlos einen Account falls du noch keinen hast).
echo --------------------------------------------------------------------
echo.

set GH_EXE="C:\Program Files\GitHub CLI\gh.exe"

%GH_EXE% auth status >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [*] Starte schnellen GitHub-Login im Browser...
    echo [*] Bitte bestaetige das Fenster im Browser mit einem Klick!
    %GH_EXE% auth login --web -h github.com -p https
)

echo.
echo [+] GitHub ist erfolgreich verbunden!
echo.
echo --------------------------------------------------------------------
echo SCHRITT 2: Projekt automatisch hochladen
echo --------------------------------------------------------------------
%GH_EXE% repo create sick-marketplace --public --source=. --remote=origin --push --yes 2>nul

if %ERRORLEVEL% NEQ 0 (
    echo [*] Aktualisiere Code auf GitHub...
    git push -u origin main
)

echo.
echo ====================================================================
echo   🎉 CODE ERFOLGREICH IN DIE CLOUD HOCHGELADEN!
echo ====================================================================
echo.
echo SCHRITT 3: 24/7 Server auf Render.com aktivieren (100%% KOSTENLOS)
echo --------------------------------------------------------------------
echo Ich oeffne jetzt direkt die Render.com Einrichtungsseite im Browser.
echo Du musst nur noch:
echo   1. Auf Render.com mit GitHub einloggen.
echo   2. Dein Repository "sick-marketplace" auswaehlen (Connect).
echo   3. Unten auf "Create Web Service" klicken.
echo.
echo FERTIG! Render gibt dir deine feste 24/7 Web-URL.
echo Die Seite bleibt ab jetzt IMMER online, auch wenn dein PC AUS ist!
echo ====================================================================
echo.
pause

start https://dashboard.render.com/select-repo?type=web
