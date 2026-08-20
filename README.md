# The Market Bubble Desk

The intelligence and memory layer for the Market Bubble show. Turns every
episode into a searchable, verified, source-linked archive: a thesis trail
that tracks how each conviction evolved, an asset dossier that separates a
stated position from a passing mention, and a search that understands
people, tickers, and statement types, not just substrings.

Built and operated by @KtheQuant. Independent concept, not affiliated with
Market Bubble.

## Structure

- `hub/`         The live product. One self-contained HTML file. Deploy to Netlify.
- `engine/`      The ingest pipeline (engine.py). Turns a transcript into verified data.
- `data/`        Generated datasets (one JSON per ingested episode).
- `transcripts/` Source transcripts, one file per episode.
- `skill/`       Engine specs: our 10-stage pipeline, plus the Counterparty
                  engine's hard-won gates (call detection, asset dossiers,
                  honesty doctrine) that this hub's logic is ported from.
- `docs/`        Strategy notes.

## Deploy the hub

`hub/index.html` is static and self-contained. Connect this repo to Netlify
with publish directory `hub` (already set in `netlify.toml`), or drag the
file in by hand.

## Ingest a new episode

    python engine/engine.py transcripts/epNN.txt --ep NN --date YYYYMMDD \
        --vid VIDEOID --title "Episode title" --duration SECONDS

The engine attributes or abstains, verifies every quote verbatim, snaps
timestamps to the second, and prints an honesty report. Its rule is to be
right, not exhaustive. See `skill/SKILL.md` for the full pipeline.

## After ingesting

The archive counters, the featured edition, the thesis timeline, and the
book all recompute from `INDEX`/`CALLS` at runtime. Nothing is hardcoded.
Add the new moments and calls to those arrays in `hub/index.html` and every
display updates on its own.
