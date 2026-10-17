# Z-TRUST — 3-minute submission video script

**Target duration:** 2:30–2:55. Record a screen capture at 720p or 1080p. Do not claim planned features are already implemented.

## 0:00–0:25 — Problem
“AI can produce fluent answers that are unsupported, contradictory, or risky. For important workflows, users need more than a confident-sounding response. They need a transparent checkpoint before relying on it.”

## 0:25–0:50 — Introduce Z-TRUST
“Our project is Z-TRUST, the Evidence-Gated AI Decision Firewall. It evaluates an AI-generated answer against reference evidence and visible risk signals, then returns an explainable Trust Score and a RELEASE, FLAG, or BLOCK recommendation.”

## 0:50–1:45 — Live demo
1. Show the public GitHub repository and its README.
2. Run the API locally with `uvicorn main:app --reload`.
3. Open `http://127.0.0.1:8000/docs`.
4. Open `POST /verify` and submit:
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
5. Show the response fields: trust_score, decision, score_components, evidence, security, and limitations.
6. Run one safe negative example with missing evidence, and one security example using the explicit prompt-injection flag. Show the resulting FLAG/BLOCK decision.

## 1:45–2:20 — What is different
“Z-TRUST makes the decision process visible. It shows evidence overlap, risk signals, and reasons instead of treating model confidence as proof. The current implementation is an early prototype: evidence matching is lexical, source validity is caller-supplied, and contradiction detection is a supplied signal.”

## 2:20–2:50 — Impact and next steps
“Our next steps are claim-level verification, source provenance and freshness checks, a labelled evaluation set, and measurements for attack detection, false-block rate, and latency. We aim to explore deployment on IBM LinuxONE with appropriate controls, subject to environment access. Z-TRUST is designed to support human review, not replace it.”

## Recording checklist
- Show only working features; do not stage fake results.
- Use 720p/1080p and keep the video under 3 minutes.
- Avoid exposing passwords, API keys, or private data.
- Upload to YouTube as **Unlisted** or Public, or to Vimeo with judge-accessible permissions.
- Test the final link in a private/incognito window before submitting.
