"""
Z-TRUST — Evidence-Gated AI Decision Firewall

Main FastAPI application with:
- /verify endpoint for Groq-powered claim verification
- /health endpoint for diagnostic status checks
- / serves the single-page frontend
"""

import html
import logging
import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from trust_engine import calculate_trust_score
from evidence_checker import check_evidence, check_evidence_with_groq
from security_checker import detect_prompt_injection, detect_privacy_risk

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger("z-trust")

app = FastAPI(
    title="Z-TRUST — Evidence-Gated AI Decision Firewall",
    description="A Groq-powered API that verifies AI-generated answers against retrieved evidence and risk signals.",
    version="0.2.1",
)


# ---------------------------------------------------------------------------
# Request / Response Models
# ---------------------------------------------------------------------------

class VerifyRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=4000)
    ai_answer: str = Field(..., min_length=1, max_length=12000)
    reference_evidence: str = Field(default="", max_length=20000)


# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    """Health check and configuration diagnostic — reports status without exposing secrets."""
    from groq_client import get_diagnostic
    return get_diagnostic()


@app.post("/verify")
def verify(request: VerifyRequest):
    """Verify an AI-generated answer against evidence.

    If reference_evidence is provided, uses it directly.
    Otherwise, auto-retrieves evidence via Groq browser search or configured search adapter.
    Uses Groq LLM for claim-level verification.
    Falls back cleanly with explicit INSUFFICIENT_EVIDENCE if retrieval fails.
    """
    # --- Step 1: Security screening (deterministic, independent of LLM) ---
    combined_text = f"{request.question}\n{request.ai_answer}\n{request.reference_evidence}"
    injection_result = detect_prompt_injection(combined_text)
    privacy_result = detect_privacy_risk(
        f"{request.ai_answer}\n{request.reference_evidence}"
    )

    injection_detected = injection_result["detected"]
    privacy_detected = privacy_result["detected"]

    # --- Step 2: Evidence verification ---
    from groq_client import is_configured

    if is_configured() or os.getenv("TAVILY_API_KEY") or os.getenv("SERPER_API_KEY"):
        # Full verification pipeline
        evidence_result = check_evidence_with_groq(
            question=request.question,
            ai_answer=request.ai_answer,
            reference_evidence=request.reference_evidence if request.reference_evidence.strip() else None,
        )
    else:
        # Fallback: lexical heuristic only
        lexical = check_evidence(request.ai_answer, request.reference_evidence)
        evidence_result = {
            "method": "lexical_fallback (no external provider configured)",
            "has_reference": lexical["has_reference"],
            "evidence_source": "user_provided" if lexical["has_reference"] else "none",
            "sources": [],
            "claims": [],
            "overall_assessment": (
                "Groq API is not configured. Using lexical overlap heuristic only. "
                "This is not semantic fact verification."
            ),
            "coverage": lexical["coverage"],
            "claim_summary": {"total": 0, "supported": 0, "contradicted": 0, "insufficient_evidence": 0},
            "retrieval_error": None,
            "verification_error": "Groq API not configured — lexical fallback only.",
            "is_provider_error": True,
            "groq_configured": False,
            "lexical_details": lexical,
        }

    # --- Step 3: Check for contradictions from claim analysis ---
    contradiction_detected = False
    claim_summary = evidence_result.get("claim_summary")
    if claim_summary and claim_summary.get("contradicted", 0) > 0:
        contradiction_detected = True

    # --- Step 4: Source validity and trust scoring ---
    has_reference = evidence_result.get("has_reference", False)
    if evidence_result.get("sources") and evidence_result.get("coverage", 0) > 0:
        has_reference = True

    if evidence_result.get("evidence_source") == "user_provided":
        source_validity = 80
    elif evidence_result.get("sources"):
        source_validity = 70
    else:
        source_validity = 0

    is_provider_error = evidence_result.get("is_provider_error", False)
    provider_err_msg = evidence_result.get("retrieval_error") or evidence_result.get("verification_error")

    trust_result = calculate_trust_score(
        evidence_coverage=evidence_result.get("coverage"),
        source_validity=source_validity,
        contradiction_detected=contradiction_detected,
        prompt_injection_detected=injection_detected,
        privacy_risk_detected=privacy_detected,
        has_reference=has_reference,
        claim_summary=claim_summary,
        is_provider_error=is_provider_error,
        provider_error_message=provider_err_msg,
    )

    # --- Step 5: Build response with deduplicated errors ---
    errors = []
    if evidence_result.get("retrieval_error"):
        errors.append(evidence_result["retrieval_error"])
    if evidence_result.get("verification_error"):
        ver_err = evidence_result["verification_error"]
        if ver_err not in errors:
            errors.append(ver_err)

    response = {
        "project": "Z-TRUST",
        "version": app.version,
        "decision": trust_result["decision"],
        "trust_score": trust_result["trust_score"],
        "score_type": trust_result["score_type"],
        "score_formula": trust_result["score_formula"],
        "score_components": trust_result["score_components"],
        "reasons": trust_result["reasons"],
        "evidence": {
            "method": evidence_result.get("method", ""),
            "evidence_source": evidence_result.get("evidence_source", ""),
            "coverage": evidence_result.get("coverage"),
            "claim_summary": evidence_result.get("claim_summary", {}),
            "claims": evidence_result.get("claims", []),
            "sources": evidence_result.get("sources", []),
            "overall_assessment": evidence_result.get("overall_assessment", ""),
            "search_executed": evidence_result.get("search_executed", False),
            "search_provider": evidence_result.get("search_provider", ""),
            "model_used": evidence_result.get("model_used", ""),
        },
        "security": {
            "prompt_injection": {
                "detected": injection_detected,
                "matches": injection_result["matches"],
                "note": injection_result.get("note"),
            },
            "privacy_risk": {
                "detected": privacy_detected,
                "matches": privacy_result["matches"],
                "note": privacy_result.get("note"),
            },
        },
        "errors": errors,
        "limitations": [
            "Evidence retrieval depends on external search provider availability.",
            "Claim verification uses LLM inference, which may contain errors.",
            "The trust score is a heuristic decision aid, not a guarantee of truth.",
            "Security pattern matching is a baseline check, not an exhaustive defense.",
            "Human review is required before consequential use.",
        ],
    }

    return response


