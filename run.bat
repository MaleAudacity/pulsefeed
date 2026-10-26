@echo off
title PulseFeed - Local RSS and Alert Engine
cd /d "%~dp0"

echo ==============================================================
echo           PulseFeed - Local RSS and Alert Engine
echo ==============================================================
echo.

:: 1. Auto-detect Python executable
set "PY_CMD="
where python >nul 2>&1 && set "PY_CMD=python"
if not defined PY_CMD (
    where py >nul 2>&1 && set "PY_CMD=py"
)
if not defined PY_CMD (
    if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
        set "PY_CMD=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    )
)
if not defined PY_CMD (
    if exist "%ProgramFiles%\Python312\python.exe" (
        set "PY_CMD=%ProgramFiles%\Python312\python.exe"
    )
)

if not defined PY_CMD (
    echo [ERROR] Python was not found in your system PATH!
    echo Please install Python 3.8+ from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)

echo [*] Python detected: %PY_CMD%
echo [*] Checking dependencies...
%PY_CMD% -c "import fastapi, uvicorn, feedparser" >nul 2>&1
if errorlevel 1 (
    echo [*] Installing required packages from requirements.txt...
    %PY_CMD% -m pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo [ERROR] Failed to install dependencies. Check your internet connection.
        pause
        exit /b 1
    )
)

echo.
echo [*] Launching PulseFeed engine and dashboard...
%PY_CMD% main.py %*

echo.
echo ==============================================================
echo [*] PulseFeed engine has stopped.
echo ==============================================================
pause
