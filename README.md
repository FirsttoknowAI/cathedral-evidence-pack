# cathedral-evidence-pack
Provenance-aware LLM evaluation system with human-validated measurement, replay verification, and tamper-evident experiment tracking.

# Cathedral Evidence Pack

A provenance-aware evaluation framework for LLM behavior, combining:

- Behavioral measurement (Project A)
- Human-validated annotation protocols
- Deterministic replay verification
- Tamper-evident experiment tracking (Chronicle)

---

## Architecture

Project A → Behavioral Evaluation
- inference.py
- judge.py
- analysis.py

Measurement Layer
- ANNOTATION_PROTOCOL.md
- gold_labels.json
- inter-rater agreement metrics

Project B → Provenance + Governance
- Chronicle (hash-chained ledger)
- Replay verification (I27 invariant)

---

## Core Guarantees

- Reproducibility (deterministic replay)
- Auditability (append-only provenance)
- Measurement reliability (human validation layer)
- Claim discipline (no overreach beyond evidence)

---

## Key Insight

Provenance proves where results came from.  
Human validation proves whether results are reliable.

---

## Status

Early-stage implementation with:
- annotation protocol defined
- evaluation fixtures prepared
- replay model specified

Next step: empirical validation + agreement analysis

---

## Why This Matters

Most LLM evaluation systems:
- measure behavior
- but cannot prove integrity or reliability

This system combines:
> measurement + validation + provenance

into a single auditable pipeline.