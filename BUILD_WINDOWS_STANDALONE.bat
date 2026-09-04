@echo off
setlocal
cd /d "%~dp0"

echo ============================================================
echo Astroneer Gameplay Tracker v1.15 - Windows Standalone Builder
echo ============================================================
echo.

where python >nul 2>nul
if errorlevel 1 (
  echo Python was not found in PATH.
  echo Install Python for Windows, then run this file again.
  pause
  exit /b 1
)

echo Installing/updating required packages...
python -m pip install --upgrade pip
if errorlevel 1 goto :fail
python -m pip install -r requirements.txt pyinstaller
if errorlevel 1 goto :fail

echo.
echo Cleaning old build output...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo.
echo Building standalone Windows distribution...
python -m PyInstaller --noconfirm Astroneer_Gameplay_Tracker.spec
if errorlevel 1 goto :fail

echo.
echo BUILD COMPLETE
echo Output:
echo   dist\Astroneer Gameplay Tracker\
echo.
echo Run:
echo   dist\Astroneer Gameplay Tracker\Astroneer Gameplay Tracker.exe
echo.
pause
exit /b 0

:fail
echo.
echo BUILD FAILED.
pause
exit /b 1
