@echo off
chcp 65001 >nul
set PYTHONUTF8=1
cd /d "%~dp0"
echo === FPL Advisor: updating data ===
where py >nul 2>nul
if %errorlevel%==0 (
  py fpl_tool.py --serve %*
) else (
  python fpl_tool.py --serve %*
)
if %errorlevel% neq 0 (
  echo.
  echo Something went wrong. Check internet and that Python 3.8+ is installed.
  echo Send the text above to Claude.
  pause
  exit /b 1
)
echo.
echo Closed. Send out\claude_brief.md to Claude.
