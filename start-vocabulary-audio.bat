@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start_vocabulary_audio.ps1"
if errorlevel 1 (
  echo.
  echo Startup failed. Read the message above and the logs folder, then try again.
  pause
  exit /b 1
)
echo.
echo Vocabulary Audio is running. This window can be closed.
if exist "%SystemRoot%\System32\timeout.exe" (
  "%SystemRoot%\System32\timeout.exe" /t 3 /nobreak >nul 2>&1
) else (
  ping -n 3 127.0.0.1 >nul 2>&1
)
endlocal
