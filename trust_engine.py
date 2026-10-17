def calculate_trust_score(
    evidence_coverage: int,
    source_validity: int,
    contradiction_detected: bool = False,
    prompt_injection_detected: bool = False,
    privacy_risk_detected: bool = False,
    has_reference: bool = True,
) -> dict:
    """Return a transparent heuristic score and rule-based decision.

    Weights: evidence 40%, source validity 30%, contradiction penalty 15%,
    prompt-injection penalty 10%, privacy penalty 5%.
    """
    evidence = max(0, min(100, int(evidence_coverage)))
    source = max(0, min(100, int(source_validity)))
    contradiction_penalty = 15 if contradiction_detected else 0
    injection_penalty = 10 if prompt_injection_detected else 0
    privacy_penalty = 5 if privacy_risk_detected else 0

    weighted = (
        0.40 * evidence
        + 0.30 * source
        + 0.15 * (100 - contradiction_penalty / 0.15 if contradiction_detected else 100)
        + 0.10 * (100 - injection_penalty / 0.10 if prompt_injection_detected else 100)
        + 0.05 * (100 - privacy_penalty / 0.05 if privacy_risk_detected else 100)
    )
    # Keep score components interpretable: risk flags subtract their stated points.
    score = round(0.40 * evidence + 0.30 * source + 0.30 * 100
                  - contradiction_penalty - injection_penalty - privacy_penalty)
    score = max(0, min(100, score))

    reasons = []
    if not has_reference:
        reasons.append("No reference evidence was provided.")
    if evidence < 50:
        reasons.append("Low lexical overlap between answer and reference evidence.")
    if source < 50:
        reasons.append("Source validity rating is low.")
    if contradiction_detected:
        reasons.append("A contradiction was reported.")
    if prompt_injection_detected:
        reasons.append("A prompt-injection pattern or signal was detected.")
    if privacy_risk_detected:
        reasons.append("A potential privacy or secret-exposure pattern was detected.")

    if prompt_injection_detected or privacy_risk_detected:
        decision = "BLOCK"
        reasons.append("Security/privacy flags trigger the block rule.")
    elif not has_reference or contradiction_detected or score < 70:
        decision = "FLAG"
    else:
        decision = "RELEASE"

    return {
        "trust_score": score,
        "decision": decision,
        "score_type": "heuristic rule-based score; not a probability",
        "score_components": {
            "evidence_coverage": evidence,
            "source_validity": source,
            "contradiction_penalty": contradiction_penalty,
            "prompt_injection_penalty": injection_penalty,
            "privacy_risk_penalty": privacy_penalty,
        },
        "reasons": reasons,
    }
