#!/usr/bin/env python3
import csv,re,sys
CTRL='\x1f'
HTML_TAG_RE=re.compile(r'''</?[A-Za-z][^>]*>|<#[0-9A-Fa-f]{6,8}>''')
BRACE_RE=re.compile(r'''\{[^{}]+\}''')
PRINTF_RE=re.compile(r'''%\d*\$?[sdif]''')
ESCAPE_RE=re.compile(r'''\\[nrt]''')
URL_RE=re.compile(r'''(?:https?://|file://)\S+''')
LINK_PREFIX_RE=re.compile(r'''\[\[.*?\x1f''')
SIMPLE_TECH_BRACKET_RE=re.compile(r'''\[(?:durationRemaining|pluralDurationType|numberOfUnitsToSurviveRemaining|numberOfUnitsToDefend|numberOfUnitsToDefendRemaining|AMT|GENERIC VO)\]''')
GERMAN=re.compile(r'\b(?:aber|auch|auf|aus|bei|das|der|die|dies|ein|eine|für|haben|hier|ich|ist|kann|mit|nicht|noch|oder|sich|sie|sind|und|von|werden|wie|wir|wird|zu|zum|zur)\b',re.I)

def sig(t):
    x=[]
    for name,rx in [('tag',HTML_TAG_RE),('brace',BRACE_RE),('printf',PRINTF_RE),('escape',ESCAPE_RE),('url',URL_RE),('link',LINK_PREFIX_RE),('techbr',SIMPLE_TECH_BRACKET_RE)]: x += [(name,m) for m in rx.findall(t)]
    x += [('close',']]') for _ in re.finditer(r'\]\]',t)]
    x += [('sep',CTRL) for _ in range(t.count(CTRL))]
    return sorted(x)

def read(p):
    with open(p,encoding='utf-8',newline='') as f:
        r=csv.DictReader(f); return r.fieldnames,list(r)
fa,a=read(sys.argv[1]); fb,b=read(sys.argv[2]); errs=[]; warnings=[]
if fa!=fb: errs.append(f'Sütunlar farklı: {fa} != {fb}')
if len(a)!=len(b): errs.append(f'Kayıt sayısı farklı: {len(a)} != {len(b)}')
for i,(x,y) in enumerate(zip(a,b),2):
    if x.get('KEY')!=y.get('KEY'): errs.append(f'{i}: KEY değişti')
    if sig(x.get('de-DE',''))!=sig(y.get('de-DE','')): errs.append(f'{i}: teknik yapı/token uyuşmuyor')
    k=(x.get('KEY') or '').lower()
    if not (k.startswith('(hidden)') or k.startswith('(debug')) and x.get('de-DE')==y.get('de-DE') and GERMAN.search(x.get('de-DE','')): warnings.append(f'{i}: Almanca kalmış olabilir')
if errs:
    print('\n'.join(errs[:500])); raise SystemExit(2)
print(f'OK: {len(a)} kayıt; sütunlar, KEY eşleşmesi ve kayıt-bazlı teknik yapı doğrulaması başarılı.')
print(f'UYARI_TARAMASI: Almanca kalmış olabilecek kayıt={len(warnings)}')
if warnings: open('validation_warnings.txt','w',encoding='utf-8').write('\n'.join(warnings)+'\n')
