@echo off
chcp 65001 >nul
title ROA OCR API v2.0

echo.
echo  ╔══════════════════════════════════════════════════════╗
echo  ║      🐺  ROA OCR API v2.0 — Iniciando...            ║
echo  ╚══════════════════════════════════════════════════════╝
echo.

:: Verificar Python
python --version >nul 2>&1
if errorlevel 1 (
    echo  [ERROR] Python no encontrado. Instala Python 3.10+ desde python.org
    pause & exit /b 1
)

:: Ir a la carpeta del proyecto
cd /d "%~dp0"

:: Instalar dependencias si no están
if not exist "venv\" (
    echo  [INFO] Creando entorno virtual...
    python -m venv venv
    echo  [INFO] Instalando dependencias...
    call venv\Scripts\activate.bat
    pip install -q -r requirements.txt
) else (
    call venv\Scripts\activate.bat
)

:: Crear carpetas necesarias
if not exist "tmp\" mkdir tmp
if not exist "logs\" mkdir logs

:: Mostrar info
echo  [INFO] Directorio: %~dp0
echo  [INFO] API Key por defecto: roa-dev-key-2024
echo  [INFO] Dashboard: http://localhost:8000/dashboard
echo  [INFO] Swagger UI: http://localhost:8000/docs
echo.
echo  Presiona Ctrl+C para detener el servidor.
echo.

:: Iniciar el servidor FastAPI
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

pause
