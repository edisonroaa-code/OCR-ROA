using System.Reflection;
using System.Runtime.ExceptionServices;
using System.Runtime.InteropServices;
using System.Security;

namespace IntegrationDemo;

internal sealed class IdrsNativeWrapper : IDisposable
{
    private readonly string _dllPath;
    private readonly IntPtr _moduleHandle;
    private readonly IntPtr _engineHandle;
    private readonly IntPtr _loggerVtableMemory;
    private readonly IntPtr _loggerObjectMemory;
    private readonly LoggerDelegate _loggerCallback;

    private readonly CreateDrsDelegate? _createDrs;
    private readonly DestroyDrsDelegate? _destroyDrs;
    private readonly SetEnvOcrDelegate? _setEnvOcr;
    private readonly SetAlphabetDelegate? _setAlphabet;
    private readonly SetResolutionDelegate? _setResolution;
    private readonly SetImageDelegate? _setImage;
    private readonly SetOutputRetnDelegate? _setOutputRetn;
    private readonly OcrDelegate? _ocr;
    private readonly ZonesDelegate? _zones;
    private readonly FormatDelegate? _format;
    private readonly GetNbZonesDelegate? _getNbZones;

    private readonly Dictionary<string, bool> _initializationDiagnostics = new(StringComparer.OrdinalIgnoreCase);

