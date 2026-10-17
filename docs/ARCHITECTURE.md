# Z-TRUST Architecture

## Flow

1. **Request intake** — FastAPI receives the question, candidate AI answer, reference evidence, source-validity rating, and optional risk signals.
2. **Evidence overlap** — `evidence_checker.py` tokenizes answer and reference text and reports a simple lexical overlap percentage plus supported/unsupported terms.
3. **Security heuristics** — `security_checker.py` checks for a small set of prompt-injection phrases and obvious secret/identifier patterns.
4. **Trust engine** — `trust_engine.py` combines evidence coverage and caller-provided source validity with penalties for reported contradiction, injection, and privacy signals.
5. **Decision output** — the API returns `RELEASE`, `FLAG`, or `BLOCK`, a heuristic score, component breakdown, reasons, and limitations.
6. **Human review** — a person reviews the evidence and result before relying on the answer.

## Decision rules

- **BLOCK:** prompt-injection or privacy-risk signal is present.
- **FLAG:** evidence is missing, a contradiction is reported, or the score is below 70.
- **RELEASE:** no block/flag rule applies and score is at least 70.

## Current implementation boundaries

This is an early prototype. Evidence overlap is not semantic fact checking; source validity is supplied by the caller rather than independently verified; contradiction detection is a request signal; and security pattern matching is incomplete. A high score does not establish truth or safety.

## Planned evaluation

Build a labelled set of supported, unsupported, stale, contradictory, prompt-injection, and privacy-risk examples. Report claim-level precision/recall where applicable, attack detection rate, false-block rate, score calibration, and median/p95 latency. Keep test examples and scoring thresholds versioned.
