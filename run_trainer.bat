@echo off
title Minecraft Dungeons II - Standalone Native Trainer
cd /d "%~dp0"

python --version >nul 2>nul
if %errorlevel% equ 0 (
    python trainer_gui.py
    goto :end
)

py -3 --version >nul 2>nul
if %errorlevel% equ 0 (
    py -3 trainer_gui.py
    goto :end
)

echo [ERROR] Python was not found in your system PATH.
echo Please install 64-bit Python 3.10+ from python.org and ensure "Add Python to PATH" is checked.
echo.
pause
exit /b 1

:end
set "trainer_exit=%errorlevel%"
if not "%trainer_exit%"=="0" (
    echo.
    echo [ERROR] The trainer could not run. See the error above.
    pause
)
exit /b %trainer_exit%
