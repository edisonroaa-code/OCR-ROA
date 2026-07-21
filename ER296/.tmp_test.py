import ctypes
from pathlib import Path
import os

root = Path('.').resolve()
dll = ctypes.WinDLL(str(root / 'idrsocr15.dll'))
for name in ['drsE_create_drs','drsD_destroy_drs','drsE_load_ocr','drsD_set_env_ocr','drsD_set_env_lex','drsD_load_lex']:
    try:
        fn = getattr(dll, name)
        fn.restype = ctypes.c_void_p
        fn.argtypes = []
        try:
            result = fn()
            print(name, '->', hex(result))
        except Exception as e:
            print(name, 'ERROR', repr(e))
    except Exception as e:
        print(name, 'MISSING', repr(e))
