@echo off
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
    python log_analyzer_desktop_live.py
) else (
    py -3 log_analyzer_desktop_live.py
)
if errorlevel 1 (
    echo Avvio fallito. Usa Python con le dipendenze della versione funzionante.
    pause
)
