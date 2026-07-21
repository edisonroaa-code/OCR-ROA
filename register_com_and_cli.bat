@echo off
title Instalador ROA OCR - Registro COM y CLI global

echo =================================================================
echo   Instalador de ROA OCR CLI v2.0 y Servidor COM (iDRS15)
echo =================================================================

set WORKSPACE=%~dp0
set WORKSPACE=%WORKSPACE:~0,-1%
set PROJECT_DIR=%WORKSPACE%\ER296\Er296ComBridge
set COM_HOST=%WORKSPACE%\ER296\Er296ComBridge\bin\Release\net8.0\IdrsComBridge.comhost.dll

:: 1. Compilar proyecto COM Bridge si es necesario
echo [+] Verificando compilacion del servidor COM...
if not exist "%COM_HOST%" (
    echo [+] Compilando IdrsComBridge en modo Release...
    dotnet build "%PROJECT_DIR%\IdrsComBridge.csproj" -c Release
)

:: 2. Crear ejecutable CLI de conveniencia (roa-ocr.bat)
echo [+] Creando comando CLI 'roa-ocr.bat'...
echo @echo off > "%WORKSPACE%\roa-ocr.bat"
echo python "%WORKSPACE%\roa_ocr.py" %%* >> "%WORKSPACE%\roa-ocr.bat"

:: 3. Registrar la DLL de COM en el Registro de Windows
echo [+] Registrando servidor COM (IdrsComBridge.comhost.dll)...
if exist "%COM_HOST%" (
    C:\Windows\System32\regsvr32.exe /s "%COM_HOST%"
    if %errorlevel% equ 0 (
        echo [SUCCESS] Servidor COM registrado exitosamente en Windows.
        echo          Objeto COM disponible: CreateObject("IdrsComBridge.IdrsOcrComService")
    ) else (
        echo [WARNING] Error al registrar con regsvr32.
        echo           Por favor ejecuta este script desde CMD como Administrador.
    )
) else (
    echo [ERROR] No se pudo encontrar el archivo: "%COM_HOST%"
)

echo.
echo =================================================================
echo   INSTALACION COMPLETADA EXITOSAMENTE
echo =================================================================
echo 1. CLI Local: Usa 'python roa_ocr.py' o 'roa-ocr.bat'
echo 2. Servidor COM: Usa 'IdrsComBridge.IdrsOcrComService' desde VBA / VBScript / C# / Python
echo =================================================================
pause
