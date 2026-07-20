import os
from pathlib import Path
try:
    import pefile
except Exception as e:
    print('pefile import failed:', e)
    raise SystemExit(1)
root = Path(r'd:\APLICATIVOS\ROA OCR\iDRS15')
for dll in sorted(root.glob('*.dll')):
    print('===', dll.name, '===')
    try:
        pe = pefile.PE(str(dll))
        print('Machine:', hex(pe.FILE_HEADER.Machine))
        print('Sections:', len(pe.sections))
        print('Imports:')
        for entry in getattr(pe, 'DIRECTORY_ENTRY_IMPORT', []):
            print(' -', entry.dll.decode(errors='ignore'))
        print('Exports:', len(getattr(pe.DIRECTORY_ENTRY_EXPORT, 'symbols', [])) if hasattr(pe, 'DIRECTORY_ENTRY_EXPORT') else 0)
        if hasattr(pe, 'DIRECTORY_ENTRY_EXPORT'):
            for sym in pe.DIRECTORY_ENTRY_EXPORT.symbols[:20]:
                print('  ', hex(sym.address), sym.name.decode(errors='ignore') if sym.name else None)
        print('Version info:')
        for k, v in sorted(getattr(pe, 'FileInfo', [])):
            pass
        try:
            for entry in pe.FileInfo:
                for st in entry:
                    if hasattr(st, 'Key') and hasattr(st, 'StringTable'):
                        for string in st.StringTable:
                            for k, val in string.items():
                                print(' ', k, val)
        except Exception:
            pass
    except Exception as e:
        print('ERROR', e)
    print()
