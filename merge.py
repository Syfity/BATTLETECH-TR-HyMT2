#!/usr/bin/env python3
import csv,json,hashlib,sys
from pathlib import Path
inp=Path(sys.argv[1]); out=Path(sys.argv[2]); cache_dir=Path(sys.argv[3])
cache={}
for p in sorted(cache_dir.glob('cache-*.jsonl')):
    if not p.exists(): continue
    for ln in p.read_text(encoding='utf-8').splitlines():
        try:
            o=json.loads(ln); cache[o['h']]=o['tr']
        except Exception: pass
with inp.open(encoding='utf-8',newline='') as f:
    reader=csv.DictReader(f); fields=reader.fieldnames; rows=list(reader)
if fields!=['KEY','de-DE']:
    raise SystemExit(f'Beklenmeyen CSV sütunları: {fields}')
changed=0
for r in rows:
    de=r['de-DE']; h=hashlib.sha256(de.encode('utf-8')).hexdigest()
    if h in cache and cache[h] != de:
        r['de-DE']=cache[h]; changed+=1
with out.open('w',encoding='utf-8',newline='') as f:
    w=csv.DictWriter(f,fieldnames=fields,lineterminator='\n',quoting=csv.QUOTE_MINIMAL)
    w.writeheader(); w.writerows(rows)
print(f'records={len(rows)} translated_records={changed} cache_entries={len(cache)}')
