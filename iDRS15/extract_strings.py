from pathlib import Path
import re
root = Path(r'd:\APLICATIVOS\ROA OCR\iDRS15')
for path in sorted(root.glob('*.dll')):
    data = path.read_bytes()
    strings = re.findall(rb'[\x20-\x7e]{4,}', data)
    print('===', path.name, '===')
    seen = []
    for s in strings:
        text = s.decode('latin1', errors='ignore')
        if 'IDRS' in text or 'OCR' in text or 'drs' in text or 'asian' in text or 'arab' in text or 'lex' in text or 'FMT_' in text or 'bi_' in text:
            if text not in seen:
                seen.append(text)
    for t in seen[:120]:
        print(t)
    print()
