import pefile
from pathlib import Path
for name in ['idrskrn15.dll','idrsocr15.dll','idrsprepro15.dll','idrsdocout15.dll','idrsasian215.dll']:
    path = Path(name)
    pe = pefile.PE(str(path))
    print('===', name, '===')
    if hasattr(pe, 'DIRECTORY_ENTRY_EXPORT'):
        syms = [s for s in pe.DIRECTORY_ENTRY_EXPORT.symbols if s.name]
        out = []
        for s in syms:
            try:
                out.append(s.name.decode('ascii'))
            except Exception:
                out.append(str(s.name))
        for item in out:
            if any(k in item.lower() for k in ['drs','ocr','lex','asian','pre','fmt','bi_','create','destroy','load','set','get','save','free','env','image','lang','result','session']):
                print(item)
        print('total exports:', len(out))
    print()
