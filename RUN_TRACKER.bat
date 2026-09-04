@echo off
cd /d "%~dp0"
python main.py
if errorlevel 1 (
  echo.
  echo The tracker exited with an error.
  pause
)
