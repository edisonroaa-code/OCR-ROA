#include <windows.h>
#include <filesystem>
#include <iostream>
#include <string>

namespace fs = std::filesystem;

namespace
{
    fs::path find_upward(const fs::path& start, const fs::path& target)
    {
        for (auto current = start; !current.empty(); current = current.parent_path())
        {
            const auto candidate = current / target;
            if (fs::exists(candidate))
            {
                return candidate;
            }

            if (current == current.parent_path())
            {
                break;
            }
        }

        return {};
    }
}

int main(int argc, char** argv)
{
    try
    {
        const fs::path root = fs::current_path();
        const fs::path dllPath = find_upward(root, "idrsocr15.dll");
        const fs::path resourcesPath = find_upward(root, "OCRResources");

        std::cout << "iDRS15 native wrapper" << std::endl;
        std::cout << "Current directory: " << root.string() << std::endl;

        if (dllPath.empty())
        {
            std::cerr << "OCR DLL not found. Place the DLL in the workspace or next to the wrapper." << std::endl;
            return 1;
        }

        const fs::path defaultSample = dllPath.parent_path() / "native-wrapper" / "sample" / "sample.bmp";
        fs::path sampleImage = defaultSample;
        if (argc > 1)
        {
            sampleImage = fs::path(argv[1]);
            if (!sampleImage.is_absolute())
            {
                sampleImage = root / sampleImage;
            }
        }

        if (!fs::exists(sampleImage))
        {
            std::cerr << "Sample input not found: " << sampleImage.string() << std::endl;
            return 2;
        }

        std::cout << "DLL located at: " << dllPath.string() << std::endl;
        std::cout << "Resources located at: " << (resourcesPath.empty() ? "<missing>" : resourcesPath.string()) << std::endl;
        std::cout << "Sample input path: " << sampleImage.string() << std::endl;

        SetDllDirectoryW(dllPath.parent_path().wstring().c_str());

        HMODULE module = LoadLibraryW(dllPath.wstring().c_str());
        if (!module)
        {
            std::cerr << "Failed to load OCR DLL. Error: " << GetLastError() << std::endl;
            return 3;
        }

        FARPROC createProc = GetProcAddress(module, "drsE_create_drs");
        FARPROC destroyProc = GetProcAddress(module, "drsD_destroy_drs");
        FARPROC loadOcrProc = GetProcAddress(module, "drsE_load_ocr");
        FARPROC setEnvOcrProc = GetProcAddress(module, "drsD_set_env_ocr");
        FARPROC setEnvLexProc = GetProcAddress(module, "drsD_set_env_lex");
        FARPROC loadLexProc = GetProcAddress(module, "drsD_load_lex");

        std::cout << "Export checks:" << std::endl;
        std::cout << "- drsE_create_drs: " << (createProc ? "available" : "missing") << std::endl;
        std::cout << "- drsD_destroy_drs: " << (destroyProc ? "available" : "missing") << std::endl;
        std::cout << "- drsE_load_ocr: " << (loadOcrProc ? "available" : "missing") << std::endl;
        std::cout << "- drsD_set_env_ocr: " << (setEnvOcrProc ? "available" : "missing") << std::endl;
        std::cout << "- drsD_set_env_lex: " << (setEnvLexProc ? "available" : "missing") << std::endl;
        std::cout << "- drsD_load_lex: " << (loadLexProc ? "available" : "missing") << std::endl;

        std::cout << "Flow status:" << std::endl;
        std::cout << "1. DLL loaded" << std::endl;
        std::cout << "2. Resources discovered" << (resourcesPath.empty() ? " (missing)" : "") << std::endl;
        std::cout << "3. Sample input ready" << std::endl;
        std::cout << "4. Native entry points resolved; the next step is to wire the real OCR initialization sequence." << std::endl;

        FreeLibrary(module);
        return 0;
    }
    catch (const std::exception& ex)
    {
        std::cerr << "Exception: " << ex.what() << std::endl;
        return 99;
    }
}
