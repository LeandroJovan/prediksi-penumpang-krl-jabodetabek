@echo off
title KRL Forecast Backend API (Flask)
echo ========================================================
echo   Menjalankan KRL Forecast Flask Server...
echo   - Web Dashboard    : http://127.0.0.1:5000/
echo   - Health Check     : http://127.0.0.1:5000/api/health
echo   - Forecast API     : http://127.0.0.1:5000/api/forecast
echo ========================================================
start http://127.0.0.1:5000/
python backend/api.py

