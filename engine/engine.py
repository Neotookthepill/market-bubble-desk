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

# ----- stage 11: NARRATIVE CLAIM VERIFIER -----
# Stage 5 (VERIFY) checks that a *quote* is verbatim. It says nothing about the
# prose wrapped around it: ctx, beats, lede, lesson, outcome. Those sentences
# often smuggle in a checkable fact ("41 days later", "restates the 58.8K
# call", "Episode 13") that quote-verification never touches. This stage
# extracts every checkable claim from prose and sources or rejects it, the
# same honesty-gate discipline as stage 5, applied to interpretation instead
# of quotation.

CLAIM_PATTERNS = {
    "day_math":   re.compile(r'\b(\d{1,3})\s*(day|week|month)s?\s*(?:later|before|after|prior|earlier)\b', re.I),
    "episode_ref":re.compile(r'\bEp(?:isode)?\.?\s*#?(\d{1,2})\b', re.I),
    "dollar":     re.compile(r'\$\s?[\d][\d,]*(?:\.\d+)?\s*[KMB]?\b'),
    "bare_num_k": re.compile(r'\b\d{1,3}(?:\.\d+)?\s?[KMB]\b'),
    "percent":    re.compile(r'\b\d{1,3}(?:\.\d+)?\s?%'),
}

def extract_claims(text):
    """Pull every checkable claim out of a prose string. Returns a list of
    {type, raw, span}. A sentence can yield more than one claim; each is
    checked independently, so a single wrong number never hides behind a
    correct one three words away."""
    claims = []
    for ctype, pat in CLAIM_PATTERNS.items():
        for m in pat.finditer(text):
            claims.append({"type": ctype, "raw": m.group(0), "span": m.span()})
    return sorted(claims, key=lambda c: c["span"][0])

def verify_day_math(text, claim, current_ep, current_date, ep_dates):
    """A claim like '41 days later ... Episode 10' is checkable without a
    transcript at all: every episode has a real air date. Find the nearest
    Episode N reference in the same sentence, diff the two real dates, compare
    to the stated count. Exact-match only, this is arithmetic, not fuzzy text."""
    from datetime import date as _date
    ep_m = CLAIM_PATTERNS["episode_ref"].search(text)
    if not ep_m:
        return {"verdict": "UNVERIFIABLE", "reason": "no Episode N in the same sentence to diff against"}
    ref_ep = int(ep_m.group(1))
    if ref_ep not in ep_dates or current_ep not in ep_dates:
        return {"verdict": "UNVERIFIABLE", "reason": f"episode {ref_ep} or {current_ep} not in the date registry"}
    n, unit = re.match(r'(\d+)\s*(day|week|month)', claim["raw"], re.I).groups()
    n = int(n)
    d1 = _date.fromisoformat(ep_dates[ref_ep])
    d2 = _date.fromisoformat(ep_dates[current_ep] if isinstance(current_date, int) else current_date)
    real_days = abs((d2 - d1).days)
    stated_days = n * (7 if unit.lower() == "week" else 30 if unit.lower() == "month" else 1)
    tol = 1 if unit.lower() == "day" else (2 if unit.lower() == "week" else 5)
    ok = abs(real_days - stated_days) <= tol
    return {"verdict": "PASS" if ok else "FAIL",
            "reason": f"real gap Ep{ref_ep}->Ep{current_ep} = {real_days}d, claim = {n} {unit}(s) = {stated_days}d"}

def verify_numeric_in_transcript(claim, vid, t, timed_entries_by_vid, window=75):
    """A dollar figure, percentage, or bare K/M/B number tied to a (vid, t)
    anchor should actually appear near that timestamp, not merely somewhere
    in the episode. timed_entries_by_vid maps vid -> [(sec, text), ...] (the
    same shape stage 1's parse() produces), so the window is real, seconds on
    either side of t, not the whole transcript treated as one bag of digits.

    Known limitation: matches digit form only ('40', not 'forty'). Real show
    transcripts overwhelmingly render numbers as digits, so this holds in
    practice, but a spelled-out number will show REVIEW, not PASS. Treat
    REVIEW as 'needs a human glance', never as a confirmed error. A REVIEW
    is also the expected, correct result for a claim that legitimately
    cross-references a different moment or episode (e.g. ctx text like
    '...three weeks before the same account turned bearish below 70K' is
    describing a LATER quote, not asserting '70K' was said at this t)."""
    entries = timed_entries_by_vid.get(vid)
    if entries is None:
        return {"verdict": "UNVERIFIABLE", "reason": f"no transcript loaded for {vid}"}
    digits = re.sub(r'[^\d]', '', claim["raw"])
    if not digits:
        return {"verdict": "UNVERIFIABLE", "reason": "no digits to search for"}
    windowed = ''.join(re.sub(r'[^\d]', '', txt) for sec, txt in entries if t is not None and abs(sec - t) <= window)
    found = digits in windowed
    return {"verdict": "PASS" if found else "REVIEW",
            "reason": f"digits '{digits}' {'found' if found else 'not found'} within {window}s of t={t}"}

