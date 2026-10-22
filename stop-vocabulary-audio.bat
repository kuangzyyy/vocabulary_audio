@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\stop_vocabulary_audio.ps1"
echo.
pause
endlocal
