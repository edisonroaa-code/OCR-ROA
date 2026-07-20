import pefile
from pathlib import Path
for name in ['idrskrn15.dll','idrsocr15.dll','idrsprepro15.dll','idrsdocout15.dll']:
    path = Path(name)
    pe = pefile.PE(str(path))
    print(name)
    if hasattr(pe, 'DIRECTORY_ENTRY_EXPORT'):
        syms = [s for s in pe.DIRECTORY_ENTRY_EXPORT.symbols if s.name]
        names = []
        for s in syms:
            try:
                names.append(s.name.decode('ascii'))
            except Exception:
                names.append(str(s.name))
        for needle in ['drsE_create_drs','drsE_load_ocr','drsD_create_drs','drsD_destroy_drs','drsD_set_env_ocr','drsD_reset_env_ocr','drsD_set_env_lex','drsD_load_lex','drsD_set_env_asianocr','drsOcr','drsZones','drsFormat','FMT_Init','FMT_SetOutputStream','bi_setup','bi_gradl_do','asian_create_engine','asian_ocr_initialize']:
            if any(n == needle for n in names):
                print(' ', needle)
        print('---')
