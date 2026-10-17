from fastapi import FastAPI
from pydantic import BaseModel, Field
from trust_engine import calculate_trust_score
from evidence_checker import check_evidence
from security_checker import detect_prompt_injection, detect_privacy_risk

app = FastAPI(
    title="Z-TRUST — Evidence-Gated AI Decision Firewall",
    description="A prototype API that evaluates AI answers against supplied evidence and risk signals.",
    version="0.1.0",
)

class VerifyRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=4000)
    ai_answer: str = Field(..., min_length=1, max_length=12000)
    reference_evidence: str = Field(default="", max_length=20000)
    source_validity: int = Field(default=50, ge=0, le=100)
    contradiction_detected: bool = False
    prompt_injection_detected: bool = False
    privacy_risk_detected: bool = False

@app.get("/")
def root():
    return {"project": "Z-TRUST", "status": "prototype", "docs": "/docs"}

@app.get("/health")
def health():
    return {"status": "ok", "version": app.version}

@app.post("/verify")
def verify(request: VerifyRequest):
    evidence_result = check_evidence(request.ai_answer, request.reference_evidence)
    injection_result = detect_prompt_injection(request.question + "\n" + request.ai_answer + "\n" + request.reference_evidence)
    privacy_result = detect_privacy_risk(request.ai_answer + "\n" + request.reference_evidence)

    injection_detected = request.prompt_injection_detected or injection_result["detected"]
    privacy_detected = request.privacy_risk_detected or privacy_result["detected"]

    result = calculate_trust_score(
        evidence_coverage=evidence_result["coverage"],
        source_validity=request.source_validity,
        contradiction_detected=request.contradiction_detected,
        prompt_injection_detected=injection_detected,
        privacy_risk_detected=privacy_detected,
        has_reference=bool(request.reference_evidence.strip()),
    )
    result["project"] = "Z-TRUST"
    result["evidence"] = evidence_result
    result["security"] = {
        "prompt_injection": {"detected": injection_detected, "matches": injection_result["matches"]},
        "privacy_risk": {"detected": privacy_detected, "matches": privacy_result["matches"]},
    }
    result["limitations"] = [
        "Evidence overlap is a heuristic, not proof of factual correctness.",
        "Source validity is supplied by the caller and is not independently authenticated.",
        "Contradiction detection is a caller-provided signal in this prototype.",
        "Human review is required before consequential use."
    ]
    return result