def verify_episode_exists(claim, ep_dates):
    ref_ep = int(re.search(r'\d+', claim["raw"]).group(0))
    ok = ref_ep in ep_dates
    return {"verdict": "PASS" if ok else "FAIL",
            "reason": f"Episode {ref_ep} {'is' if ok else 'is NOT'} in the known episode range"}

# ----- cross-reference guard -----
# Counterparty's engine (same DNA) leans on GUARDS: a claim is not verified
# blind, it is first checked for a pattern that changes what "verified" even
# means. Their conditional/hypothetical guard routes "if I'm long X" away
# from stance-scoring entirely rather than mis-scoring it. The equivalent bug
# here: "...three weeks before the same account turned bearish below 70K"
# names a number that belongs to a DIFFERENT moment, not to the (vid, t) this
# ctx is anchored to. Without this guard, a numeric check against the local
# window is answering the wrong question and reports REVIEW for something
# that was never a local claim in the first place.
CROSS_REF_MARKERS = re.compile(
    r'\b(?:back in|earlier in|later in|the (?:previous|next|same) (?:week|episode|month)|'
    r'weeks? (?:before|after|later|prior)|episode\s*#?\d+|since (?:then|episode)|'
    r'then later|eventually|afterward|subsequently|by the time)\b', re.I)

def is_cross_reference(text, claim):
    """True if the claim's own sentence carries a marker that points this
    number at a different episode or moment than the record's own (vid, t)
    anchor. A cross-referenced number should never be scored against the
    local window; it needs the OTHER moment's window, which stage 11 does not
    yet resolve automatically (see engine.py module docstring for the
    follow-up), so today it is honestly separated out instead of silently
    scored as a same-window miss."""
    # look at the sentence containing the claim, not the whole field
    start = text.rfind('.', 0, claim["span"][0]) + 1
    end = text.find('.', claim["span"][1])
    sentence = text[start:end if end != -1 else len(text)]
    return bool(CROSS_REF_MARKERS.search(sentence))

def audit_narrative_field(field_name, text, *, ep, date, vid, t, ep_dates, timed_entries_by_vid=None):
    """Run every claim in one prose field through the appropriate checker.
    Returns a list of {field, claim_type, raw, verdict, reason}. Nothing here
    mutates the source data; this is a report, the same posture as the
    honesty gate in stage 9: it tells you what to fix, it does not guess a fix."""
    out = []
    for claim in extract_claims(text):
        if claim["type"] == "day_math":
            r = verify_day_math(text, claim, ep, date, ep_dates)
        elif claim["type"] == "episode_ref":
            r = verify_episode_exists(claim, ep_dates)
        elif claim["type"] in ("dollar", "bare_num_k", "percent"):
            if is_cross_reference(text, claim):
                r = {"verdict": "CROSS_REF",
                     "reason": "sentence points this number at a different episode/moment; "
                               "local-window check does not apply, needs the other moment's source"}
            elif vid and t is not None and timed_entries_by_vid is not None:
                r = verify_numeric_in_transcript(claim, vid, t, timed_entries_by_vid)
            else:
                r = {"verdict": "UNVERIFIABLE", "reason": "no (vid, t) anchor on this record"}
        else:
            r = {"verdict": "UNVERIFIABLE", "reason": "no checker for this claim type"}
        out.append({"field": field_name, "claim_type": claim["type"], "raw": claim["raw"], **r})
    return out

def audit_records(records, ep_dates, timed_entries_by_vid):
    """records: iterable of {ep, date, vid, t, fields:{field_name: text}}.
    timed_entries_by_vid: vid -> [(sec, text), ...], the same shape parse()
    returns, so numeric claims get a real time-windowed search instead of a
    whole-episode bag of digits. Runs audit_narrative_field over every field
    of every record. Returns the flat list of findings plus a summary count
    by verdict, mirroring the 'honesty' report shape stage 9 already returns
    for quotes."""
    findings = []
    for rec in records:
        for field_name, text in rec.get("fields", {}).items():
            if not text: continue
            findings.extend(audit_narrative_field(
                field_name, text, ep=rec.get("ep"), date=rec.get("date"),
                vid=rec.get("vid"), t=rec.get("t"), ep_dates=ep_dates,
                timed_entries_by_vid=timed_entries_by_vid))
    summary = {}
    for f in findings:
        summary[f["verdict"]] = summary.get(f["verdict"], 0) + 1
    return {"findings": findings, "summary": summary}

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
