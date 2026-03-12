@echo off
title Greybark Portal
cd /d "C:\Users\I7 8700\onedrive\documentos\wealth\estructuras\consejo_ia"

echo Starting ngrok with static domain...
start "ngrok" cmd /c "ngrok http 8000 --url=debbi-dolorimetric-trustworthily.ngrok-free.dev"
timeout /t 3 >nul

:loop
echo Starting FastAPI portal...
python -m uvicorn deploy.app:app --host 0.0.0.0 --port 8000
echo Server crashed. Restarting in 5 seconds...
timeout /t 5 >nul
goto loop
