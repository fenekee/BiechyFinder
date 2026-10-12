@echo off
chcp 65001 >nul
echo ========================================================
echo   Configuration de l'environnement BiechyFinder (Dev)
echo ========================================================
echo.

where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [1/2] Python n'est pas détecté sur cette machine.
    echo Installation automatique de Python via winget...
    winget install Python.Python.3.12 --silent --accept-package-agreements --accept-source-agreements
    if %ERRORLEVEL% neq 0 (
        echo Échec de l'installation automatique. Veuillez installer Python manuellement depuis python.org.
        pause
        exit /b 1
    )
    echo Python installé avec succès !
) else (
    echo [1/2] Python est déjà installé.
)

echo [2/2] Installation des dépendances (customtkinter, paramiko, httpx)...
python -m pip install --upgrade pip
python -m pip install -r "%~dp0requirements.txt"

echo.
echo ========================================================
echo   Environnement configuré avec succès !
echo   Vous pouvez lancer le script via : python BiechyFinder.py
echo ========================================================
pause
