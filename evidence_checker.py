"""
Evidence checker for Z-TRUST.

Provides two modes:
1. Lexical overlap heuristic (original fast baseline, no external API needed)
2. Groq-powered evidence retrieval and claim verification (full pipeline)

Ensures:
- Retrieval is attempted only once per verification request
- Duplicate error messages are eliminated
- Provider failures return explicit INSUFFICIENT_EVIDENCE without assigning a false score of 0
"""

import re
from typing import Optional

STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "is", "are", "was", "were",
    "be", "been", "being", "to", "of", "in", "on", "for", "with", "by",
    "as", "at", "from", "that", "this", "it", "its", "can", "could",
    "may", "might", "will", "would", "should", "has", "have", "had"
}


def _tokens(text: str) -> list[str]:
    words = re.findall(r"[a-zA-Z0-9]+", text.lower())
    return [word for word in words if word not in STOPWORDS and len(word) > 1]


def check_evidence(answer: str, reference_evidence: str) -> dict:
    """Original lexical overlap heuristic — preserved for backward compatibility
    and for use when Groq is unavailable."""
    if not reference_evidence.strip():
        return {
            "coverage": 0,
            "supported_terms": [],
            "unsupported_terms": _tokens(answer)[:30],
            "has_reference": False,
            "method": "simple lexical overlap heuristic"
        }

    answer_terms = _tokens(answer)
    evidence_terms = set(_tokens(reference_evidence))
    unique_answer_terms = list(dict.fromkeys(answer_terms))
    if not unique_answer_terms:
        coverage = 0
        supported = []
        unsupported = []
    else:
        supported = [term for term in unique_answer_terms if term in evidence_terms]
        unsupported = [term for term in unique_answer_terms if term not in evidence_terms]
        coverage = round(100 * len(supported) / len(unique_answer_terms))

    return {
        "coverage": coverage,
        "supported_terms": supported[:50],
        "unsupported_terms": unsupported[:50],
        "has_reference": True,
        "method": "simple lexical overlap heuristic"
    }


def check_evidence_with_groq(
    question: str,
    ai_answer: str,
    reference_evidence: Optional[str] = None,
) -> dict:
    """Full Groq-powered evidence verification pipeline.

    1. If user provided reference_evidence, uses it directly.
    2. Otherwise, performs automated search retrieval once.
    3. If retrieval fails, returns explicit INSUFFICIENT_EVIDENCE state.
    4. Evaluates claims with Groq LLM and computes grounded coverage.
    """
    from groq_client import retrieve_evidence, verify_claims, is_configured

    has_user_ref = bool(reference_evidence and reference_evidence.strip())
    result = {
        "method": "groq_powered_verification",
        "has_reference": has_user_ref,
        "evidence_source": "user_provided" if has_user_ref else "auto_retrieved",
        "sources": [],
        "claims": [],
        "overall_assessment": "",
        "coverage": None,
        "retrieval_error": None,
        "verification_error": None,
        "is_provider_error": False,
        "groq_configured": is_configured(),
        "claim_summary": {"total": 0, "supported": 0, "contradicted": 0, "insufficient_evidence": 0},
    }

    if not is_configured() and not has_user_ref:
        result["verification_error"] = (
            "Groq API key is not configured. "
            "Copy .env.example to .env and paste your Groq API key."
        )
        result["overall_assessment"] = (
            "Verification unavailable: Groq API key not configured. "
            "Please configure GROQ_API_KEY in .env."
        )
        result["is_provider_error"] = True
        return result

    # --- Step 1: Obtain evidence text ---
    evidence_text = ""
    sources = []

    if has_user_ref:
        evidence_text = reference_evidence.strip()
        sources = [{"title": "User-provided reference evidence", "url": "", "snippet": evidence_text[:300]}]
        result["sources"] = sources
        result["has_reference"] = True
    else:
        # Perform retrieval exactly once
        retrieval = retrieve_evidence(question, ai_answer)
        sources = retrieval.get("sources", [])
        result["sources"] = sources
        result["search_executed"] = retrieval.get("search_executed", False)
        result["search_provider"] = retrieval.get("provider", "")

        if retrieval.get("error"):
            # Clean single error assignment
            result["retrieval_error"] = retrieval["error"]
            result["is_provider_error"] = True

        # Build combined evidence text
        parts = []
        if retrieval.get("raw_content"):
            parts.append(retrieval["raw_content"])
        for s in sources:
            if s.get("snippet"):
                parts.append(f"[{s.get('title', 'Source')}]: {s['snippet']}")

        evidence_text = "\n\n".join(parts).strip()

        # Handle failure to obtain evidence
        if not evidence_text or not sources:
            err_msg = retrieval.get("error") or "No relevant evidence sources found for this query."
            result["retrieval_error"] = err_msg
            result["is_provider_error"] = True
            result["overall_assessment"] = (
                f"INSUFFICIENT_EVIDENCE: {err_msg} "
                "Verification cannot be completed. This is a retrieval limitation, not evidence of falsity."
            )
            result["claims"] = [
                {
                    "claim": "AI Answer Statements",
                    "classification": "INSUFFICIENT_EVIDENCE",
                    "explanation": f"Evidence retrieval incomplete: {err_msg}. Statements are unverified.",
                    "evidence_passage": "",
                    "is_inference": False,
                }
            ]
            result["claim_summary"] = {
                "total": 1,
                "supported": 0,
                "contradicted": 0,
                "insufficient_evidence": 1,
            }
            result["coverage"] = 0
            return result

        result["has_reference"] = True

    # --- Step 2: Verify claims against evidence ---
    verification = verify_claims(question, ai_answer, evidence_text, sources)

    if verification.get("error"):
        result["verification_error"] = verification["error"]
        result["is_provider_error"] = True
        result["overall_assessment"] = (
            f"INSUFFICIENT_EVIDENCE: Claim verification failed ({verification['error']})."
        )
        result["claims"] = [
            {
                "claim": "AI Answer Statements",
                "classification": "INSUFFICIENT_EVIDENCE",
                "explanation": f"Verification error: {verification['error']}.",
                "evidence_passage": "",
                "is_inference": False,
            }
        ]
        result["claim_summary"] = {
            "total": 1,
            "supported": 0,
            "contradicted": 0,
            "insufficient_evidence": 1,
        }
        result["coverage"] = 0
        return result

    result["claims"] = verification.get("claims", [])
    result["overall_assessment"] = verification.get("overall_assessment", "")
    result["model_used"] = verification.get("model_used", "")

    # --- Step 3: Compute claim coverage ---
    if result["claims"]:
        supported = sum(1 for c in result["claims"] if c["classification"] == "SUPPORTED")
        contradicted = sum(1 for c in result["claims"] if c["classification"] == "CONTRADICTED")
        insufficient = sum(1 for c in result["claims"] if c["classification"] == "INSUFFICIENT_EVIDENCE")
        total = len(result["claims"])

        result["coverage"] = round(100 * supported / total) if total > 0 else 0
        result["claim_summary"] = {
            "total": total,
            "supported": supported,
            "contradicted": contradicted,
            "insufficient_evidence": insufficient,
        }
    else:
        result["coverage"] = 0
        result["claim_summary"] = {"total": 0, "supported": 0, "contradicted": 0, "insufficient_evidence": 0}

    return result
