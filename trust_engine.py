"""
Trust engine for Z-TRUST.

Produces a deterministic decision (RELEASE / FLAG / BLOCK) based on
evidence verification results, security signals, and claim coverage.

Decision Precedence (deterministic, highest priority first):
  1. BLOCK — security or privacy rule triggers (overrides everything)
  2. FLAG  — insufficient evidence, material contradictions, provider failures, or low coverage
  3. RELEASE — sufficient evidence, no contradictions, no security blocks

The trust score is a heuristic composite. It is NOT a probability of truth.
When retrieval fails due to a provider/infrastructure error, the trust score is None (unassessed)
so as not to imply the answer is disproven or has 0 trust.
"""

from typing import Optional


def calculate_trust_score(
    evidence_coverage: Optional[int],
    source_validity: int,
    contradiction_detected: bool = False,
    prompt_injection_detected: bool = False,
    privacy_risk_detected: bool = False,
    has_reference: bool = True,
    claim_summary: dict | None = None,
    is_provider_error: bool = False,
    provider_error_message: Optional[str] = None,
) -> dict:
    """Return a transparent heuristic score and rule-based decision."""
    reasons = []

    # Priority 1: BLOCK on security or privacy signals (always overrides)
    if prompt_injection_detected or privacy_risk_detected:
        if prompt_injection_detected:
            reasons.append("Prompt injection pattern detected in input text.")
        if privacy_risk_detected:
            reasons.append("Potential sensitive data exposure pattern detected.")
        reasons.append(
            "Decision: BLOCK — security or privacy rule triggered. "
            "This overrides any evidence score."
        )
        return {
            "trust_score": 0,
            "decision": "BLOCK",
            "score_type": "Security BLOCK triggered (score overridden to 0).",
            "score_formula": "Security override: score is 0 due to safety risk.",
            "score_components": {
                "evidence_coverage": evidence_coverage or 0,
                "source_validity": source_validity,
                "contradiction_penalty": 15 if contradiction_detected else 0,
                "prompt_injection_penalty": 10 if prompt_injection_detected else 0,
                "privacy_risk_penalty": 5 if privacy_risk_detected else 0,
            },
            "reasons": reasons,
        }

    # Priority 2: Provider / Retrieval Failure -> FLAG (INSUFFICIENT_EVIDENCE) with trust_score = None
    if is_provider_error:
        reasons.append(
            f"Provider/Retrieval error occurred: {provider_error_message or 'Evidence retrieval failed'}."
        )
        reasons.append(
            "Decision: FLAG (INSUFFICIENT_EVIDENCE) — Evidence was unavailable. "
            "The answer is unassessed, NOT proven false."
        )
        return {
            "trust_score": None,
            "decision": "FLAG",
            "score_type": "Unassessed — Provider retrieval failure prevented verification; not a score of 0.",
            "score_formula": "N/A — Verification incomplete due to provider failure.",
            "score_components": {
                "evidence_coverage": None,
                "source_validity": 0,
                "reference_bonus": 0,
                "contradiction_penalty": 0,
                "prompt_injection_penalty": 0,
                "privacy_risk_penalty": 0,
            },
            "reasons": reasons,
        }

    # Normal calculation
    cov_val = int(evidence_coverage) if evidence_coverage is not None else 0
    evidence = max(0, min(100, cov_val))
    source = max(0, min(100, int(source_validity)))
    reference_bonus = 100 if has_reference else 0

    contradiction_penalty = 15 if contradiction_detected else 0
    injection_penalty = 10 if prompt_injection_detected else 0
    privacy_penalty = 5 if privacy_risk_detected else 0

    base_score = (
        0.50 * evidence
        + 0.20 * source
        + 0.30 * reference_bonus
    )
    total_penalty = contradiction_penalty + injection_penalty + privacy_penalty
    score = round(max(0, min(100, base_score - total_penalty)))

    if not has_reference:
        reasons.append("No reference evidence was available for verification.")
    elif evidence < 30:
        reasons.append("Very low evidence support — most claims could not be verified.")
    elif evidence < 60:
        reasons.append("Partial evidence support — some claims lack sufficient evidence.")

    if source < 50:
        reasons.append("Source validity rating is low.")

    if contradiction_detected:
        reasons.append("One or more claims are contradicted by the evidence.")

    has_contradictions = False
    has_insufficient = False
    if claim_summary:
        total = claim_summary.get("total", 0)
        supported = claim_summary.get("supported", 0)
        contradicted = claim_summary.get("contradicted", 0)
        insufficient = claim_summary.get("insufficient_evidence", 0)
        has_contradictions = contradicted > 0
        has_insufficient = insufficient > 0

        if total > 0:
            reasons.append(
                f"Claim analysis: {supported}/{total} supported, "
                f"{contradicted}/{total} contradicted, "
                f"{insufficient}/{total} insufficient evidence."
            )

    # Decision logic
    if not has_reference:
        decision = "FLAG"
        reasons.append("Decision: FLAG — no evidence available for verification.")
    elif contradiction_detected or has_contradictions:
        decision = "FLAG"
        reasons.append("Decision: FLAG — material claims are contradicted by evidence.")
    elif has_insufficient and evidence < 60:
        decision = "FLAG"
        reasons.append("Decision: FLAG — insufficient evidence for key claims.")
    elif score < 60:
        decision = "FLAG"
        reasons.append("Decision: FLAG — overall evidence support is too low.")
    else:
        decision = "RELEASE"
        reasons.append(
            "Decision: RELEASE — claims are supported by evidence and no blocking rules apply."
        )

    return {
        "trust_score": score,
        "decision": decision,
        "score_type": (
            "Heuristic composite score (0–100). NOT a probability of truth. "
            "The decision (RELEASE/FLAG/BLOCK) is authoritative; "
            "the score provides supplementary context."
        ),
        "score_formula": (
            "evidence_coverage×0.50 + source_validity×0.20 + reference_bonus×0.30 "
            "− contradiction_penalty(15) − injection_penalty(10) − privacy_penalty(5)"
        ),
        "score_components": {
            "evidence_coverage": evidence,
            "source_validity": source,
            "reference_bonus": reference_bonus,
            "contradiction_penalty": contradiction_penalty,
            "prompt_injection_penalty": injection_penalty,
            "privacy_risk_penalty": privacy_penalty,
        },
        "reasons": reasons,
    }
