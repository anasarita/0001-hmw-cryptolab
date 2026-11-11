@echo off
title CRYPTO LAB - SIMULADOR & AUDITORIA FORENSE
color 0B
cd /d "%~dp0"

echo ======================================================================
echo           INICIANDO SERVIDOR DE CRYPTO LAB PARA TU CLASE
echo ======================================================================
echo.
echo Verificando entorno de ejecucion...
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] No se encontro Python en el sistema.
    echo Asegurate de tener Python instalado y en el PATH.
    pause
    exit /b
)

echo Python detectado correctamente.
echo Iniciando servidor en red local (0.0.0.0)...
echo.

python iniciar_cryptolab.py

pause
