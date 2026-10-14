@echo off
chcp 65001 >nul
title BiechyFinder
start /b pythonw app.py
if %ERRORLEVEL% neq 0 (
    python app.py
)
