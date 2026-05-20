# Copilot Instructions for cathedral-evidence-pack

You are helping implement a minimal, deterministic LLM evaluation system with provenance tracking and replay verification.

## STRICT CONSTRAINTS

- Python 3.11+
- Standard library only (no external dependencies)
- Keep all files < 200–250 lines
- No frameworks, no async, no databases
- No over-engineering or abstractions unless necessary
- Code must be readable and testable

## SYSTEM GOAL

Build a small but correct system that:
1. Runs evaluation fixtures
2. Logs all events to an append-only ledger (Chronicle)
3. Uses hash chaining for tamper detection
4. Supports deterministic replay validation
5. Stores human annotation records immutably

## REPOSITORY STRUCTURE

```
project_a/
  inference.py
  judge.py

project_b/
  chronicle.py
  replay_validator.py

measurement/
  tracer_fixtures_v1.json
  ANNOTATION_PROTOCOL.md

run_eval.py
```

## CORE INVARIANTS

1. Chronicle is append-only
2. Every event is SHA256 hash-chained
3. Replay must reproduce identical hash sequence
4. All records are immutable after write
5. JSON serialization must be deterministic (sorted keys, no randomness)
6. Human + model events use the SAME logging format

## EVENT FORMAT (JSONL)

Each event must include:
- `event_id` (uuid)
- `timestamp` (ISO8601)
- `event_type` (e.g. "inference", "annotation")
- `payload` (dict)
- `prev_hash`
- `hash`

## DELIVERABLES (IN ORDER)

1. Working chronicle (append + verify)
2. Replay validator
3. Simple evaluation runner
4. Annotation schema
5. CLI entrypoint: run_eval.py

## DO NOT ADD

- Cloud services
- UI
- APIs
- ML models
- Distributed systems
- Unnecessary abstractions
- Multiple files per phase without explicit approval

## FOCUS

- Correctness > features
- Determinism > performance
- Clarity > abstraction

## BUILD DISCIPLINE

1. Implement ONE file at a time
2. Each file must pass basic verification before moving to next
3. Keep code boring (boring = correct)
4. Use only standard library imports
5. Add heavy comments explaining the "why"
