using System.Runtime.InteropServices;
using IntegrationDemo;

namespace IdrsComBridge;

[ComVisible(true)]
[Guid("E296C0A0-1111-4829-9296-D7B0D6ED296A")]
[ProgId("Er296ComBridge.Er296OcrComService")]
[ClassInterface(ClassInterfaceType.AutoDual)]
public class Er296OcrComService
{
    public string ProcessPdfToMarkdown(string inputPdfPath, string? outputMarkdownPath = null)
    {
        var legacyService = new IdrsOcrComService();
        return legacyService.ProcessPdfToMarkdown(inputPdfPath, outputMarkdownPath);
    }

    public string ProcessFile(string inputPath, string outputPath, string? options = null)
    {
        if (string.IsNullOrWhiteSpace(inputPath))
        {
            throw new ArgumentException("Se requiere una ruta de entrada.", nameof(inputPath));
        }

        var fullInputPath = Path.GetFullPath(inputPath);
        if (!File.Exists(fullInputPath))
        {
            throw new FileNotFoundException("No se encontró el archivo de entrada.", fullInputPath);
        }

        var fullOutputPath = Path.GetFullPath(outputPath);
        var outputDirectory = Path.GetDirectoryName(fullOutputPath)!;
        Directory.CreateDirectory(outputDirectory);

        using var wrapper = new IdrsNativeWrapper();
        if (!wrapper.IsEngineReady || !wrapper.TryInitializeEngine())
        {
            throw new InvalidOperationException("No se pudo inicializar el motor nativo ER296.");
        }

        bool success = wrapper.RecognizeImageFile(fullInputPath, out int zonesCount);
        var textResult = $"# Documento Procesado con ER296 Engine\n" +
            $"Entrada: {Path.GetFileName(fullInputPath)}\n" +
            $"Estado: {(success ? "Exitoso" : "Parcial")}\n" +
            $"Zonas Detectadas: {zonesCount}\n";

        File.WriteAllText(fullOutputPath, textResult);
        return fullOutputPath;
    }

    public string GetEngineInfo()
    {
        return "ER296 Native OCR Engine v2.0 (x64 COM Bridge)";
    }
}

[ComVisible(true)]
[Guid("D7B0D6ED-4BDA-4918-A7FE-6B8B6962C2A4")]
[ProgId("IdrsComBridge.IdrsOcrComService")]
[ClassInterface(ClassInterfaceType.AutoDual)]
public class IdrsOcrComService
{
    public string ProcessPdfToMarkdown(string inputPdfPath, string? outputMarkdownPath = null)
    {
        if (string.IsNullOrWhiteSpace(inputPdfPath))
        {
            throw new ArgumentException("Se requiere una ruta de entrada.", nameof(inputPdfPath));
        }

        var fullInputPath = Path.GetFullPath(inputPdfPath);
        if (!File.Exists(fullInputPath))
        {
            throw new FileNotFoundException("No se encontró el archivo de entrada.", fullInputPath);
        }

        var markdownPath = outputMarkdownPath is null
            ? Path.ChangeExtension(fullInputPath, ".md")
            : Path.GetFullPath(outputMarkdownPath);

        var outputDirectory = Path.GetDirectoryName(markdownPath)!;
        Directory.CreateDirectory(outputDirectory);

        using var wrapper = new IdrsNativeWrapper();
        if (!wrapper.IsEngineReady || !wrapper.TryInitializeEngine())
        {
            throw new InvalidOperationException("No se pudo inicializar el motor nativo ER296.");
        }

        bool success = wrapper.RecognizeImageFile(fullInputPath, out int zonesCount);

        var markdownText = $"# Documento: {Path.GetFileName(fullInputPath)}\n\n" +
            $"**Motor**: ER296 Nativo (COM Bridge)\n" +
            $"**Reconocimiento**: {(success ? "Exitoso" : "Parcial")}\n" +
            $"**Zonas detectadas**: {zonesCount}\n\n" +
            "--- Texto Reconocido ---\n";

        File.WriteAllText(markdownPath, markdownText);
        return markdownPath;
    }
}
