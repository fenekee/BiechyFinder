@echo off
chcp 65001 >nul
echo ==============================================
echo   Publication automatique de release BiechyFinder
echo ==============================================
python "%~dp0publish_release.py" %*
pause
