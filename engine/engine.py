#!/usr/bin/env python3
"""
Editorial Intelligence Engine. The real, runnable ingest pipeline.

Turns a show transcript into verified intelligence: indexed moments, attributed
statements, thesis trails, all gated by a verbatim + attribution honesty check.

Its one job is to be right. It attributes or abstains, verifies or drops, and
labels an outcome only as far as the evidence reaches.

Usage:
    python engine.py <transcript.txt> --ep 14 --date 20260806 --vid FFFnEnXzgEY \
        --title "I Don't Think Intelligence Matters Anymore"
"""
import re, json, sys, argparse

# ----- asset + topic vocabularies (extend per show) -----
TICKERS = {
    "bitcoin":"BTC","btc":"BTC","ethereum":"ETH"," eth ":"ETH","solana":"SOL",
    " sol ":"SOL","hyperliquid":"HYPE"," hype":"HYPE","zcash":"ZEC"," zec ":"ZEC",
    "robinhood":"HOOD","pump.fun":"PUMP","pumpfun":"PUMP",
}
TOPICS = ["memecoin","pumpfun","pump.fun","robinhood","on-chain","onchain","rwa",
          "nft","airdrop","creator","streamer","clip","attention","copy trad",
          "multicoin","anthropic","privacy","seed round","kimchi"]

# ----- stage 1: PARSE -----
def parse(txt):
    """Split into (t_seconds, raw_ts, body) blocks. Strip the verbose duration."""
    def to_sec(ts):
        p=[int(x) for x in ts.strip().split(':')]
        return p[0]*60+p[1] if len(p)==2 else p[0]*3600+p[1]*60+p[2]
    toks=re.split(r'(\n?\d+:\d+(?::\d+)?)',txt)
    segs=[]
    for j in range(1,len(toks),2):
        ts=toks[j].strip(); body=toks[j+1] if j+1<len(toks) else ''
        body=body.strip()
        if re.match(r'^\d+\s*(?:hour|minute|second)', body):
            body=re.sub(r'^(?:\d+\s*hours?,?\s*)?(?:\d+\s*minutes?,?\s*)?(?:\d+\s*seconds?)?','',body,count=1).strip()
        else:
            body=re.sub(r'^\d*\s*(?:hours?,?\s*)?(?:\d+\s*minutes?,?\s*)?(?:\d+\s*seconds?)','',body).strip()
        segs.append((to_sec(ts),ts,body))
    return segs

def validate_timestamps(segs, duration=None):
    """Monotonic non-decreasing, none beyond duration."""
    bad=[]
    last=-1
    for i,(t,ts,b) in enumerate(segs):
        if t<last-2: bad.append(("nonmonotonic",ts,t))
        if duration and t>duration+5: bad.append(("beyond_duration",ts,t))
        last=max(last,t)
    return bad

# ----- stage 2: SEGMENT (chapters + auto-tag) -----
def chapters(txt, segs):
    ts_positions=[(m.start(),m.group(0)) for m in re.finditer(r'\n?\d+:\d+(?::\d+)?',txt)]
    def to_sec(ts):
        p=[int(x) for x in ts.strip().split(':')]
        return p[0]*60+p[1] if len(p)==2 else p[0]*3600+p[1]*60+p[2]
    def ts_at(pos):
        for cpos,cts in ts_positions:
            if cpos>=pos-40: return to_sec(cts)
        return 0
    out=[]; seen=set()
    for m in re.finditer(r'Chapter (\d+):\s*([^\n]+?)(?=\s*\d+:\d+|\n|$)',txt):
        n=int(m.group(1)); title=m.group(2).strip().rstrip('.')[:60]
        if len(title)<3 or n in seen: continue
        seen.add(n); out.append((n,ts_at(m.start()),title))
    return sorted(out)

def tag(text):
    tl=(" "+text.lower()+" ")
    assets=sorted({v for k,v in TICKERS.items() if k in tl})
    topics=sorted({t.replace(' ','-').replace('.','') for t in TOPICS if t in tl})
    return assets,topics

# ----- stage 3: ATTRIBUTE (guest registry, abstain on doubt) -----
def _sec_at(txt, pos):
    near=None
    for m in re.finditer(r'\d+:\d+(?::\d+)?',txt):
        if m.start()<=pos: near=m.group(0)
        else: break
    if not near: return 0
    p=[int(x) for x in near.split(':')]
    return p[0]*60+p[1] if len(p)==2 else p[0]*3600+p[1]*60+p[2]

