@echo off
title KRL Insight Dashboard
echo ========================================================
echo   Menjalankan KRL Insight Dashboard...
echo   Browser akan terbuka otomatis di http://localhost:8000
echo   Untuk menghentikan server, tutup jendela terminal ini.
echo ========================================================
start http://localhost:8000
cd frontend
python -m http.server 8000
