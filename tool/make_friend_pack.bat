@echo off
chcp 65001 >nul
set PYTHONUTF8=1
cd /d "%~dp0"
echo === FPL Advisor: building a pack for a friend ===
where py >nul 2>nul
if %errorlevel%==0 (
  py pack.py
) else (
  python pack.py
)
if %errorlevel% neq 0 (
  echo.
  echo Something went wrong. Send the text above to Claude.
  pause
  exit /b 1
)
echo.
echo Send dist\FPL_Advisor_for_friend.zip to your friend.
if exist "..\dist" start "" explorer "..\dist"
pause
