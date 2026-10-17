import re
from collections import Counter

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
