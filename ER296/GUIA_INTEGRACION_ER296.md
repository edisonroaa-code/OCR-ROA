# Guía de integración recomendada para ER296

## Objetivo

Esta guía resume los pasos recomendados para integrar el motor OCR de ER296 de forma realista, a partir del análisis del workspace actual.

## Estado del proyecto detectado

- El paquete contiene bibliotecas nativas DLL, no un servicio web ni un backend HTTP.
- El componente principal es [idrsocr15.dll](idrsocr15.dll).
- El motor depende de otros DLLs como [idrskrn15.dll](idrskrn15.dll), [idrsprepro15.dll](idrsprepro15.dll), [idrsdocout15.dll](idrsdocout15.dll) y de los recursos de [OCRResources](OCRResources).

## Pasos recomendados

### 1. Confirmar el entorno de ejecución

Asegurar que el directorio de ejecución tenga:
- [idrsocr15.dll](idrsocr15.dll)
- [idrskrn15.dll](idrskrn15.dll)
- [idrsprepro15.dll](idrsprepro15.dll)
- [idrsdocout15.dll](idrsdocout15.dll)
- [OCRResources](OCRResources)

Esto evita errores de carga de dependencias.

### 2. Obtener la firma exacta de las funciones exportadas

Para que el wrapper funcione de forma estable, es necesario conocer:
- la convención de llamada,
- los tipos de parámetros,
- el tipo de retorno,
- el orden correcto de inicialización del motor.

En motores nativos como este, una firma incorrecta suele provocar una excepción de acceso a memoria.

### 3. Implementar un wrapper nativo

La recomendación más sólida es construir una capa nativa en C/C++ para:
- cargar la DLL,
- resolver las exportaciones,
- crear el motor,
- cargar recursos y entorno,
- ejecutar OCR,
- obtener resultados y zonas.

### 4. Preparar la entrada de imagen

Definir cómo se enviará la imagen al motor:
- formato,
- resolución,
- profundidad de color,
- orientación,
- tamaño.

### 5. Configurar el entorno de idioma y lexicon

Cargar los recursos de [OCRResources](OCRResources) y los módulos de idioma como:
- [idrsarabic15.dll](idrsarabic15.dll)
- [idrsasian15.dll](idrsasian15.dll)
- [idrsasian215.dll](idrsasian215.dll)
- [idrslex15.dll](idrslex15.dll)

### 6. Ejecutar el flujo completo

El flujo ideal es:
1. Crear el motor.
2. Configurar entorno.
3. Cargar lexicon y recursos.
4. Enviar imagen.
5. Ejecutar reconocimiento.
6. Obtener texto, zonas y resultados.
7. Exportar salida.

### 7. Probar con una imagen simple

Empezar con un documento claro de buena calidad para validar el flujo antes de pasar a textos complejos o documentos difíciles.

### 8. Encapsular el uso en una API propia

Una vez el motor funcione, exponer una capa simple como:
- `RecognizeImage`
- `GetText`
- `GetZones`
- `ExportResult`

## Recomendación práctica

El siguiente paso más útil es convertir el ejemplo actual en un wrapper nativo en C/C++ y usar esa capa como puente para una aplicación .NET o un servicio interno.

## Estado actual del ejemplo de integración

El ejemplo en [integration-demo](integration-demo) compila, pero la invocación real del motor sigue necesitando un contexto nativo más preciso para evitar excepciones de memoria.
