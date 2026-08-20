---
name: counterparty-intelligence-engine
description: >
  Full intelligence behind The Record (counterparty.netlify.app): the verified pipeline that turns
  Counterparty show transcripts into an honest, searchable memory. Covers call detection, scoring,
  speaker attribution, asset dossiers (stance vs mention, flips, on-air price context), the
  asset/theme search logic, and the honesty doctrine with known limits. Use when building, auditing,
  extending, or porting this engine (Market Bubble runs the same DNA).
---

# Counterparty Intelligence Engine (The Record)

One sentence: the show talks, the machine remembers, attributes, and hands back the exact source.
Doctrine: **refuse to be wrong. Attribute or abstain. Verify or drop. Recompute every number from data.**

## Data source
- Buzzsprout podcast feed 2535072. Per episode: word-level timestamped transcript, title, date.
- Current corpus: 146 episodes, 37,946 tape lines, 282 clean calls, 93 lexicon terms.
- Dates: "Mon DD" strings; year rule: Sep-Dec = 2025, Jan-Aug = 2026.

## Stage 1: call detection (extract_calls_heuristic)
A sentence becomes a call candidate only if ALL pass:
1. Ticker detected (pattern + TICKERS name map), not in NOT_TICKERS (FOMC, GPU, COVID, UFC, acronyms).
2. Direction word present with **word-boundary regex** (so "no longer", "along", "belong" never trigger "long"). Multi-word phrases matched as substrings.
3. TIME_LONG exclusions ("long time", "as long as", "how long"...) and NEGATIONS ("not long", "no position"...).
4. **Object guard**: "bought/sold + my/his/a/the + watch|car|monitors|house|..." rejects the sentence (the object is not the asset). This killed "Razmer bought my watch" being a SOL long.
5. **Proximity gate**: direction word must sit within 8 tokens of the ticker or its name, else direction is dropped. Kills cross-contamination in long multi-ticker sentences.
Quote trimmed to <=200 chars at sentence boundary.

## Stage 2: scoring and thresholds (rank_calls)
Additive score. +30 first-person ("I longed", "I bought"), +30 stated price level, +20 conviction
words, -20 hedging, hard 0 if third-party context ("he bought", "Trump acquired").
Keep score >= 40. De-dupe per episode by (ticker, direction), keep best score, store `mentions`
(how many times the position was repeated: repetition is conviction). Filter residual junk tickers
(BAD set). Each call keeps: tk, dir, quote, ts, secs, score, epid (Buzzsprout id), mentions.

## Stage 3: speaker attribution (attribute or abstain)
- guest_from_title(): "Name - topic" episode titles yield the guest (TITLE_NOISE filters false names).
- Guest episode + clear first-person position language -> who = guest.
- Guest episode, ambiguous -> who = null + who_note "guest episode, speaker unresolved". NEVER default to host.
- Solo episode -> who = "Threadguy".
UI shows the badge only when it informs: guests and unresolved. Host is the silent default.

## Stage 4: statement taxonomy (computed, mostly not displayed)
classify_statement(): retrospective_claim / probability_view / scenario / disclosed_position /
prediction / observation. Kept in data; hidden in UI because it did not discriminate enough
(313/350 were "prediction"). Lesson: a label that is everywhere means nothing.

## Stage 5: asset dossiers (compute_dossiers, min 3 calls)
Per asset: n, longs/shorts, monthly attention series, and the critical distinction:
- **lastStance**: last first-person position (STANCE_PATTERNS regex: "I'm long", "I bought",
  "sell the house and buy", "I'd short"...). Displayed with direction.
- **lastMention**: last time it came up. If not a stance, UI says "direction not stated as a
  position". Never conflate mention with position.
- **flips**: direction changes computed on stances only (not observations).
- **BTC priceCtx**: on-air price marks scraped from the tape itself (market opens: "Bitcoin 63.9",
  "64.8 on BTC"; targets like "to 75k" excluded; plausibility 40-150k; median per day). Each call
  gets nearest mark at call time and the nearest later mark (5-45 days). Label: "Prices as spoken
  on air during market opens. Context, not a verdict." The show is its own oracle: zero external data.

## Search logic (asset vs theme, automatic)
- Query is an ASSET if it equals a ticker in the corpus OR maps via NAME2SYM (~90 names:
  micron->MU, bitcoin->BTC...). Asset mode is STRICT: only calls on that ticker, plus its dossier
  rendered above the list.
- Otherwise THEME: weighted full-text (partial ticker 70, quote mention 55, episode title 35).
- Result counter always shown. Longs/Shorts chips filter via data-d.
Every call row links to https://www.buzzsprout.com/2535072/episodes/{epid}?t={secs}.

## UI comprehension rules
- Subtabs self-describe: "The Tape (every word)" vs "The Ledger (only the calls)", cross-linked.
- All counters recomputed from data (never hardcoded); animated on scroll.
- No empty sections, no overpromising copy, no em-dashes anywhere.
- Anatomy of a Call = closed case studies, steps numbered 01-04, "From the tape" verbatim anchors.

## Honest limits (state these when asked about accuracy)
- Precision is ESTIMATED by sampling (~95% after cleanups), not certified: no labeled ground truth
  yet. Next step if rigor is required: label ~200 sentences, compute precision AND recall, fit a
  logistic scorer, pick threshold on the F0.5 curve (precision weighted 2x).
- Recall loss: calls spanning two sentences ("Micron. I bought it yesterday") are missed
  (no pronoun resolution, no sliding window yet).
- BTC price marks are sparse (~11 days); "later mark" can be up to 45 days out. Context only.
- Direction = direction EXPRESSED on air, not verified portfolio positioning.
- Dossier ratios have no confidence intervals yet; treat n<10 as low sample.

## Porting note
Market Bubble (The Tape, marketbubbleacademy.netlify.app) runs the same DNA. To port: swap the
feed source, rebuild NAME2SYM for that show's asset universe, keep every gate identical.
