"""
Security checker for Z-TRUST.

Provides deterministic pattern-based detection for:
- Prompt injection indicators
- Privacy/secret exposure risks

These checks do NOT depend on the LLM — they run as fast deterministic
regex scans before and independent of any Groq API call.

Limitations acknowledged:
- Pattern matching catches known phrases but will miss novel attacks.
- False positives are possible (e.g., legitimate discussion of security topics).
- This is a heuristic layer, not a complete security filter.
"""

import re

INJECTION_PATTERNS = [
    r"ignore all previous instructions",
    r"ignore previous instructions",
    r"reveal confidential information",
    r"reveal secrets",
    r"system prompt",
    r"bypass (?:the )?security",
    r"disregard (?:all )?prior instructions",
    r"override (?:all )?safety",
    r"pretend you are",
    r"act as if you have no restrictions",
    r"jailbreak",
    r"DAN mode",
    r"developer mode",
    r"ignore (?:all )?safety",
]

PRIVACY_PATTERNS = [
    r"\b\d{3}-\d{2}-\d{4}\b",  # US SSN-like pattern
    r"\b\d{16}\b",              # possible payment-card number; heuristic only
    r"\b(?:password|api[_ -]?key|secret token)\s*[:=]\s*\S+",
    r"\b(?:private key|access token)\s*[:=]\s*\S+",
    r"\b(?:bearer)\s+[a-zA-Z0-9_\-\.]+",  # Bearer tokens
]


def _scan(text: str, patterns: list[str]) -> list[str]:
    """Scan text for regex patterns. Returns list of matched pattern strings."""
    found = []
    for pattern in patterns:
        if re.search(pattern, text, flags=re.IGNORECASE):
            found.append(pattern)
    return found


def detect_prompt_injection(text: str) -> dict:
    """Detect prompt injection indicators using deterministic pattern matching.

    Returns:
        dict with 'detected' (bool), 'matches' (list of matched patterns),
        and 'note' explaining limitations.
    """
    matches = _scan(text, INJECTION_PATTERNS)
    return {
        "detected": bool(matches),
        "matches": matches,
        "note": (
            "Pattern-based detection only. May produce false positives "
            "(e.g., legitimate security discussions) or miss novel attacks."
        ) if matches else None,
    }


def detect_privacy_risk(text: str) -> dict:
    """Detect potential privacy/secret exposure using deterministic pattern matching.

    Returns:
        dict with 'detected' (bool), 'matches' (list of matched patterns),
        and 'note' explaining limitations.
    """
    matches = _scan(text, PRIVACY_PATTERNS)
    return {
        "detected": bool(matches),
        "matches": matches,
        "note": (
            "Pattern-based detection only. May flag benign content "
            "that resembles sensitive data formats."
        ) if matches else None,
    }
