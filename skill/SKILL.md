---
name: editorial-intelligence-engine
description: The verified ingest engine that turns show transcripts into durable intelligence (indexed moments, attributed calls, evolving thesis trails, a clean lexicon) with honesty gates that block anything unverified. Use this whenever ingesting a new episode or show, extracting calls or moments from a transcript, attributing quotes to speakers, building or extending a thesis trail, verifying quotes verbatim, snapping timestamps to the exact second, or auditing a media-intelligence dataset. Trigger on any mention of: ingest, pipeline, algorithm, transcript, index moments, extract calls, thesis trail, verbatim check, snap timestamps, speaker attribution, lexicon, honesty check, or adding an episode to Market Bubble / Counterparty / The Tape / The Record. This is the DATA engine; pair it with editorial-intelligence-builder for strategy and the single-file build. Prefer this skill over ad-hoc parsing every time a transcript becomes data.
---

# Editorial Intelligence Engine

The engine that converts raw show transcripts into verified, attributed, evolving intelligence. Its output feeds the single-file build (see editorial-intelligence-builder). Its one job is to be **right**: every displayed quote is an exact substring of a real transcript, every call is attributed to the person who said it, every count is recomputed from the data, and nothing unverified ever ships.

The product's entire value is that "exact second" and "verified, not curated" are literally true. This engine is what makes them true at scale, so its discipline is non-negotiable.

## The ten stages, in order

Ingest is a pipeline. Each stage has a contract, a known failure mode, and a rule. Run them in order; never skip verification.

### 1. Parse (timestamps and segments)

Transcripts arrive with a messy timestamp format, e.g. `1:022 minutes, 2 secondsUm now...` (an `M:SS` or `H:MM:SS` prefix immediately followed by a redundant verbose duration, then the text).

- Split on the leading `\n?\d+:\d+(?::\d+)?` prefix. Strip the trailing verbose duration (`^\d*\s*(?:hours?,?\s*)?(?:\d+\s*minutes?,?\s*)?(?:\d+\s*seconds?)`).
- Convert `M:SS` -> `m*60+s`, `H:MM:SS` -> `h*3600+m*60+s`.
- **Validation gate:** timestamps must be monotonically non-decreasing, and no `t` may exceed the video duration (get the duration from the `.info.json` or the channel page). A `t` beyond the duration is a parse error, not data. Flag and drop.

```python
def to_sec(ts):
    p=[int(x) for x in ts.strip().split(':')]
    return p[0]*60+p[1] if len(p)==2 else p[0]*3600+p[1]*60+p[2]
```

### 2. Segment (chapters and moments)

Author chapters are the backbone. Chapter markers (`Chapter N: Title`) appear embedded in the text.

- For each chapter marker, snap its `t` to the **first content line at or after** the marker, not the marker's own char offset (which can trail into the previous segment).
- Emit one moment per chapter as the baseline, plus intra-chapter **beat moments** for high-signal lines (a stated numeric level, a guest intro, a direction word next to a ticker).
- **Auto-tag from the chapter's text, not just its title.** Scan the chapter body for tickers (BTC, SOL, HYPE, ZEC, ...) -> `assets`; for topic keywords (memecoin, pumpfun, robinhood, on-chain, rwa, ...) -> `topics`; for named guests -> `guests`.

**Edition titles are claims, not labels.** A chapter name ("Where The $600 SOL Number Comes From", "Complex's Top 25 Streamers List") is a label: it says what the segment is about. An edition title is a claim: it says what was said, with a subject, a verb and a stake ("Multicoin's math puts Solana at $600", "Complex's streamer rankings read like engagement bait"). Any moment surfaced in the featured edition, the book rundown, or a recap card carries an `insight` field written as a claim, drawn from the chapter's strongest line, never invented beyond what was said. The renderer prefers `insight` over `title`. Chapter titles stay in the archive as navigation; claims are what the edition publishes.

Moment contract: `{ep, date:"YYYYMMDD", vid, t, title, insight?, assets:[], topics:[], guests:[], isEp, epTitle}`.

### 3. Attribute (who said it) . the highest-value stage

Raw transcripts have **no speaker labels**. Guessing here is how you attribute a guest's thesis to the host. This happened: Zcash / Hyperliquid / Solana were Tushar Jain (Multicoin), not Ansem. Never guess.

- Build a **speaker registry** per episode from intro detection: `I'?m ([A-Z][a-z]+)...(founder|CEO|CIO|at) ([A-Z][\w ]+)` and the chapter titles ("Tushar Clip: ...", "Mike Dudas Joins").
- Map each chapter to its **active speaker(s)**: the host(s) by default, plus any guest whose intro falls in or just before the chapter.
- Attribute a quote to the resolved active speaker. If a chapter has multiple active speakers and the line cannot be pinned to one, set `who` to `null` and add the moment to a `NEEDS_SPEAKER` review set. **A quote with an unresolved speaker never becomes a scored call and never displays an attribution.**

### 4. Classify (statement taxonomy)

Not every market sentence is a call. Force each into one honest type, and never inflate:

| stype | test | example |
|---|---|---|
| `prediction` | future + directional | "60K is not going to hold" |
| `disclosed_position` | past tense, "we put on / we're long" | "we put on a big Zcash position in February" |
| `retrospective_claim` | claims a past call | "I called bottom around 58.8K" |
| `probability_view` | fades or backs an odds/line | "the 11% odds for 100K are too low" |
| `scenario` | hypothetical / conditional | "with Bitcoin at 200K, position accordingly" |
| `observation` | market color, no stance | "Bitcoin printing a higher low" |