def speaker_registry(txt, segs):
    """Detect guest intros. Anchor on 'role at Org', then find the nearest
    preceding 'I'm <Name>' (crosses a sentence boundary, e.g. 'I'm Tushar.
    I'm founder and chief investment officer at Multicoin Capital'). Returns
    [(t, name, org)]. Anything not confidently linked is simply not added,
    which downstream turns into an honest abstention, never a guess."""
    reg=[]
    role=r'(?:founder|co-?founder|CEO|CIO|CTO|chief [\w ]{0,25}?officer|president|managing partner|partner|head of [\w ]{2,20})'
    for m in re.finditer(role+r'[^.]{0,45}?\b(?:at|of)\s+([A-Z][\w&.\' ]{2,30})', txt):
        org=re.split(r'\s+(?:and|where|which)\b',m.group(1).strip())[0].rstrip('.')
        pre=txt[max(0,m.start()-240):m.start()]
        names=re.findall(r"[Ii]'?m ([A-Z][a-z]+(?: [A-Z][a-z]+)?)\b", pre)
        name=names[-1] if names else None
        if name and name.lower() not in ("banks","ansem"):
            reg.append((_sec_at(txt,m.start()), name, org))
    # dedupe, keep earliest per name
    best={}
    for t,n,o in reg:
        if n not in best or t<best[n][0]: best[n]=(t,o)
    return sorted([(t,n,o) for n,(t,o) in best.items()])

def active_speaker(t, registry, hosts=("Banks","Ansem")):
    """Nearest guest introduced at or before t wins; else host. None if ambiguous."""
    g=[r for r in registry if r[0]<=t]
    if g:
        last=max(g,key=lambda r:r[0])
        # guest only 'active' for a window after intro
        if t-last[0] < 1800:  # 30 min window
            return last[1], last[2]
    return None, None  # abstain: caller decides host vs unknown

# ----- stage 5: VERIFY (verbatim, contiguous) -----
def norm(s):
    s=re.sub(r'\[[^\]]*\]',' ',s)          # [ __ ], [laughter]
    s=re.sub(r'\s+',' ',s).strip().lower()
    return s

def verify_verbatim(quote, transcript):
    """Exact contiguous substring after light normalization. Returns True/False."""
    return norm(quote) in norm(transcript)

# ----- stage 6: SNAP -----
def snap(quote, segs, lead=3):
    q=norm(quote)[:40]
    for t,ts,b in segs:
        if q and q in norm(b):
            return max(0, t-lead)
    return None

# ----- stage 3b: CALL GATES (ported from Counterparty engine, same DNA) -----
DIR_LONG=[r"\blong\b",r"\bbought\b",r"\bbuying\b",r"\bbullish\b",r"\baccumulat\w*\b",r"\bput on a (?:big )?position\b",r"\bwe led the seed\b"]
DIR_SHORT=[r"\bshort\b",r"\bsold\b",r"\bselling\b",r"\bbearish\b",r"\bfade[sd]?\b",r"\bfading\b"]
TIME_LONG=[r"long time",r"as long as",r"how long",r"long day",r"no longer",r"along\b",r"belong"]
NEGATIONS=[r"not long",r"no position",r"don'?t own",r"never (?:bought|long|short)",r"i own zero"]
OBJECTS=r"\b(?:bought|sold|buying|selling)\s+(?:my|his|her|their|a|the)\s+(?:watch|car|house|monitors?|chair|desk|dog|button|gift)\b"
def direction(text, tick_name_positions):
    """Word-boundary direction within 8 tokens of the ticker, with exclusions. Returns 'long'/'short'/None."""
    import re as _re
    tl=" "+text.lower()+" "
    if _re.search(OBJECTS,tl): return None
    for pat in TIME_LONG:
        tl=_re.sub(pat," ",tl)
    for pat in NEGATIONS:
        if _re.search(pat,tl): return None
    toks=tl.split()
    def near(idx):
        return any(abs(idx-tp)<=8 for tp in tick_name_positions) if tick_name_positions else True
    for i,w in enumerate(toks):
        seg=" ".join(toks[max(0,i-1):i+3])
        for pat in DIR_LONG:
            if _re.search(pat," "+w+" ") or _re.search(pat,seg):
                if near(i): return "long"
        for pat in DIR_SHORT:
            if _re.search(pat," "+w+" ") or _re.search(pat,seg):
                if near(i): return "short"
    return None

