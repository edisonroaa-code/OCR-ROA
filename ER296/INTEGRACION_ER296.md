# Guía de integración básica de iDRS15

## 1. Capa de integración en C#

Este repositorio ya no es solo un punto de partida: contiene una base de integración realista para usar iDRS15 desde .NET con carga de bibliotecas nativas, inicialización del motor y un flujo de entrada/salida preparado para OCR y Markdown.

### Archivos principales
- [integration-demo/integration-demo.csproj](integration-demo/integration-demo.csproj)
- [integration-demo/Program.cs](integration-demo/Program.cs)
- [integration-demo/IdrsNativeWrapper.cs](integration-demo/IdrsNativeWrapper.cs)
- [IdrsComBridge/IdrsOcrComService.cs](IdrsComBridge/IdrsOcrComService.cs)

### Qué hace hoy
1. Carga la DLL nativa [idrsocr15.dll](idrsocr15.dll).
2. Crea una instancia del motor y la inicializa con recursos del proyecto.
3. Acepta un PDF o una imagen como entrada.
4. Renderiza el PDF a BMP cuando no hay texto embebido.
5. Prepara una ruta de salida a Markdown para el resultado.
6. Expone una puerta trasera COM para agentes externos.

### Cómo ejecutar la demo
```powershell
cd integration-demo
dotnet run
```

### Cómo validar la puerta COM
```powershell
cd .
dotnet test IdrsComBridge.Tests/IdrsComBridge.Tests.csproj
```

### Salida esperada
- se genera un archivo BMP intermedio en el flujo PDF → imagen,
- se escribe un resultado Markdown en la carpeta de salida del proyecto,
- y la demo deja constancia de si la invocación al motor fue estable.

### Observación importante
La integración ya está estable en el sentido de carga, creación e inicialización del motor. El siguiente objetivo es afinar la extracción real de texto OCR para documentos complejos y mejorar la calidad del resultado final.
