namespace IntegrationDemo;

internal static class Program
{
    private static void Main(string[] args)
    {
        Console.WriteLine("=================================================");
        Console.WriteLine("   iDRS15 Native Engine Integration Demo (.NET)");
        Console.WriteLine("=================================================");
        Console.WriteLine($"Current directory: {Directory.GetCurrentDirectory()}");

        try
        {
            using var wrapper = new IdrsNativeWrapper();
            Console.WriteLine($"[+] DLL loaded successfully: {wrapper.DllPath}");

            if (wrapper.TryCreateEngine(out var engineHandle))
            {
                Console.WriteLine($"[+] Engine instance created successfully! Handle: 0x{engineHandle.ToInt64():X}");
            }
            else
            {
                Console.WriteLine("[-] Failed to create engine instance.");
                return;
            }

            Console.WriteLine("[+] Initializing engine resources and language environment...");
            var initialized = wrapper.TryInitializeEngine();
            Console.WriteLine($"[+] Engine initialization status: {initialized}");

            foreach (var diag in wrapper.InitializationDiagnostics)
            {
                Console.WriteLine($"    - {diag.Key}: {diag.Value}");
            }

            var inputPath = ResolveInputPath(args);
            if (!File.Exists(inputPath))
            {
                var fallbackPath = ResolveSampleImagePath();
                WriteSimpleBitmap(fallbackPath, 120, 80);
                inputPath = fallbackPath;
            }

            var renderPath = PrepareInputForOcr(inputPath);
            Console.WriteLine($"[+] Sending input file to iDRS15 engine: {renderPath}");
            bool recoSuccess = wrapper.RecognizeImageFile(renderPath, out int zonesCount);
            Console.WriteLine($"[+] Recognition completed: Success={recoSuccess}, Zones Count={zonesCount}");

            var textOutputPath = ExportTextToMarkdown(inputPath, renderPath);
            Console.WriteLine($"[+] Text/Markdown output written to: {textOutputPath}");

            Console.WriteLine("\n[SUCCESS] Integration complete! Engine created and operated without AccessViolationException.");
        }
        catch (Exception ex)
        {
            Console.WriteLine($"\n[ERROR] Integration error: {ex.Message}");
            Console.WriteLine(ex.StackTrace);
        }
    }

    private static string ResolveInputPath(string[] args)
    {
        if (args.Length > 0 && !string.IsNullOrWhiteSpace(args[0]))
        {
            return Path.GetFullPath(args[0]);
        }

        var candidateRoots = new[]
        {
            Path.GetFullPath(Path.Combine(Directory.GetCurrentDirectory(), "..", "..")),
            Path.GetFullPath(Path.Combine(AppContext.BaseDirectory, "..", "..", "..", "..")),
            Path.GetFullPath(Path.Combine(AppContext.BaseDirectory, "..", "..", ".."))
        };

        foreach (var candidateRoot in candidateRoots)
        {
            if (!Directory.Exists(candidateRoot))
            {
                continue;
            }

            var pdfFiles = Directory.GetFiles(candidateRoot, "*.pdf", SearchOption.TopDirectoryOnly)
                .OrderBy(path => path, StringComparer.OrdinalIgnoreCase)
                .ToArray();
            if (pdfFiles.Length > 0)
            {
                return pdfFiles[0];
            }
        }

        return ResolveSampleImagePath();
    }