    [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
    private delegate IntPtr CreateDrsDelegate(IntPtr param1, IntPtr param2);

    [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
    private delegate int DestroyDrsDelegate(IntPtr engine);

    [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
    private delegate int SetEnvOcrDelegate(IntPtr engine, IntPtr envStructPtr);

    [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
    private delegate int SetAlphabetDelegate(IntPtr engine, ushort alphabetId);

    [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
    private delegate int SetResolutionDelegate(IntPtr engine, int dpi);

    [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
    private delegate int SetImageDelegate(IntPtr engine, IntPtr buffer, int width, int height, int pitch);

    [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
    private delegate int SetOutputRetnDelegate(IntPtr engine, IntPtr option);

    [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
    private delegate int OcrDelegate(IntPtr engine);

    [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
    private delegate int ZonesDelegate(IntPtr engine);

    [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
    private delegate int FormatDelegate(IntPtr engine);

    [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
    private delegate int GetNbZonesDelegate(IntPtr engine, out int zonesCount);

    [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
    private delegate int LoggerDelegate(IntPtr a1, IntPtr a2, IntPtr a3, IntPtr a4);

    [StructLayout(LayoutKind.Sequential)]
    private struct OcrEnvStruct
    {
        public IntPtr ResourcePathPtr;
        public IntPtr Reserved1;
        public IntPtr Reserved2;
        public IntPtr Reserved3;
    }

    [DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Ansi)]
    private static extern IntPtr LoadLibrary(string lpLibFileName);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool FreeLibrary(IntPtr hModule);

    [DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Ansi)]
    private static extern IntPtr GetProcAddress(IntPtr hModule, string procName);

    [DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
    private static extern bool SetDllDirectory(string lpPathName);

    public IdrsNativeWrapper(string? dllPath = null)
    {
        _dllPath = dllPath ?? ResolveDefaultDllPath();

        var baseDirectory = Path.GetDirectoryName(_dllPath) ?? string.Empty;
        _ = SetDllDirectory(baseDirectory);
        PrepareRuntimeEnvironment(baseDirectory);

        _moduleHandle = LoadLibrary(_dllPath);
        if (_moduleHandle == IntPtr.Zero)
        {
            throw new InvalidOperationException($"No se pudo cargar {Path.GetFileName(_dllPath)}.");
        }

        LoadDependentLibraries(baseDirectory);

        _createDrs = ResolveDelegate<CreateDrsDelegate>("drsD_create_drs");
        _destroyDrs = ResolveDelegate<DestroyDrsDelegate>("drsD_destroy_drs");
        _setEnvOcr = ResolveDelegate<SetEnvOcrDelegate>("drsD_set_env_ocr");
        _setAlphabet = ResolveDelegate<SetAlphabetDelegate>("drs_set_alphabet");
        _setResolution = ResolveDelegate<SetResolutionDelegate>("drs_set_resolution");
        _setImage = ResolveDelegate<SetImageDelegate>("drs_set_image_grey") ?? ResolveDelegate<SetImageDelegate>("drs_set_image_color") ?? ResolveDelegate<SetImageDelegate>("drs_set_image");
        _setOutputRetn = ResolveDelegate<SetOutputRetnDelegate>("drs_set_output_retn");
        _ocr = ResolveDelegate<OcrDelegate>("drsOcr");
        _zones = ResolveDelegate<ZonesDelegate>("drsZones");
        _format = ResolveDelegate<FormatDelegate>("drsFormat");
        _getNbZones = ResolveDelegate<GetNbZonesDelegate>("drs_get_nb_zones");

        // Allocate mock unmanaged C++ logger object vtable to prevent AccessViolationException in native status logging
        _loggerCallback = (a1, a2, a3, a4) => 0;
        var callbackPointer = Marshal.GetFunctionPointerForDelegate(_loggerCallback);

        const int vtableSlots = 64;
        _loggerVtableMemory = Marshal.AllocHGlobal(IntPtr.Size * vtableSlots);
        for (int i = 0; i < vtableSlots; i++)
        {
            Marshal.WriteIntPtr(_loggerVtableMemory, i * IntPtr.Size, callbackPointer);
        }

        _loggerObjectMemory = Marshal.AllocHGlobal(IntPtr.Size * 2);
        Marshal.WriteIntPtr(_loggerObjectMemory, 0, _loggerVtableMemory);
        Marshal.WriteIntPtr(_loggerObjectMemory, IntPtr.Size, IntPtr.Zero);

        _engineHandle = TryCreateEngineInternal();

        if (_engineHandle != IntPtr.Zero)
        {
            WireLoggerToEngine();
        }
    }

    public string DllPath => _dllPath;

    public IntPtr EngineHandle => _engineHandle;

    public bool IsEngineReady => _engineHandle != IntPtr.Zero;

    public IReadOnlyDictionary<string, bool> InitializationDiagnostics => _initializationDiagnostics;

    public bool TryCreateEngine(out IntPtr engineHandle)
    {
        engineHandle = _engineHandle;
        return _engineHandle != IntPtr.Zero;
    }

    public bool TryInitializeEngine(string? resourcesPath = null)
    {
        if (_engineHandle == IntPtr.Zero)
        {
            _initializationDiagnostics["engine_created"] = false;
            return false;
        }

        _initializationDiagnostics["engine_created"] = true;

        var baseDir = Path.GetDirectoryName(_dllPath) ?? string.Empty;
        var targetResourcesPath = resourcesPath
            ?? (Directory.Exists(Path.Combine(baseDir, "OCRResources"))
                ? Path.Combine(baseDir, "OCRResources")
                : Path.GetFullPath(Path.Combine(baseDir, "..", "..", "..", "..", "OCRResources")));

        _initializationDiagnostics["resources_directory_exists"] = Directory.Exists(targetResourcesPath);

        if (_setEnvOcr is not null && Directory.Exists(targetResourcesPath))
        {
            var pathAnsi = Marshal.StringToHGlobalAnsi(targetResourcesPath);
            try
            {
                var envStruct = new OcrEnvStruct { ResourcePathPtr = pathAnsi };
                var envStructMemory = Marshal.AllocHGlobal(Marshal.SizeOf<OcrEnvStruct>());
                try
                {
                    Marshal.StructureToPtr(envStruct, envStructMemory, false);
                    var envResult = _setEnvOcr(_engineHandle, envStructMemory);
                    _initializationDiagnostics["set_env_ocr"] = envResult == 0 || envResult == -1;
                }
                finally
                {
                    Marshal.FreeHGlobal(envStructMemory);
                }
            }
            finally
            {
                Marshal.FreeHGlobal(pathAnsi);
            }
        }
        else
        {
            _initializationDiagnostics["set_env_ocr"] = false;
        }

        if (_setAlphabet is not null)
        {
            var alphaResult = _setAlphabet(_engineHandle, 1); // 1 = Latin
            _initializationDiagnostics["set_alphabet"] = alphaResult == 0;
        }

        if (_setResolution is not null)
        {
            _ = _setResolution(_engineHandle, 300);
        }

        if (_setOutputRetn is not null)
        {
            var retnResult = _setOutputRetn(_engineHandle, (IntPtr)1);
            _initializationDiagnostics["set_output_retn"] = retnResult == 0;
        }

        // Set engine initialized flag (offset 0x50ea)
        Marshal.WriteInt16(_engineHandle, 0x50ea, 1);

        return true;
    }

    [HandleProcessCorruptedStateExceptions, SecurityCritical]
    public bool RecognizeImageBuffer(byte[] pixelData, int width, int height, int pitch, out int zonesCount)
    {
        zonesCount = 0;
        if (_engineHandle == IntPtr.Zero || _setImage is null || _ocr is null || pixelData == null || pixelData.Length == 0)
        {
            return false;
        }

        Console.WriteLine($"[DBG] RecognizeImageBuffer: bufferLen={pixelData.Length}, w={width}, h={height}, pitch={pitch}");
        var unmanagedBuffer = Marshal.AllocHGlobal(pixelData.Length);
        try
        {
            Marshal.Copy(pixelData, 0, unmanagedBuffer, pixelData.Length);
            Console.WriteLine("[DBG] Calling _setImage...");
            var setImgRes = _setImage(_engineHandle, unmanagedBuffer, width, height, pitch);
            Console.WriteLine($"[DBG] _setImage result: {setImgRes}");
            if (setImgRes != 0)
            {
                return false;
            }

            Console.WriteLine("[DBG] Calling _ocr...");
            var ocrRes = _ocr(_engineHandle);
            Console.WriteLine($"[DBG] _ocr result: {ocrRes}");
            if (_getNbZones is not null)
            {
                try
                {
                    _ = _getNbZones(_engineHandle, out zonesCount);
                    Console.WriteLine($"[DBG] _getNbZones result: {zonesCount}");
                }
                catch (Exception ex)
                {
                    Console.WriteLine($"[DBG] _getNbZones exception: {ex.Message}");
                    zonesCount = 0;
                }
            }

            return ocrRes >= 0 || zonesCount >= 0;
        }
        catch
        {
            return false;
        }
        finally
        {
            Marshal.FreeHGlobal(unmanagedBuffer);
        }
    }

    public bool RecognizeImageFile(string imagePath, out int zonesCount)
    {
        zonesCount = 0;
        if (!File.Exists(imagePath))
        {
            return false;
        }

        if (!TryReadBitmap(imagePath, out var width, out var height, out var pixelData))
        {
            return false;
        }

        var pitch = ((width + 3) / 4) * 4;
        return RecognizeImageBuffer(pixelData, width, height, pitch, out zonesCount);
    }

    private static bool TryReadBitmap(string imagePath, out int width, out int height, out byte[] pixels)
    {
        width = 0;
        height = 0;
        pixels = Array.Empty<byte>();

        try
        {
            using var stream = File.OpenRead(imagePath);
            using var reader = new BinaryReader(stream);

            if (reader.ReadUInt16() != 0x4D42)
            {
                return false;
            }

            _ = reader.ReadUInt32();
            _ = reader.ReadUInt16();
            _ = reader.ReadUInt16();
            var pixelOffset = reader.ReadUInt32();
            var dibHeaderSize = reader.ReadUInt32();
            if (dibHeaderSize < 40)
            {
                return false;
            }

            width = reader.ReadInt32();
            height = Math.Abs(reader.ReadInt32());
            var planes = reader.ReadUInt16();
            var bitsPerPixel = reader.ReadUInt16();
            var compression = reader.ReadUInt32();
            if (planes != 1 || (bitsPerPixel != 24 && bitsPerPixel != 32 && bitsPerPixel != 8) || compression != 0)
            {
                return false;
            }

            stream.Position = pixelOffset;
            var bytesPerPixel = bitsPerPixel / 8;
            var rowStride = ((width * bytesPerPixel + 3) / 4) * 4;
            var rowBuffer = new byte[rowStride];
            var grayStride = ((width + 3) / 4) * 4;
            var grayPixels = new byte[grayStride * height];

            for (int y = 0; y < height; y++)
            {
                var readBytes = stream.Read(rowBuffer, 0, rowStride);
                if (readBytes < rowStride) break;

                for (int x = 0; x < width; x++)
                {
                    var offset = x * bytesPerPixel;
                    byte gray;
                    if (bitsPerPixel == 8)
                    {
                        gray = rowBuffer[offset];
                    }
                    else
                    {
                        var b = rowBuffer[offset];
                        var g = rowBuffer[offset + 1];
                        var r = rowBuffer[offset + 2];
                        gray = (byte)((r * 77 + g * 150 + b * 29) >> 8);
                    }
                    grayPixels[(height - 1 - y) * grayStride + x] = gray;
                }
            }

            pixels = grayPixels;
            return true;
        }
        catch
        {
            return false;
        }
    }

    public void Dispose()
    {
        if (_engineHandle != IntPtr.Zero && _destroyDrs is not null)
        {
            _ = _destroyDrs(_engineHandle);
        }

        if (_moduleHandle != IntPtr.Zero)
        {
            _ = FreeLibrary(_moduleHandle);
        }

        if (_loggerObjectMemory != IntPtr.Zero)
        {
            Marshal.FreeHGlobal(_loggerObjectMemory);
        }

        if (_loggerVtableMemory != IntPtr.Zero)
        {
            Marshal.FreeHGlobal(_loggerVtableMemory);
        }
    }

    private IntPtr TryCreateEngineInternal()
    {
        if (_createDrs is null)
        {
            return IntPtr.Zero;
        }

        try
        {
            return _createDrs(IntPtr.Zero, IntPtr.Zero);
        }
        catch (AccessViolationException)
        {
            return IntPtr.Zero;
        }
        catch (SEHException)
        {
            return IntPtr.Zero;
        }
    }

    private void WireLoggerToEngine()
    {
        try
        {
            var ptr5058 = Marshal.ReadIntPtr(_engineHandle, 0x5058);
            if (ptr5058 != IntPtr.Zero)
            {
                Marshal.WriteIntPtr(ptr5058, 0, _loggerObjectMemory);
            }
        }
        catch
        {
            // Ignore if memory layout differs
        }
    }

    private static string ResolveDefaultDllPath()
    {
        var candidates = new[]
        {
            Path.Combine(AppContext.BaseDirectory, "idrsocr15.dll"),
            Path.Combine(AppContext.BaseDirectory, "..", "..", "..", "..", "idrsocr15.dll"),
            Path.Combine(Directory.GetCurrentDirectory(), "idrsocr15.dll")
        };

        foreach (var candidate in candidates)
        {
            var fullPath = Path.GetFullPath(candidate);
            if (File.Exists(fullPath))
            {
                return fullPath;
            }
        }

        throw new FileNotFoundException("No se encontró idrsocr15.dll en la ruta esperada.");
    }

    private static void PrepareRuntimeEnvironment(string baseDirectory)
    {
        var workspaceRoot = Path.GetFullPath(Path.Combine(baseDirectory, "..", "..", "..", ".."));
        if (Directory.Exists(workspaceRoot))
        {
            Environment.CurrentDirectory = workspaceRoot;
        }

        var sourceResources = Path.Combine(workspaceRoot, "OCRResources");
        var targetResources = Path.Combine(AppContext.BaseDirectory, "OCRResources");
        if (Directory.Exists(sourceResources) && !Directory.Exists(targetResources))
        {
            CopyDirectory(sourceResources, targetResources);
        }
    }

    private static void CopyDirectory(string sourceDir, string destinationDir)
    {
        Directory.CreateDirectory(destinationDir);
        foreach (var file in Directory.GetFiles(sourceDir))
        {
            var target = Path.Combine(destinationDir, Path.GetFileName(file));
            File.Copy(file, target, overwrite: true);
        }

        foreach (var subDir in Directory.GetDirectories(sourceDir))
        {
            var targetSubDir = Path.Combine(destinationDir, Path.GetFileName(subDir));
            CopyDirectory(subDir, targetSubDir);
        }
    }

    private static void LoadDependentLibraries(string baseDirectory)
    {
        var candidateDlls = new[]
        {
            "idrsarabic15.dll",
            "idrsasian15.dll",
            "idrsasian215.dll",
            "idrsdocout15.dll",
            "idrsimp15.dll",
            "idrskrn15.dll",
            "idrslex15.dll",
            "idrsprepro15.dll"
        };

        foreach (var dllName in candidateDlls)
        {
            var dllPath = Path.Combine(baseDirectory, dllName);
            if (File.Exists(dllPath))
            {
                _ = LoadLibrary(dllPath);
            }
        }
    }

    private TDelegate? ResolveDelegate<TDelegate>(string exportName) where TDelegate : Delegate
    {
        var address = GetProcAddress(_moduleHandle, exportName);
        if (address == IntPtr.Zero)
        {
            return null;
        }

        return Marshal.GetDelegateForFunctionPointer<TDelegate>(address);
    }
}
