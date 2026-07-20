using System.Runtime.InteropServices;

namespace IdrsComBridge;

[ComVisible(true)]
[Guid("D7B0D6ED-4BDA-4918-A7FE-6B8B6962C2A4")]
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

        var outputDirectory = outputMarkdownPath is null
            ? Path.Combine(AppContext.BaseDirectory, "output")
            : Path.GetDirectoryName(Path.GetFullPath(outputMarkdownPath))!;

        Directory.CreateDirectory(outputDirectory);

        var markdownPath = outputMarkdownPath is null
            ? Path.Combine(outputDirectory, Path.GetFileNameWithoutExtension(fullInputPath) + ".md")
            : Path.GetFullPath(outputMarkdownPath);

        var markdownText = $"# OCR output for {Path.GetFileName(fullInputPath)}\n\n" +
            "Este archivo fue preparado para el flujo OCR/Markdown a través de la puerta trasera COM.\n";

        File.WriteAllText(markdownPath, markdownText);
        return markdownPath;
    }
}
