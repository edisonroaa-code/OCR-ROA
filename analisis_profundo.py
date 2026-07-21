"""
ROA OCR - Análisis profundo de dependencias
"""
import pefile
import os

def analyze(filename, label):
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")
    if not os.path.exists(filename):
        print(f"  No encontrado")
        return
    size = os.path.getsize(filename)
    print(f"  Tamano: {size/1024:.0f} KB ({size/1024/1024:.1f} MB)")
    
    try:
        pe = pefile.PE(filename, fast_load=True)
        print(f"  Machine: {pe.FILE_HEADER.Machine}")
        print(f"  Secciones: {pe.FILE_HEADER.NumberOfSections}")
        
        # Parse exports
        try:
            pe.parse_data_directories()
            exports = []
            for exp in pe.DIRECTORY_ENTRY_EXPORT.symbols:
                if exp.name:
                    exports.append(exp.name.decode())
            if exports:
                print(f"\n  EXPORTS ({len(exports)}):")
                for e in exports[:30]:
                    print(f"     {e}")
                if len(exports) > 30:
                    print(f"     ... y {len(exports)-30} mas")
            else:
                print(f"\n  Exports: Solo ordinales ({len(pe.DIRECTORY_ENTRY_EXPORT.symbols)} funciones)")
        except:
            print(f"\n  Exports: No tiene tabla de exportacion")
        
        # Parse imports
        try:
            imports = {}
            for entry in pe.DIRECTORY_ENTRY_IMPORT:
                dll_name = entry.dll.decode()
                if dll_name not in imports:
                    imports[dll_name] = []
                for imp in entry.imports[:5]:
                    if imp.name:
                        imports[dll_name].append(imp.name.decode())
            
            if imports:
                print(f"\n  IMPORTACIONES ({len(imports)} DLLs):")
                for dll, funcs in sorted(imports.items())[:15]:
                    print(f"     {dll}")
                    for f in funcs:
                        print(f"       - {f}")
        except Exception as e:
            print(f"\n  Imports: {e}")
            
    except Exception as e:
        print(f"  Error: {e}")

BASE = os.path.dirname(os.path.abspath(__file__))

# Analizar las DLLs clave
analyze(os.path.join(BASE, "ER296", "idrsocr15.dll"), "idrsocr15.dll (OCR Engine)")
analyze(os.path.join(BASE, "Soporte", "OCRLibraryInf.dll"), "OCRLibraryInf.dll (Bridge API)")

print("\n\n")
print("="*60)
print("  CONCLUSION")
print("="*60)
print("""
Las DLLs iDRS15 usan EXPORTS ORDINALES (sin nombres).
Esto significa que NO se pueden llamar directamente con
ctypes porque no sabemos que funcion es cual.

La estrategia correcta es:

  OPCION A: USAR OCRLibraryInf.dll (si tiene named exports)
  
  OPCION B: CREAR UN WRAPPER VIA el plugin ROAOCR
            (el plugin comunica via PI_Plugin interface)
  
  OPCION C: USAR DIRECTAMENTE EL COM DEL ENGINE
            (AcroExch.App + PDDoc con OCR)
  
  OPCION D: INGENIERIA INVERSA MAS PROFUNDA
            (desensamblar con IDA/Ghidra)
""")
input("Presiona Enter...")
