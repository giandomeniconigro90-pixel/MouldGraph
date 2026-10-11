@echo off
cd /d "%~dp0"
title MouldGraph - prova Live Data
where py >nul 2>nul
if errorlevel 1 (
    python log_analyzer_desktop_live.py
) else (
    py -3 log_analyzer_desktop_live.py
)
if errorlevel 1 (
    echo.
    echo Avvio non riuscito. Copia il messaggio di errore qui sopra.
    echo La versione precedente e il suo EXE non sono stati modificati.
    pause
)
