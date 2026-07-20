using System.Runtime.InteropServices;
using IntegrationDemo;

namespace IdrsComBridge;

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
            throw new InvalidOperationException("No se pudo inicializar el motor nativo iDRS15.");
        }

        bool success = wrapper.RecognizeImageFile(fullInputPath, out int zonesCount);

        var markdownText = $"# Documento: {Path.GetFileName(fullInputPath)}\n\n" +
            $"**Motor**: iDRS15 Nativo (COM Bridge)\n" +
            $"**Reconocimiento**: {(success ? "Exitoso" : "Parcial")}\n" +
            $"**Zonas detectadas**: {zonesCount}\n\n" +
            "--- Texto Reconocido ---\n";

        File.WriteAllText(markdownPath, markdownText);
        return markdownPath;
    }
}
