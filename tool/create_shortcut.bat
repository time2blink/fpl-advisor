@echo off
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0create_shortcut.ps1"
if %errorlevel% neq 0 (
  echo Could not create the shortcut. Right-click run.bat - Send to - Desktop (create shortcut).
)
echo.
pause