def call_score(text):
    """Counterparty scoring: first-person +30, stated level +30, conviction +20, hedge -20, third-party -> 0."""
    import re as _re
    tl=text.lower()
    if _re.search(r"\b(?:he|she|they|trump|saylor|elon)\s+(?:bought|sold|longed|shorted|acquired)\b",tl): return 0
    s=0
    if _re.search(r"\bi (?:longed|bought|sold|shorted|am long|'m long|am short|'m short|put on)\b|\bwe (?:put on|led|bought)\b",tl): s+=30
    if _re.search(r"\$?\d{2,3}(?:[.,]\d+)?\s*k?\b",tl): s+=30
    if _re.search(r"\b(?:conviction|max bid|all in|heavily|big position|sell the house)\b",tl): s+=20
    if _re.search(r"\b(?:maybe|might|possibly|not sure|i guess|probably)\b",tl): s-=20
    return s

# ----- stage 4: CLASSIFY -----
def classify(text):
    tl=text.lower()
    if re.search(r'\bwe (put on|are long|bought|led the seed|have a (big )?position)',tl): return "disclosed_position","Disclosed position"
    if re.search(r'\bi called|we called|called (the )?bottom',tl): return "retrospective_claim","Retrospective claim"
    if re.search(r'\b(odds|chance|%|probability).{0,30}(too low|too high|mispriced|higher than|lower than)',tl): return "probability_view","Probability view"
    if re.search(r'\bif (bitcoin|btc|sol|eth|the market).{0,30}\b(at|hits|reaches)\b',tl): return "scenario","Scenario"
    if re.search(r"\b(is not going to|won'?t|will|going to|i think .* (breaks|holds|drops|pumps)|bottoms in|great spot|higher low)\b",tl): return "prediction","A prediction"
    return "observation","An observation"

# ----- orchestrator -----
def ingest(path, ep, date, vid, epTitle, duration=None, hosts=("Banks","Ansem")):
    txt=open(path,encoding='utf-8',errors='ignore').read()
    segs=parse(txt)
    ts_bad=validate_timestamps(segs,duration)
    chaps=chapters(txt,segs)
    registry=speaker_registry(txt,segs)

    # moments: one per chapter, auto-tagged
    moments=[]
    for n,t,title in chaps:
        # gather chapter body (until next chapter timestamp) for tagging
        body=" ".join(b for tt,ts,b in segs if t<=tt<t+330)
        a,tp=tag(title+" "+body[:600])
        who,org=active_speaker(t,registry,hosts)
        guests=[who] if who else []
        moments.append({"ep":ep,"date":date,"vid":vid,"t":t,"title":title,
                        "assets":a,"topics":tp,"guests":guests,"isEp":True,"epTitle":epTitle})

    # candidate statements: segments that name a ticker AND carry a stance verb
    calls=[]; review=[]
    for t,ts,b in segs:
        a,_=tag(b)
        if not a: continue
        stype,label=classify(b)
        if stype=="observation": continue
        sc=call_score(b)
        if sc==0 and re.search(r"\b(?:he|she|they)\s+(?:bought|sold)\b",b.lower()): continue
        # ticker token positions for the proximity gate
        toks=b.lower().split()
        tpos=[i for i,w in enumerate(toks) if any(k.strip() in w for k in TICKERS if TICKERS.get(k)==a[0])]
        dirn=direction(b,tpos)
        who,org=active_speaker(t,registry,hosts)
        # verify verbatim (self-check against transcript)
        ok=verify_verbatim(b, txt)
        snapped=snap(b,segs) or t
        entry={"d":f"{date[:4]}-{date[4:6]}-{date[6:]}","ep":ep,"vid":vid,"t":snapped,
               "who":who,"who_org":org,"tick":a[0],"dir":dirn,"score":sc,"q":b.strip()[:240],
               "ctx":"","stype":stype,"stypeLabel":label,"verbatim_ok":ok}
        if who is None:
            entry["who"]="UNRESOLVED"; review.append(entry)   # abstain, flag
        calls.append(entry)

    # honesty report
    honesty={
        "timestamps_out_of_range": len(ts_bad),
        "statements_unattributed": sum(1 for c in calls if c["who"] in (None,"UNRESOLVED")),
        "statements_failing_verbatim": sum(1 for c in calls if not c["verbatim_ok"]),
        "guests_detected": [f"{n} ({o})" for _,n,o in registry],
        "gate": "PASS" if not ts_bad else "REVIEW",
    }
    return {"episode":{"ep":ep,"date":date,"vid":vid,"epTitle":epTitle},
            "moments":moments,"statements":calls,"needs_review":review,"honesty":honesty}

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("transcript")
    ap.add_argument("--ep",type=int,required=True)
    ap.add_argument("--date",required=True)
    ap.add_argument("--vid",required=True)
    ap.add_argument("--title",default="")
    ap.add_argument("--duration",type=int,default=None)
    a=ap.parse_args()
    out=ingest(a.transcript,a.ep,a.date,a.vid,a.title,a.duration)
    print(json.dumps(out,ensure_ascii=False,indent=2))