- A statement is only promoted to a **scorable call** (gets `entry`/`target`) when a numeric level **and** a direction **and** a timeframe are all present. Otherwise it stays a labeled statement, never scored.
- `dir` in {long, short, neutral}. `stypeLabel` is the human label shown in the UI ("A prediction", "Disclosed position", "Retrospective claim", "Probability view").

Call contract: `{d:"YYYY-MM-DD", ep, vid, t, who, tick, dir, entry, q, ctx, stype, stypeLabel, stated, target}`.

### 5. Verify (verbatim, non-negotiable)

Every `q` must be an **exact contiguous substring** of its transcript. This is the whole credibility of the product.

- Normalize both sides only for the match (strip `[ __ ]`, `[laughter]`, collapse whitespace, lowercase); store the **raw** verbatim in `q`.
- **Reject stitched quotes.** If the displayed text is not one contiguous run in the source, it is a paraphrase. Either quote a real contiguous span or label it `Summary` and drop the quote marks. (This is the "paraphrase in quotes" bug: never do it.)
- **Flag speaker-crossing.** If the span crosses a timestamp gap larger than a few seconds, it may splice two speakers; hold for review.
- Zero drift is the bar. If a quote cannot be verified, it does not enter the data.

### 6. Snap (timestamp to the quote)

- Re-align `t` to the second where the quote's **first distinctive word** is actually said, minus a small lead-in (default `-3s`) so "open at source" lands just before the line.
- Clamp to `[0, duration]`.

### 7. Trail (build the thesis, honestly)

The thesis trail is the centerpiece: one conviction tracked across episodes. Build it automatically per `(asset, speaker)`.

- Order that speaker's statements on the asset by date. Each becomes a node: date, ep, verbatim quote, hear-at-source, and an honest state label.
- **Honest outcome rules** (this encodes discipline that was hard-won by correcting real overreach):
  - If a stated invalidation level was breached **after** the stated target was met -> `Target condition met first` and note the later cross. Do **not** call it "invalidated".
  - If invalidation was breached and no target was met -> `Invalidated at <level>`.
  - If neither resolved -> `Open`.
  - If no explicit exit or P&L was stated -> append `logged as called, not scored`.
  - Never `won`, `winning trade`, `live`, or `still open` without the evidence for that exact word.
- Guest theses build their **own** trails, never merged into a host's trail.

### 8. Lexicon (quality-gated)

Mine terms that appear >= 3 times, each with a real example quote (`vid` + `t`).

- **Reject** a term whose example starts mid-word, is truncated, or is a common English word matched out of crypto context. Hold rejects in a `LEX_REVIEW_REQUIRED` set: they stay in the data, spliced out of display, until a human verifies the source clip in the intended sense.
- Frequency counts are real. Fix false positives; never inflate.

### 9. Honesty gate (blocks the build)

A single check that must pass with **zero violations** before anything renders:

- No displayed quote fails the verbatim check (stage 5).
- No displayed call has an unresolved or guessed speaker (stage 3).
- No thesis node uses an outcome word its evidence does not support (stage 7).
- No number is hard-coded; every count recomputes from the data (stage 10).
- No `latest` / `today` / `live` claim that the cadence does not support. Weekly show: use "Latest edition", "Archive indexed through Episode N", "Watch the show", never "today" or a permanent live dot.
- The Read / coverage entries are dated, sourced, and labeled independent (the one dataset not transcript-verifiable).

If any check fails, fix the data, not the check.

### 10. Incremental ingest and dynamic render

Adding an episode must be **idempotent** and must never drift a count.

- Dedup key `(ep, round(t))`. Re-ingesting an episode **replaces** its moments, never appends duplicates.
- After ingest, **recompute every displayed number from the data at runtime**: total moments (with a real `ep`), episode count, per-episode counts, `Archive indexed through Episode <max ep>`, latest date, calls, terms. Never write a total into the markup.
- Extend affected thesis trails automatically.
- Then validate: re-extract the JS (`node --check`), run the HTML structure check, headless-render and assert zero `pageerror`, and spot-check the ten most visible timestamps by hand. One bad timestamp undermines the whole traceability claim.

## Counts are snapshots, never constants

Any number (moments, calls, terms, episodes) is a value at one moment in time. The engine recomputes it from the current data every time. The single source of truth is the datasets, not the HTML.

## Same engine, any show

The field contracts are identical across shows. Only the transcripts, brand tokens, assets, and copy change. Market Bubble (The Tape) and Counterparty (The Record) run the exact same engine; a new show is just new transcripts through the same ten stages.

## What "more intelligent" means here

Intelligence in this engine is not fancier extraction. It is **refusing to be wrong**: attribute or abstain, verify or drop, score only with full evidence, and label outcomes only as far as the evidence reaches. Every upgrade above serves that. A model that indexes 500 moments but misattributes one thesis is worth less than one that indexes 300 and is never caught wrong, because the second one keeps the trust the product is built on.

## No em-dashes

In any produced copy (site, thread, deck, email, UI strings), never use an em-dash mid-sentence. Use a period, comma, parentheses, or middot. The only allowed `--` is an empty-value placeholder.
