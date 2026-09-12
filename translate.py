#!/usr/bin/env python3
import argparse, csv, json, re, hashlib, time, urllib.request
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

CTRL_SEP = "\x1f"
HTML_TAG_RE = re.compile(r'''</?[A-Za-z][^>]*>|<#[0-9A-Fa-f]{6,8}>''')
BRACE_RE = re.compile(r'''\{[^{}]+\}''')
PRINTF_RE = re.compile(r'''%\d*\$?[sdif]''')
ESCAPE_RE = re.compile(r'''\\[nrt]''')
URL_RE = re.compile(r'''(?:https?://|file://)\S+''')
SIMPLE_TECH_BRACKET_RE = re.compile(r'''\[(?:durationRemaining|pluralDurationType|numberOfUnitsToSurviveRemaining|numberOfUnitsToDefend|numberOfUnitsToDefendRemaining|AMT|GENERIC VO)\]''')
LINK_PREFIX_RE = re.compile(r'''\[\[.*?\x1f''')

STYLE = (
    "BATTLETECH (2018) için profesyonel Türkçe oyun yerelleştirmesi. Askerî bilimkurgu, paralı askerlik ve taktik savaş tonu. "
    "Arayüz kısa ve doğal; diyaloglar karaktere ve rütbeye uygun; anlatı akıcı Türkçe olmalı. "
    "BattleTech evrenindeki özel adları ve kanonik ürün/araç/karakter/gezegen adlarını çevirmeyin."
)
CONTEXT = (
    "BATTLETECH by Harebrained Schemes, 3025 döneminde geçer. Oyuncu bir paralı asker birliğini ve BattleMech'leri yönetir. "
    "Bağlam: Inner Sphere, Periphery, Great Houses, Aurigan Reach, House Arano, Aurigan Restoration; MechWarrior, BattleMech, "
    "lance, salvage, contracts, heat, armor, stability ve benzeri BattleTech terminolojisi."
)

def is_non_player(key: str, text: str) -> bool:
    k=(key or '').strip().lower(); t=(text or '').strip().lower()
    if not text: return True
    return k.startswith('(hidden)') or k.startswith('(debugmode)') or k.startswith('(debug)') or t.startswith('(hidden)') or t.startswith('(debug-modus)')

def _mask_regex(text, regex, tokens):
    def repl(m):
        idx=len(tokens); tokens.append(m.group(0)); return f"__BT_PH_{idx:04d}__"
    return regex.sub(repl, text)

def mask_tokens(text: str):
    tokens=[]
    text=_mask_regex(text, LINK_PREFIX_RE, tokens)
    def close_repl(m):
        idx=len(tokens); tokens.append(m.group(0)); return f"__BT_PH_{idx:04d}__"
    text=re.sub(r'\]\]', close_repl, text)
    for rx in (URL_RE, HTML_TAG_RE, BRACE_RE, PRINTF_RE, ESCAPE_RE, SIMPLE_TECH_BRACKET_RE):
        text=_mask_regex(text, rx, tokens)
    def sep_repl(_m):
        idx=len(tokens); tokens.append(CTRL_SEP); return f"__BT_PH_{idx:04d}__"
    text=re.sub(CTRL_SEP, sep_repl, text)
    return text,tokens

def unmask(text: str, tokens):
    out=text
    for i,tok in enumerate(tokens): out=out.replace(f"__BT_PH_{i:04d}__", tok)
    return out

def structure_signature(text: str):
    sig=[]
    sig += [('tag',x) for x in HTML_TAG_RE.findall(text)]
    sig += [('brace',x) for x in BRACE_RE.findall(text)]
    sig += [('printf',x) for x in PRINTF_RE.findall(text)]
    sig += [('escape',x) for x in ESCAPE_RE.findall(text)]
    sig += [('url',x) for x in URL_RE.findall(text)]
    sig += [('techbr',x) for x in SIMPLE_TECH_BRACKET_RE.findall(text)]
    sig += [('link',x) for x in LINK_PREFIX_RE.findall(text)]
    sig += [('linkclose',']]') for _ in re.finditer(r'\]\]', text)]
    sig += [('sep',CTRL_SEP) for _ in range(text.count(CTRL_SEP))]
    return sorted(sig)

def relevant_glossary(src: str, glossary: dict):
    low=src.casefold(); items=[]
    for k,v in glossary.items():
        if k.casefold() in low: items.append(f"{k} translates to {v}")
    return items[:60]

