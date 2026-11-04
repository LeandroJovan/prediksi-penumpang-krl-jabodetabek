@echo off
title KRL Forecast Backend API (FastAPI)
echo ========================================================
echo   Menjalankan KRL Forecast FastAPI Server...
echo   - Swagger API Docs : http://localhost:8000/docs
echo   - ReDoc API Docs   : http://localhost:8000/redoc
echo   - REST Endpoints   : http://localhost:8000/api/v1
echo   - Web Dashboard    : http://localhost:8000/
echo ========================================================
start http://localhost:8000/docs
python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload

