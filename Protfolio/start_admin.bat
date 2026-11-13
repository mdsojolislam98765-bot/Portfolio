@echo off
title Sojol Visuals - Admin Panel Launcher
echo ========================================================
echo   Launching Sojol Visuals Server and Admin Panel...
echo ========================================================
echo.
cd /d "%~dp0"
python server.py --open-admin
pause
