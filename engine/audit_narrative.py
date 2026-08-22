#!/usr/bin/env python3
"""
Stage 11 runner: audits every narrative claim (CALLS.ctx, DISP.beats/lede/call,
ANAT.setup/lesson/outcome) in hub/index.html against the real transcripts in
transcripts/epNN.txt. No separate mapping file: the (ep -> vid) link and the
episode date registry are both read straight out of hub/index.html's own
DISP array, since that data already exists once an episode is ingested.

Reuses engine.parse() so this reads the exact same transcript format the
ingest command already expects, one format, one parser, no drift.

Run from the repo root:
    python engine/audit_narrative.py

Optional:
    python engine/audit_narrative.py --hub hub/index.html --transcripts transcripts

Exit code 1 if any FAIL is found (a real, computed error), 0 otherwise.
CROSS_REF and REVIEW never fail the run; they are honest "needs a human
glance" findings, printed but not blocking, same posture as stage 9.
"""
import re, json, sys, os, argparse
sys.path.insert(0, os.path.dirname(__file__))
import engine as eng

def load_disp_registry(hub_text):
    """(ep -> vid) and (ep -> date) straight from DISP. No hand-maintained
    mapping file to fall out of sync with the data it's supposed to describe."""
    DISP = json.loads(re.search(r'const DISP=(\[.*?\]);', hub_text, re.S).group(1))
    ep_vid = {d["ep"]: d["vid"] for d in DISP}
    ep_dates = {d["ep"]: d["date"] for d in DISP}
    return ep_vid, ep_dates

def load_transcript_timed(path):
    """One parser, engine.py's own parse(), so a transcript that ingests
    cleanly also audits cleanly. Returns [(sec, text), ...]."""
    txt = open(path, encoding='utf-8', errors='replace').read()
    return [(t, b) for t, ts, b in eng.parse(txt)]

def load_records(hub_text, ep_vid):
    CALLS = json.loads(re.search(r'const CALLS=(\[.*?\]);', hub_text, re.S).group(1))
    DISP = json.loads(re.search(r'const DISP=(\[.*?\]);', hub_text, re.S).group(1))
    ANAT = json.loads(re.search(r'const ANAT=(\[.*?\]);', hub_text, re.S).group(1))
    records = []
    for c in CALLS:
        records.append({"ep": c["ep"], "date": c["d"], "vid": c.get("vid") or ep_vid.get(c["ep"]),
                         "t": c["t"], "fields": {"ctx": c.get("ctx", "")}})
    for d in DISP:
        beats_text = ' '.join(b["text"] if isinstance(b, dict) else b for b in d.get("beats", []))
        records.append({"ep": d["ep"], "date": d["date"], "vid": d["vid"], "t": None,
                         "fields": {"lede": d.get("lede", ""), "beats": beats_text,
                                    "call": d.get("call") or ""}})
    for a in ANAT:
        records.append({"ep": a["ep"], "date": a["date"], "vid": a.get("vid") or ep_vid.get(a["ep"]),
                         "t": a["t"], "fields": {"setup": a.get("setup", ""),
                                                  "lesson": a.get("lesson", ""),
                                                  "outcome": a.get("outcome", "")}})
    return records

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hub", default="hub/index.html")
    ap.add_argument("--transcripts", default="transcripts")
    a = ap.parse_args()

    if not os.path.exists(a.hub):
        print(f"Cannot find {a.hub}. Run this from the repo root, or pass --hub.")
        sys.exit(2)

    hub_text = open(a.hub, encoding='utf-8').read()
    ep_vid, ep_dates = load_disp_registry(hub_text)
    records = load_records(hub_text, ep_vid)

    timed = {}
    missing_transcripts = []
    for ep, vid in ep_vid.items():
        # transcripts/epNN.txt, matching the ingest command's own naming
        path = os.path.join(a.transcripts, f"ep{ep:02d}.txt")
        if os.path.exists(path):
            timed[vid] = load_transcript_timed(path)
        else:
            missing_transcripts.append(path)

    report = eng.audit_records(records, ep_dates, timed)

    print("=== Narrative claim audit ===")
    print(report["summary"])
    if missing_transcripts:
        print(f"\n(skipped numeric checks for {len(missing_transcripts)} missing transcript file(s): "
              f"{', '.join(missing_transcripts)})")

    fails = [f for f in report["findings"] if f["verdict"] == "FAIL"]
    reviews = [f for f in report["findings"] if f["verdict"] == "REVIEW"]
    cross_refs = [f for f in report["findings"] if f["verdict"] == "CROSS_REF"]

    if fails:
        print("\n--- FAIL (confirmed wrong by computation, fix before publishing) ---")
        for f in fails:
            print(f)
    if reviews:
        print("\n--- REVIEW (tool could not confirm locally, human call) ---")
        for f in reviews:
            print(f)
    if cross_refs:
        print("\n--- CROSS_REF (this number belongs to a different moment/episode, not locally checkable) ---")
        for f in cross_refs:
            print(f)

    sys.exit(1 if fails else 0)

if __name__ == "__main__":
    main()
