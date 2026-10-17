import re

INJECTION_PATTERNS = [
    r"ignore all previous instructions",
    r"ignore previous instructions",
    r"reveal confidential information",
    r"reveal secrets",
    r"system prompt",
    r"bypass (?:the )?security",
    r"disregard (?:all )?prior instructions",
]

PRIVACY_PATTERNS = [
    r"\b\d{3}-\d{2}-\d{4}\b",  # US SSN-like pattern
    r"\b\d{16}\b",              # possible payment-card number; heuristic only
    r"\b(?:password|api[_ -]?key|secret token)\s*[:=]\s*\S+",
    r"\b(?:private key|access token)\s*[:=]\s*\S+",
]

def _scan(text: str, patterns: list[str]) -> list[str]:
    found = []
    for pattern in patterns:
        if re.search(pattern, text, flags=re.IGNORECASE):
            found.append(pattern)
    return found

def detect_prompt_injection(text: str) -> dict:
    matches = _scan(text, INJECTION_PATTERNS)
    return {"detected": bool(matches), "matches": matches}

def detect_privacy_risk(text: str) -> dict:
    matches = _scan(text, PRIVACY_PATTERNS)
    return {"detected": bool(matches), "matches": matches}