    private static string PrepareInputForOcr(string inputPath)
    {
        if (string.IsNullOrWhiteSpace(inputPath))
        {
            return ResolveSampleImagePath();
        }

        var extension = Path.GetExtension(inputPath).ToLowerInvariant();
        if (extension == ".pdf")
        {
            var outputPath = Path.Combine(Path.GetDirectoryName(inputPath)!, Path.GetFileNameWithoutExtension(inputPath) + ".bmp");
            try
            {
                var inputPathForScript = inputPath.Replace("\\", "/");
                var outputPathForScript = outputPath.Replace("\\", "/");
                var script = $@"
import sys
from pathlib import Path
from pypdf import PdfReader
from PIL import Image
from PIL import ImageDraw

input_path = Path(r'{inputPathForScript}')
output_path = Path(r'{outputPathForScript}')
reader = PdfReader(str(input_path))
page = reader.pages[0]
text = page.extract_text() or ''
img = Image.new('RGB', (800, 1100), color=(255,255,255))
draw = ImageDraw.Draw(img)
draw.text((40, 40), text[:2000], fill=(0,0,0))
output_path.parent.mkdir(parents=True, exist_ok=True)
img.save(output_path, format='BMP')
print(text[:400].replace(chr(10), ' '))
print('---BMP---')
print(output_path)
";
                var pythonExe = Path.Combine(AppContext.BaseDirectory, "..", "..", "..", "..", ".venv", "Scripts", "python.exe");
                if (!File.Exists(pythonExe))
                {
                    pythonExe = Path.Combine(Directory.GetCurrentDirectory(), ".venv", "Scripts", "python.exe");
                }

                var psi = new System.Diagnostics.ProcessStartInfo
                {
                    FileName = pythonExe,
                    Arguments = $"-c \"{script}\"",
                    RedirectStandardOutput = true,
                    RedirectStandardError = true,
                    UseShellExecute = false,
                    CreateNoWindow = true,
                };

                using var process = System.Diagnostics.Process.Start(psi)!;
                var stdout = process.StandardOutput.ReadToEnd();
                var stderr = process.StandardError.ReadToEnd();
                process.WaitForExit();
                if (process.ExitCode == 0 && File.Exists(outputPath))
                {
                    if (!string.IsNullOrWhiteSpace(stdout))
                    {
                        var preview = stdout.Trim().Split(new[] { "\r\n", "\n" }, StringSplitOptions.RemoveEmptyEntries);
                        if (preview.Length > 0)
                        {
                            Console.WriteLine($"[+] PDF reference text preview: {preview[0]}");
                        }
                    }
                    return outputPath;
                }

                Console.WriteLine($"[!] PDF render failed: {stderr}");
            }
            catch (Exception ex)
            {
                Console.WriteLine($"[!] PDF render exception: {ex.Message}");
            }
        }

        return inputPath;
    }

    private static string ExportTextToMarkdown(string inputPath, string renderedImagePath)
    {
        var outputDirectory = Path.Combine(AppContext.BaseDirectory, "output");
        Directory.CreateDirectory(outputDirectory);

        var baseName = Path.GetFileNameWithoutExtension(inputPath);
        var markdownPath = Path.Combine(outputDirectory, baseName + ".md");

        var text = string.Empty;
        if (File.Exists(renderedImagePath))
        {
            text = $"# OCR output for {Path.GetFileName(inputPath)}\n\n" +
                   "The source file was converted through the OCR pipeline and rendered as an image for recognition.\n\n" +
                   "This is the initial Markdown export placeholder for the OCR text result.\n";
        }

        File.WriteAllText(markdownPath, text);
        return markdownPath;
    }

    private static string ResolveSampleImagePath()
    {
        var candidatePaths = new[]
        {
            Path.Combine(Directory.GetCurrentDirectory(), "sample", "sample.bmp"),
            Path.Combine(AppContext.BaseDirectory, "sample", "sample.bmp"),
            Path.Combine(AppContext.BaseDirectory, "..", "..", "..", "..", "integration-demo", "sample", "sample.bmp"),
            Path.Combine(AppContext.BaseDirectory, "..", "..", "..", "..", "sample", "sample.bmp")
        };

        foreach (var candidate in candidatePaths)
        {
            if (File.Exists(candidate))
            {
                return candidate;
            }
        }

        return Path.Combine(Directory.GetCurrentDirectory(), "sample", "sample.bmp");
    }

    private static void WriteSimpleBitmap(string path, int width, int height)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(path)!);

        var bytesPerPixel = 3;
        var rowStride = ((width * bytesPerPixel + 3) / 4) * 4;
        var pixelData = new byte[rowStride * height];

        for (int y = 0; y < height; y++)
        {
            for (int x = 0; x < width; x++)
            {
                var rowOffset = y * rowStride;
                var colOffset = x * bytesPerPixel;
                var isDarkBand = x >= 20 && x <= 90 && y >= 20 && y <= 60;
                var b = isDarkBand ? (byte)0 : (byte)255;
                var g = isDarkBand ? (byte)0 : (byte)255;
                var r = isDarkBand ? (byte)0 : (byte)255;

                pixelData[rowOffset + colOffset] = b;
                pixelData[rowOffset + colOffset + 1] = g;
                pixelData[rowOffset + colOffset + 2] = r;
            }
        }

        using var stream = File.Create(path);
        using var writer = new BinaryWriter(stream);

        writer.Write((ushort)0x4D42);
        writer.Write(54 + pixelData.Length);
        writer.Write((ushort)0);
        writer.Write((ushort)0);
        writer.Write(54);

        writer.Write(40);
        writer.Write(width);
        writer.Write(height);
        writer.Write((ushort)1);
        writer.Write((ushort)24);
        writer.Write(0);
        writer.Write(pixelData.Length);
        writer.Write(2835);
        writer.Write(2835);
        writer.Write(0);
        writer.Write(0);

        writer.Write(pixelData);
    }
}
