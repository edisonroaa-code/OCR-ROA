@echo off
chcp 65001 > nul
title Instalador ROA OCR - Registro COM y CLI global

echo =================================================================
echo   Instalador de ROA OCR CLI v2.0 & Servidor COM (iDRS15)
echo =================================================================

set WORKSPACE=D:\APLICATIVOS\ROA OCR
set COM_HOST=%WORKSPACE%\iDRS15\IdrsComBridge\bin\Release\net8.0\IdrsComBridge.comhost.dll

:: 1. Crear ejecutable CLI de conveniencia (roa-ocr.bat)
echo [+] Creando comando CLI 'roa-ocr.bat'...
(
  echo @echo off
  echo python "%WORKSPACE%\roa_ocr.py" %%*
) > "%WORKSPACE%\roa-ocr.bat"

:: 2. Registrar el DLL de COM en el Registro de Windows
echo [+] Registrando servidor COM (IdrsComBridge.comhost.dll)...
if exist "%COM_HOST%" (
    regsvr32 /s "%COM_HOST%"
    if %errorlevel% equ 0 (
        echo [SUCCESS] Servidor COM registrado exitosamente en Windows.
        echo          Objeto COM disponible: CreateObject("IdrsComBridge.IdrsOcrComService")
    ) else (
        echo [WARNING] regsvr32 requiri permisos de Administrador para registrar en el Registro de Windows.
        echo           Si no se registr, ejecuta este script como Administrador.
    )
) else (
    echo [ERROR] No se encontr %COM_HOST%. Compila el proyecto con 'dotnet build -c Release'.
)

echo.
echo =================================================================
echo   INSTALACIN COMPLETADA
echo =================================================================
echo 1. CLI Local: Usa 'python roa_ocr.py' o 'roa-ocr.bat'
echo 2. Servidor COM: Usa 'IdrsComBridge.IdrsOcrComService' desde VBA / VBScript / C# / Python
echo =================================================================
pause