def build_prompt(src: str, glossary: dict):
    terms='\n'.join(relevant_glossary(src,glossary))
    return (
        f"[Background Information]\n{CONTEXT}\n\n"
        f"[Source Text]\n{src}\n\n"
        f"[Translation Tasks]\n"
        f"1. Translate the German [Source Text] into Turkish.\n"
        f"2. Translation style must strictly conform to: {STYLE}\n"
        f"3. Every token matching __BT_PH_XXXX__ is protected technical data. Copy every protected token exactly once and never translate, remove, reorder, split, or modify it.\n"
        f"4. Preserve numbers, percentages and measurement values unless Turkish punctuation is clearly user-facing prose.\n"
        + (f"5. Reference terminology:\n{terms}\n" if terms else "") +
        f"6. Output ONLY the Turkish translation without explanations, labels, quotation wrappers, or commentary."
    )

def api_completion(server, prompt, max_tokens=4096, timeout=900):
    payload={"model":"Hy-MT2-7B","messages":[{"role":"user","content":prompt}],"temperature":0.7,"top_p":0.6,"top_k":20,"repeat_penalty":1.05,"max_tokens":max_tokens,"stream":False}
    data=json.dumps(payload,ensure_ascii=False).encode('utf-8')
    req=urllib.request.Request(server.rstrip('/')+'/v1/chat/completions',data=data,headers={'Content-Type':'application/json'},method='POST')
    with urllib.request.urlopen(req,timeout=timeout) as r: obj=json.loads(r.read().decode('utf-8'))
    return obj['choices'][0]['message']['content'].strip()

def clean_output(text: str):
    out=text.strip()
    out=re.sub(r'^```(?:text|turkish|tr)?\s*','',out,flags=re.I)
    out=re.sub(r'\s*```$','',out)
    out=re.sub(r'^\s*(?:Çeviri|Türkçe|Translation)\s*:\s*','',out,flags=re.I)
    return out.strip()

def translate_one(server, de, glossary):
    masked,tokens=mask_tokens(de); prompt=build_prompt(masked,glossary); last=''
    for attempt in range(3):
        try:
            if attempt==0: tr=api_completion(server,prompt)
            else:
                repair=("Translate the following German BATTLETECH game text into natural Turkish. Output ONLY the translation. Every __BT_PH_XXXX__ token is immutable: copy all of them exactly once and do not reorder them.\n\n"+masked)
                tr=api_completion(server,repair)
            tr=unmask(clean_output(tr),tokens)
            if tr and structure_signature(de)==structure_signature(tr): return tr,None
        except Exception as e:
            last=str(e); time.sleep(2*(attempt+1))
    return de,last or 'Yapısal doğrulama başarısız'

def load_cache(path):
    cache={}; p=Path(path)
    if not p.exists(): return cache
    for line in p.read_text(encoding='utf-8').splitlines():
        try:
            o=json.loads(line); cache[o['h']]=o['tr']
        except Exception: pass
    return cache

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--input',required=True); ap.add_argument('--glossary',required=True); ap.add_argument('--server',default='http://127.0.0.1:8080'); ap.add_argument('--shard',type=int,default=0); ap.add_argument('--shards',type=int,default=1); ap.add_argument('--cache',required=True); ap.add_argument('--failures',required=True); ap.add_argument('--workers',type=int,default=2); args=ap.parse_args()
    glossary=json.load(open(args.glossary,encoding='utf-8')); cache=load_cache(args.cache)
    with open(args.input,encoding='utf-8',newline='') as f: rows=list(csv.DictReader(f))
    unique={}
    for r in rows:
        de=r.get('de-DE',''); key=r.get('KEY','')
        if is_non_player(key,de): continue
        h=hashlib.sha256(de.encode('utf-8')).hexdigest()
        if int(h[:16],16)%args.shards==args.shard: unique.setdefault(h,de)
    pending=[(h,de) for h,de in unique.items() if h not in cache]
    print(f"shard {args.shard}: total={len(unique)} cached={len(unique)-len(pending)} pending={len(pending)}",flush=True)
    cache_f=open(args.cache,'a',encoding='utf-8'); fail_f=open(args.failures,'a',encoding='utf-8'); done=0
    with ThreadPoolExecutor(max_workers=max(1,args.workers)) as ex:
        futs={ex.submit(translate_one,args.server,de,glossary):(h,de) for h,de in pending}
        for fut in as_completed(futs):
            h,de=futs[fut]
            try: tr,err=fut.result()
            except Exception as e: tr,err=de,str(e)
            cache[h]=tr; cache_f.write(json.dumps({'h':h,'de':de,'tr':tr},ensure_ascii=False)+'\n'); cache_f.flush()
            if err: fail_f.write(json.dumps({'h':h,'de':de,'error':err},ensure_ascii=False)+'\n'); fail_f.flush()
            done+=1
            if done%25==0 or done==len(pending): print(f"shard {args.shard}: {done}/{len(pending)}",flush=True)
    cache_f.close(); fail_f.close()

if __name__=='__main__': main()
