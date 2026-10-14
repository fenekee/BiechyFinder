@echo off
chcp 65001 >nul
echo ========================================================
echo   Lancement de BiechyFinder Web App (Svelte + FastAPI)
echo ========================================================
echo.
echo Démarrage du serveur local sur http://127.0.0.1:8000 ...
start "" http://127.0.0.1:8000
python server.py
pause
