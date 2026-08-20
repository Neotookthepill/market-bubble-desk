# Editorial Intelligence Engine (runnable)

The verified ingest pipeline. One command turns a show transcript into
attributed, verbatim-checked intelligence with an honesty report.

    python engine.py <transcript.txt> --ep N --date YYYYMMDD --vid VIDEOID \
        --title "Episode title" --duration SECONDS

Output (JSON): indexed moments, classified + attributed statements, a
needs_review set (unresolved speakers, abstained not guessed), and an
honesty report (timestamps out of range, unattributed, verbatim failures,
guests detected, gate PASS/REVIEW).

Principle: attribute or abstain, verify or drop, score only with full
evidence. Being right beats being exhaustive.

See ../skills/editorial-intelligence-engine/SKILL.md for the full spec.
