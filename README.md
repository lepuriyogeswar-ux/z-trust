# Z-TRUST — Evidence-Gated AI Decision Firewall

**Tagline:** The AI Firewall for the AI Age.

Z-TRUST is a prototype concept for checking AI-generated answers against supplied reference evidence before a human decision-maker relies on them. It reports evidence coverage, source validity, detected contradictions, security/privacy flags, a transparent rule-based trust score, and a release/flag/block recommendation.

> **Status:** Prototype / proposal-stage implementation. Scores are heuristic decision aids, not guarantees of truth or safety. Human review remains necessary.

## Current prototype capabilities
- FastAPI endpoints: `/`, `/health`, and `/verify`.
- Evidence overlap check against user-provided reference evidence.
- Transparent score components for evidence coverage and source validity.
- Rule-based contradiction, prompt-injection, and privacy-risk flags supplied by the request.
- Decision outcomes: `RELEASE`, `FLAG`, or `BLOCK` with reasons.

## Run locally

```bash
python -m venv .venv
# Windows PowerShell: .venv\\Scripts\\Activate.ps1
pip install -r requirements.txt
uvicorn main:app --reload
```

Open `http://127.0.0.1:8000/docs` for the interactive API docs.

## Example request

```json
{
  "question": "What city is the capital of Maharashtra?",
  "ai_answer": "Mumbai is the capital of Maharashtra.",
  "reference_evidence": "Mumbai is the capital city of Maharashtra, India.",
  "source_validity": 90,
  "contradiction_detected": false,
  "prompt_injection_detected": false,
  "privacy_risk_detected": false
}
```

Send this object as JSON to `POST /verify`.

## Architecture (prototype)
1. Receive AI answer and reference evidence.
2. Inspect text overlap and caller-provided risk signals.
3. Calculate a transparent heuristic score.
4. Apply decision rules and return score breakdown plus reasons.
5. Human reviewer decides whether to use the answer.

## Security and limitations
- Do not submit secrets, credentials, or real personal data.
- Prompt-injection matching is a basic prototype check, not a complete security filter.
- Evidence overlap is not semantic fact verification and may miss paraphrases or reward misleading overlap.
- The source-validity field is supplied by the caller; the prototype does not independently authenticate URLs or source provenance.
- Contradiction and privacy flags are currently input signals, not automatically established facts.
- Do not use this prototype for high-stakes decisions without rigorous validation, monitoring, and expert review.

## Planned extensions
- Independent source retrieval and provenance validation.
- Claim-level verification and contradiction analysis.
- Stronger prompt-injection and sensitive-data detection.
- Evaluation dataset, attack scenarios, latency and false-block measurements.
- Deployment on IBM LinuxONE with appropriate security controls, subject to environment availability.

## License
MIT License (see `LICENSE`).