# Market Media Intelligence

**A source-linked intelligence and learning system for market shows.**

Market Media Intelligence turns long-form conversations about crypto, equities, macro, prediction markets, and internet culture into a durable product people can **search, understand, follow, and verify**.

It is not a transcript dump, a clip feed, a call scoreboard, or a generic online course. It is the connective layer around a show: part archive, part research desk, part learning product, and part institutional memory.

This repository packages the product thinking, evidence model, editorial standards, UX principles, audit process, and operator workflow developed through the **Market Bubble Desk** and **Counterparty Record** concepts.

## The problem

Market shows create hours of valuable conversations: calls, explanations, changing convictions, guest insight, frameworks, and follow-up questions. Most of that value disappears into video archives once the broadcast ends.

Clips recover attention, but they usually lose chronology, context, and accountability.

Market Media Intelligence preserves what clips cannot:

- what was actually said;
- who said it and who they were talking about;
- whether it was a position, prediction, observation, scenario, probability read, or retrospective claim;
- how that view changed across episodes;
- what an audience can learn from it;
- and the exact source moment where it can be checked.

## Four user outcomes

The system is designed around four simple jobs:

1. **Catch up** — understand a multi-hour episode in minutes.
2. **Understand** — learn the language, mechanics, risk, and reasoning behind a call.
3. **Follow** — see how a speaker's market view or disclosed stance evolves over time.
4. **Verify** — return to the exact source second and inspect the original words.

Search supports every layer rather than becoming a separate content product.

## Product architecture

### 1. Archive

Searchable episodes, transcript moments, guests, topics, assets, and timestamped source links.

### 2. Calls and records

Structured statements grouped by **asset and speaker**, with clear separation between:

- disclosed positions;
- predictions;
- probability reads;
- scenarios;
- observations;
- retrospective claims.

The record distinguishes a speaker's **latest recorded view** from their **last disclosed stance**. These are not automatically the same thing.

### 3. Evolving theses

Chronological records showing when a view began, what changed, what remained open, and which source supports every step.

### 4. Academy

Source-linked studies built from real show moments. Each study can explain the context, call, entry, target, invalidation, outcome, and reusable lesson without rewriting history around the result.

### 5. Independent analysis

Original research, charts, setups, on-chain work, small-cap analysis, follow-ups, and unresolved questions. This layer is explicitly attributed and never presented as the show's official position.

### 6. Editorial radar

An optional decision-support layer that surfaces candidates for human editors using signals such as contradiction, view change, repetition, compact quotability, and archive significance.

It does **not** claim to replace human taste in viral clip selection.

## Core capabilities

- Archive ingestion and searchable moment indexing
- Episode recaps designed for rapid comprehension
- Call extraction and statement classification
- Speaker, subject, and asset separation
- Asset-and-speaker dossiers
- Evolving thesis timelines
- Retrospective claim verification
- Source-linked Academy studies
- Independent market analysis surfaces
- Information-architecture and UI/UX restructuring
- Responsive and accessibility audits
- Editorial and data-integrity validation
- Pre-launch and pre-send product audits
- Proof-of-work positioning and concise outreach
- Optional broadcast and unified-chat architecture

## Evidence doctrine

The system is only useful if the record can be trusted.

- Preserve the record without rewriting it.
- Attribute or abstain. Verify or qualify.
- Keep raw evidence immutable and derive presentation from it.
- Separate speaker, grammatical subject, asset, statement type, and direction.
- Mark every omission inside an excerpt with an ellipsis.
- Never put a paraphrase inside quotation marks.
- Never infer a position from enthusiasm, a price target, or somebody else's description.
- Never treat a probability disagreement as a personal prediction automatically.
- Never merge `hold` with `avoid`; they describe opposite portfolio states.
- Scope cards, counts, dossiers, and timelines with the same active filters.
- Label sparse history honestly instead of inventing a trend.
- Use **source-linked** rather than **verified** until quote, speaker, timestamp, and interpretation have all been reviewed.

## Statement model

Every structured market statement should preserve:

```text
episode + moment + speaker + subject + asset
statement type + direction + stated view
quote or excerpt class + context
date + timestamp + source
historical status + confidence + review status
```

Thesis records are derived from **speaker + asset**, never from the asset alone.

## Editorial model

The product complements a show's existing hosts, producers, and clippers.

Before a show, the operator can turn research across crypto, memecoins, equities, macro, and prediction markets into sourced briefs, guest notes, segment ideas, and unresolved questions.

After a show, the operator can preserve calls, track changes, identify follow-ups, build Academy studies, and publish clearly labeled independent analysis.

The result is not merely a website. It is an operating system for turning recurring broadcasts into durable intellectual property.

## Show profiles

### Market Bubble

Best expressed as a premium editorial desk: fast episode recaps, searchable moments, evolving speaker-and-asset records, Academy studies, and original analysis around a broadcast-first media brand.

### Counterparty

Best expressed as a forensic record: positions, predictions, observations, reversals, retrospective claims, and evidence across a larger archive of crypto, stocks, macro, and on-chain conversations.

The evidence architecture transfers between shows. The surface design and editorial emphasis should not be copied blindly.

## Repository structure

```text
market-media-intelligence/
├── SKILL.md
├── agents/
│   └── openai.yaml
└── references/
    ├── vision-and-product.md
    ├── data-and-evidence.md
    ├── pipeline-and-validation.md
    ├── ux-and-information-architecture.md
    ├── editorial-and-analysis.md
    ├── show-profiles.md
    ├── audit-and-shipping.md
    ├── broadcast-and-chat.md
    └── operator-and-outreach.md
```

## Using the Codex skill

Install or copy the `market-media-intelligence` directory into your Codex skills directory, then invoke it explicitly:

```text
Use $market-media-intelligence to audit this market-show intelligence product.
```

Example prompts:

```text
Use $market-media-intelligence to redesign the Calls experience around asset, speaker, latest view, and last disclosed stance.
```

```text
Use $market-media-intelligence to audit every public quote, timestamp, speaker attribution, count, filter, and thesis timeline before launch.
```

```text
Use $market-media-intelligence to turn this episode archive into five-minute recaps, source-linked calls, Academy studies, and an evolving thesis record.
```

```text
Use $market-media-intelligence to position this MVP as proof of work without overstating automation or commercial results.
```

## Reference implementations

- [Market Bubble Academy / The Market Bubble Desk](https://marketbubbleacademy.netlify.app/)
- [Counterparty](https://counterparty.netlify.app/#home)

These are independent proof-of-concept implementations built around real show data. They are not official products of, or affiliated with, Market Bubble or Counterparty unless explicitly stated otherwise.

## What this system does not claim

- It does not replace human editorial judgment.
- It does not guarantee speaker attribution when the source lacks reliable diarization.
- It does not call an excerpt verified merely because a source link exists.
- It does not turn every opinion into a position or every probability read into a prediction.
- It does not claim commercial, retention, or audience outcomes that have not been measured.
- It does not present independent analysis as financial advice or as the show's official view.

## Guiding principle

> A clip shows the moment. The record preserves what changed.

The goal is simple: turn an ephemeral markets show into a durable product people can search, learn from, verify, and return to.
