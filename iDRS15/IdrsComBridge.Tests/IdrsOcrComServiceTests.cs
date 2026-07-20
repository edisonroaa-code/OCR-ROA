using IdrsComBridge;
using Xunit;

namespace IdrsComBridge.Tests;

public class IdrsOcrComServiceTests
{
    [Fact]
    public void ProcessPdfToMarkdown_WritesMarkdownFile()
    {
        var tempDir = Path.Combine(Path.GetTempPath(), "idrs-com-tests", Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(tempDir);

        var inputPath = Path.Combine(tempDir, "sample.pdf");
        File.WriteAllText(inputPath, "placeholder");

        var service = new IdrsOcrComService();
        var outputPath = service.ProcessPdfToMarkdown(inputPath, Path.Combine(tempDir, "out.md"));

        Assert.True(File.Exists(outputPath));
        Assert.Contains("OCR output", File.ReadAllText(outputPath));

        Directory.Delete(tempDir, recursive: true);
    }
}
