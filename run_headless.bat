@echo off
title PulseFeed Engine - Headless Mode
cd /d "%~dp0"

echo ==============================================================
echo        PulseFeed Engine - Headless Background Service
echo ==============================================================
echo Running on http://127.0.0.1:8000 (No browser auto-launch)
echo Press Ctrl+C to stop.
echo.
run.bat --headless
