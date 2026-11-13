@echo off
rem ===========================================================================
rem  Pomodoro starten.
rem
rem  Doppelklick genuegt. Argumente werden durchgereicht, zum Beispiel:
rem      start-windows.bat --window
rem      start-windows.bat --page /pomodoro/stats
rem      start-windows.bat --no-browser
rem
rem  Das Skript sucht Python, ergaenzt fehlende Abhaengigkeiten und merkt,
rem  wenn der Server schon laeuft -- dann oeffnet es nur den Browser.
rem ===========================================================================

setlocal
cd /d "%~dp0"
title Pomodoro

echo.
echo   Pomodoro
echo   --------
echo.

rem -- 1. Python finden -------------------------------------------------------
set "PY="
py -3 --version >nul 2>&1 && set "PY=py -3"
if not defined PY (
    python --version >nul 2>&1 && set "PY=python"
)
if not defined PY (
    echo   Python 3 wurde nicht gefunden.
    echo.
    echo   Installieren von https://www.python.org/downloads/
    echo   Dabei den Haken bei "Add python.exe to PATH" setzen.
    echo.
    pause
    exit /b 1
)

rem -- 2. Abhaengigkeiten pruefen ---------------------------------------------
%PY% -c "import flask, yaml" >nul 2>&1
if errorlevel 1 (
    echo   Flask oder PyYAML fehlen. Installiere ...
    echo.
    %PY% -m pip install --disable-pip-version-check --quiet Flask PyYAML
    if errorlevel 1 (
        echo.
        echo   Installation fehlgeschlagen. Von Hand:
        echo       %PY% -m pip install Flask PyYAML
        echo.
        pause
        exit /b 1
    )
    echo   Fertig.
    echo.
)

rem -- 3. Adresse aus config.yaml lesen ---------------------------------------
set "HOST=127.0.0.1"
set "PORT=5333"
for /f "tokens=1,2" %%a in ('%PY% -c "from data.appconfig import CONFIG as c; print(c['server']['host'], c['server']['port'])" 2^>nul') do (
    set "HOST=%%a"
    set "PORT=%%b"
)

rem -- 4. Laeuft schon einer? --------------------------------------------------
rem     Ohne diese Pruefung endet ein zweiter Start in einem haesslichen
rem     "address already in use" statt im Timer.
%PY% -c "import socket,sys; s=socket.socket(); s.settimeout(0.5); sys.exit(0 if s.connect_ex(('%HOST%', %PORT%))==0 else 1)" >nul 2>&1
if not errorlevel 1 (
    echo   Der Server laeuft bereits auf Port %PORT%.
    echo   Oeffne nur den Browser ...
    start "" "http://%HOST%:%PORT%/pomodoro"
    rem  Kurz stehen lassen. Kein timeout /t -- das bricht ab, sobald
    rem  die Eingabe umgeleitet ist.
    ping -n 3 127.0.0.1 >nul 2>&1
    exit /b 0
)

rem -- 5. Los -----------------------------------------------------------------
echo   Adresse:  http://%HOST%:%PORT%/pomodoro
echo   Beenden:  Strg + C oder dieses Fenster schliessen
echo.

%PY% app.py %*

rem Bei einem Fehler das Fenster offen lassen, sonst ist die Meldung weg,
rem bevor man sie lesen kann.
if errorlevel 1 (
    echo.
    echo   Der Server hat sich mit einem Fehler beendet ^(siehe oben^).
    echo.
    pause
)

endlocal