# ---------------------------------------------------------------------------
# Frontend
# ---------------------------------------------------------------------------

FRONTEND_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Z-TRUST — AI Verification Firewall</title>
<style>
  :root {
    --primary: #1a73e8;
    --bg: #f8f9fa;
    --card: #ffffff;
    --text: #202124;
    --text-secondary: #5f6368;
    --border: #dadce0;
    --success: #0d652d;
    --success-bg: #e6f4ea;
    --warning: #e37400;
    --warning-bg: #fef7e0;
    --danger: #c5221f;
    --danger-bg: #fce8e6;
    --info-bg: #e8f0fe;
    --radius: 12px;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.6;
    min-height: 100vh;
  }
  .container { max-width: 800px; margin: 0 auto; padding: 24px 16px; }

  /* Header */
  header {
    text-align: center;
    padding: 32px 0 24px;
  }
  header h1 {
    font-size: 2rem;
    font-weight: 700;
    color: var(--text);
    letter-spacing: -0.5px;
  }
  header h1 span { color: var(--primary); }
  header p {
    color: var(--text-secondary);
    font-size: 1rem;
    margin-top: 8px;
  }

  /* Card */
  .card {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 24px;
    margin-bottom: 20px;
  }

  /* Form */
  label {
    display: block;
    font-weight: 600;
    font-size: 0.9rem;
    margin-bottom: 6px;
    color: var(--text);
  }
  label .optional {
    font-weight: 400;
    color: var(--text-secondary);
    font-size: 0.8rem;
  }
  textarea, input[type="text"] {
    width: 100%;
    padding: 12px;
    border: 1px solid var(--border);
    border-radius: 8px;
    font-size: 0.95rem;
    font-family: inherit;
    resize: vertical;
    transition: border-color 0.2s;
    background: #fff;
  }
  textarea:focus, input:focus {
    outline: none;
    border-color: var(--primary);
    box-shadow: 0 0 0 2px rgba(26,115,232,0.15);
  }
  .field { margin-bottom: 16px; }

  /* Advanced toggle */
  .advanced-toggle {
    background: none;
    border: none;
    color: var(--primary);
    cursor: pointer;
    font-size: 0.9rem;
    padding: 8px 0;
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .advanced-toggle:hover { text-decoration: underline; }
  .advanced-section { display: none; margin-top: 12px; }
  .advanced-section.open { display: block; }

  /* Button */
  .btn-verify {
    width: 100%;
    padding: 14px;
    background: var(--primary);
    color: #fff;
    border: none;
    border-radius: 8px;
    font-size: 1.05rem;
    font-weight: 600;
    cursor: pointer;
    transition: background 0.2s, transform 0.1s;
    margin-top: 8px;
  }
  .btn-verify:hover { background: #1557b0; }
  .btn-verify:active { transform: scale(0.99); }
  .btn-verify:disabled {
    background: #93b4e0;
    cursor: not-allowed;
    transform: none;
  }

  /* Loading */
  .loading {
    display: none;
    text-align: center;
    padding: 32px;
  }
  .loading.active { display: block; }
  .spinner {
    width: 40px; height: 40px;
    border: 4px solid var(--border);
    border-top-color: var(--primary);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
    margin: 0 auto 16px;
  }
  @keyframes spin { to { transform: rotate(360deg); } }

  /* Results */
  #results { display: none; }
  #results.visible { display: block; }

  /* Decision badge */
  .decision-badge {
    display: inline-block;
    padding: 8px 24px;
    border-radius: 24px;
    font-size: 1.3rem;
    font-weight: 700;
    letter-spacing: 1px;
    text-transform: uppercase;
  }
  .decision-RELEASE { background: var(--success-bg); color: var(--success); }
  .decision-FLAG { background: var(--warning-bg); color: var(--warning); }
  .decision-BLOCK { background: var(--danger-bg); color: var(--danger); }

  .decision-header {
    text-align: center;
    padding: 24px;
  }
  .trust-score {
    font-size: 2.5rem;
    font-weight: 700;
    color: var(--text);
  }
  .score-label {
    font-size: 0.85rem;
    color: var(--text-secondary);
    margin-top: 4px;
  }

  /* Sections */
  .section-title {
    font-size: 1rem;
    font-weight: 700;
    margin-bottom: 12px;
    padding-bottom: 8px;
    border-bottom: 1px solid var(--border);
  }

  /* Claims */
  .claim-item {
    padding: 12px;
    border-radius: 8px;
    margin-bottom: 8px;
    border-left: 4px solid;
  }
  .claim-SUPPORTED { background: var(--success-bg); border-color: var(--success); }
  .claim-CONTRADICTED { background: var(--danger-bg); border-color: var(--danger); }
  .claim-INSUFFICIENT_EVIDENCE { background: var(--warning-bg); border-color: var(--warning); }
  .claim-badge {
    display: inline-block;
    font-size: 0.75rem;
    font-weight: 700;
    padding: 2px 8px;
    border-radius: 4px;
    margin-bottom: 4px;
  }
  .badge-SUPPORTED { background: var(--success); color: #fff; }
  .badge-CONTRADICTED { background: var(--danger); color: #fff; }
  .badge-INSUFFICIENT_EVIDENCE { background: var(--warning); color: #fff; }
  .claim-text { font-weight: 600; font-size: 0.9rem; }
  .claim-explanation { font-size: 0.85rem; color: var(--text-secondary); margin-top: 4px; }
  .claim-passage {
    font-size: 0.82rem;
    font-style: italic;
    color: var(--text-secondary);
    margin-top: 4px;
    padding: 6px 10px;
    background: rgba(0,0,0,0.03);
    border-radius: 4px;
  }

  /* Sources */
  .source-item {
    padding: 8px 0;
    border-bottom: 1px solid var(--border);
  }
  .source-item:last-child { border-bottom: none; }
  .source-title { font-weight: 600; font-size: 0.9rem; }
  .source-url {
    color: var(--primary);
    font-size: 0.82rem;
    word-break: break-all;
    text-decoration: none;
  }
  .source-url:hover { text-decoration: underline; }
  .source-snippet {
    font-size: 0.82rem;
    color: var(--text-secondary);
    margin-top: 2px;
  }

  /* Reasons */
  .reason-item {
    font-size: 0.88rem;
    padding: 4px 0;
    color: var(--text-secondary);
  }
  .reason-item::before {
    content: "•";
    margin-right: 8px;
    color: var(--primary);
  }

  /* Alert boxes */
  .alert {
    padding: 12px 16px;
    border-radius: 8px;
    font-size: 0.88rem;
    margin-bottom: 12px;
  }
  .alert-error { background: var(--danger-bg); color: var(--danger); }
  .alert-warning { background: var(--warning-bg); color: var(--warning); }
  .alert-info { background: var(--info-bg); color: var(--primary); }

  /* Security */
  .security-flag {
    padding: 10px 14px;
    border-radius: 8px;
    margin-bottom: 8px;
    font-size: 0.88rem;
  }
  .security-detected { background: var(--danger-bg); color: var(--danger); }
  .security-clear { background: var(--success-bg); color: var(--success); }

  /* Retry button */
  .btn-retry {
    padding: 8px 16px;
    background: var(--warning);
    color: #fff;
    border: none;
    border-radius: 6px;
    font-size: 0.85rem;
    font-weight: 600;
    cursor: pointer;
    margin-top: 8px;
  }
  .btn-retry:hover { background: #c06200; }

  /* Responsive */
  @media (max-width: 600px) {
    .container { padding: 16px 12px; }
    header h1 { font-size: 1.5rem; }
    .trust-score { font-size: 2rem; }
    .card { padding: 16px; }
  }

  /* Footer */
  footer {
    text-align: center;
    padding: 24px 0;
    color: var(--text-secondary);
    font-size: 0.8rem;
  }
</style>
</head>
<body>

<div class="container">
  <header>
    <h1><span>Z-TRUST</span> — AI Verification Firewall</h1>
    <p>Verify AI-generated answers against evidence before you trust them.</p>
  </header>

  <!-- Input Form -->
  <div class="card" id="form-card">
    <div class="field">
      <label for="question">Question</label>
      <textarea id="question" rows="2" placeholder="What question was asked of the AI?"></textarea>
    </div>

    <div class="field">
      <label for="ai_answer">AI-Generated Answer</label>
      <textarea id="ai_answer" rows="4" placeholder="Paste the AI's answer here for verification..."></textarea>
    </div>

    <button class="advanced-toggle" type="button" onclick="toggleAdvanced()">
      <span id="adv-arrow">&#9654;</span> Advanced: Provide your own reference evidence
    </button>
    <div class="advanced-section" id="advanced-section">
      <div class="field">
        <label for="reference_evidence">Reference Evidence <span class="optional">(optional — leave empty for automatic web retrieval)</span></label>
        <textarea id="reference_evidence" rows="4" placeholder="Paste reference evidence here, or leave empty to auto-search..."></textarea>
      </div>
    </div>

    <button class="btn-verify" id="btn-verify" onclick="runVerification()">
      &#x1F50D; Verify Answer
    </button>
  </div>

  <!-- Loading State -->
  <div class="loading" id="loading">
    <div class="spinner"></div>
    <p><strong>Verifying answer...</strong></p>
    <p style="font-size:0.85rem;color:var(--text-secondary);">Searching for evidence and analyzing claims with Groq AI</p>
  </div>

  <!-- Results -->
  <div id="results">
    <!-- Errors -->
    <div id="error-section"></div>

    <!-- Decision -->
    <div class="card" id="decision-card">
      <div class="decision-header">
        <div id="decision-badge"></div>
        <div style="margin-top:16px;">
          <div class="trust-score" id="trust-score"></div>
          <div class="score-label" id="score-label"></div>
        </div>
      </div>
    </div>

    <!-- Claims -->
    <div class="card" id="claims-card">
      <div class="section-title">&#x1F4CB; Claim Verification</div>
      <div id="claims-summary"></div>
      <div id="claims-list"></div>
    </div>

    <!-- Sources -->
    <div class="card" id="sources-card">
      <div class="section-title">&#x1F517; Evidence Sources</div>
      <div id="sources-list"></div>
    </div>

    <!-- Security -->
    <div class="card" id="security-card">
      <div class="section-title">&#x1F6E1; Security Screening</div>
      <div id="security-results"></div>
    </div>

    <!-- Reasons -->
    <div class="card" id="reasons-card">
      <div class="section-title">&#x1F4DD; Decision Reasons</div>
      <div id="reasons-list"></div>
    </div>

    <!-- Limitations -->
    <div class="card">
      <div class="section-title">&#x26A0; Limitations</div>
      <div id="limitations-list"></div>
    </div>
  </div>

  <footer>
    Z-TRUST v0.2.1 — Evidence-Gated AI Decision Firewall &bull; <a href="/health" target="_blank" style="color:var(--primary);text-decoration:none;">System Diagnostics</a><br>
    Human review is required before consequential use.
  </footer>
</div>

<script>
function esc(s) {
  const d = document.createElement('div');
  d.textContent = s || '';
  return d.innerHTML;
}

function toggleAdvanced() {
  const sec = document.getElementById('advanced-section');
  const arrow = document.getElementById('adv-arrow');
  sec.classList.toggle('open');
  arrow.innerHTML = sec.classList.contains('open') ? '&#9660;' : '&#9654;';
}

async function runVerification() {
  const question = document.getElementById('question').value.trim();
  const ai_answer = document.getElementById('ai_answer').value.trim();
  const reference_evidence = document.getElementById('reference_evidence').value.trim();

  if (!question) { alert('Please enter a question.'); return; }
  if (!ai_answer) { alert('Please enter the AI-generated answer to verify.'); return; }

  const btn = document.getElementById('btn-verify');
  const loading = document.getElementById('loading');
  const results = document.getElementById('results');

  btn.disabled = true;
  loading.classList.add('active');
  results.classList.remove('visible');

  try {
    const resp = await fetch('/verify', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question, ai_answer, reference_evidence }),
    });

    if (!resp.ok) {
      const errText = await resp.text();
      throw new Error(`Server error ${resp.status}: ${errText}`);
    }

    const data = await resp.json();
    renderResults(data);
  } catch (err) {
    document.getElementById('error-section').innerHTML =
      `<div class="alert alert-error">
        <strong>Verification Failure:</strong> ${esc(err.message)}
        <br><button class="btn-retry" onclick="runVerification()">Retry Verification</button>
      </div>`;
    results.classList.add('visible');
  } finally {
    btn.disabled = false;
    loading.classList.remove('active');
  }
}

function renderResults(data) {
  const results = document.getElementById('results');

  // Deduplicated errors
  const errors = data.errors || [];
  if (errors.length > 0) {
    const errorHtml = errors
      .map(e => `<div class="alert alert-warning">
        <strong>&#x26A0; Provider Notice:</strong> ${esc(e)}
        <br><button class="btn-retry" onclick="runVerification()">Retry Verification</button>
      </div>`)
      .join('');
    document.getElementById('error-section').innerHTML = errorHtml;
  } else {
    document.getElementById('error-section').innerHTML = '';
  }

  // Decision badge
  const dec = data.decision || 'FLAG';
  document.getElementById('decision-badge').innerHTML =
    `<span class="decision-badge decision-${esc(dec)}">${esc(dec)}</span>`;

  // Score handling: if null/undefined, do not show 0
  if (data.trust_score === null || data.trust_score === undefined) {
    document.getElementById('trust-score').textContent = 'N/A';
    document.getElementById('score-label').textContent = 'Score Unassessed (Provider/Retrieval Limitation — Claims Unverified)';
  } else {
    document.getElementById('trust-score').textContent = data.trust_score;
    document.getElementById('score-label').textContent = 'Trust Score (heuristic — not a probability)';
  }

  // Claims
  const claims = (data.evidence && data.evidence.claims) || [];
  const cs = (data.evidence && data.evidence.claim_summary) || {};

  let claimsSummaryHtml = '';
  if (cs.total > 0 && (cs.supported > 0 || cs.contradicted > 0)) {
    claimsSummaryHtml = `<div class="alert alert-info" style="margin-bottom:12px;">
      <strong>${cs.total} claim(s) analyzed:</strong>
      ${cs.supported || 0} supported, ${cs.contradicted || 0} contradicted, ${cs.insufficient_evidence || 0} insufficient evidence
    </div>`;
  } else if (data.evidence && data.evidence.overall_assessment) {
    claimsSummaryHtml = `<div class="alert alert-warning">${esc(data.evidence.overall_assessment)}</div>`;
  }
  document.getElementById('claims-summary').innerHTML = claimsSummaryHtml;

  let claimsHtml = '';
  if (claims.length === 0) {
    claimsHtml = '<p style="color:var(--text-secondary);font-size:0.9rem;">No claims were extracted for verification.</p>';
  }
  claims.forEach(c => {
    const cls = c.classification || 'INSUFFICIENT_EVIDENCE';
    let passageHtml = '';
    if (c.evidence_passage) {
      passageHtml = `<div class="claim-passage">Evidence Quote: "${esc(c.evidence_passage)}"</div>`;
    }
    claimsHtml += `
      <div class="claim-item claim-${esc(cls)}">
        <span class="claim-badge badge-${esc(cls)}">${esc(cls)}</span>
        ${c.is_inference ? '<span class="claim-badge" style="background:#666;color:#fff;">INFERENCE</span>' : ''}
        <div class="claim-text">${esc(c.claim)}</div>
        <div class="claim-explanation">${esc(c.explanation)}</div>
        ${passageHtml}
      </div>`;
  });
  document.getElementById('claims-list').innerHTML = claimsHtml;

  // Sources
  const sources = (data.evidence && data.evidence.sources) || [];
  let sourcesHtml = '';
  if (sources.length === 0) {
    sourcesHtml = '<p style="color:var(--text-secondary);font-size:0.9rem;">No external sources were retrieved.</p>';
    if (data.evidence && data.evidence.evidence_source === 'user_provided') {
      sourcesHtml = '<p style="color:var(--text-secondary);font-size:0.9rem;">Using user-provided reference evidence.</p>';
    }
  }
  sources.forEach(s => {
    let urlHtml = '';
    if (s.url) {
      urlHtml = `<a href="${esc(s.url)}" target="_blank" rel="noopener noreferrer" class="source-url">${esc(s.url)}</a>`;
    }
    sourcesHtml += `
      <div class="source-item">
        <div class="source-title">${esc(s.title || 'Source')}</div>
        ${urlHtml}
        ${s.snippet ? `<div class="source-snippet">${esc(s.snippet)}</div>` : ''}
      </div>`;
  });
  document.getElementById('sources-list').innerHTML = sourcesHtml;

  // Security
  const sec = data.security || {};
  let secHtml = '';
  const inj = sec.prompt_injection || {};
  const priv = sec.privacy_risk || {};

  if (inj.detected) {
    secHtml += `<div class="security-flag security-detected">
      <strong>&#x26A0; Prompt Injection Detected</strong>
      <div style="font-size:0.82rem;margin-top:4px;">Matched patterns: ${esc((inj.matches||[]).join(', '))}</div>
      ${inj.note ? `<div style="font-size:0.8rem;margin-top:4px;font-style:italic;">${esc(inj.note)}</div>` : ''}
    </div>`;
  } else {
    secHtml += `<div class="security-flag security-clear">&#x2705; No prompt injection patterns detected</div>`;
  }

  if (priv.detected) {
    secHtml += `<div class="security-flag security-detected">
      <strong>&#x26A0; Privacy Risk Detected</strong>
      <div style="font-size:0.82rem;margin-top:4px;">Matched patterns: ${esc((priv.matches||[]).join(', '))}</div>
      ${priv.note ? `<div style="font-size:0.8rem;margin-top:4px;font-style:italic;">${esc(priv.note)}</div>` : ''}
    </div>`;
  } else {
    secHtml += `<div class="security-flag security-clear">&#x2705; No privacy risk patterns detected</div>`;
  }
  document.getElementById('security-results').innerHTML = secHtml;

  // Reasons
  const reasons = data.reasons || [];
  document.getElementById('reasons-list').innerHTML =
    reasons.map(r => `<div class="reason-item">${esc(r)}</div>`).join('');

  // Limitations
  const lims = data.limitations || [];
  document.getElementById('limitations-list').innerHTML =
    lims.map(l => `<div class="reason-item">${esc(l)}</div>`).join('');

  results.classList.add('visible');
  document.getElementById('decision-card').scrollIntoView({ behavior: 'smooth' });
}
</script>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
def root():
    """Serve the single-page frontend."""
    return HTMLResponse(content=FRONTEND_HTML)
