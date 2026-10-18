# Z-TRUST Architecture

## System Flow

```
┌──────────────────────────────────────────────────────┐
│                  User / Frontend                      │
│  Inputs: question + AI answer (+ optional evidence)   │
└──────────────────────┬───────────────────────────────┘
                       │ POST /verify
                       ▼
┌──────────────────────────────────────────────────────┐
│                  FastAPI Backend                      │
│  main.py — orchestrates the verification pipeline     │
└──┬──────────────┬────────────────┬───────────────────┘
   │              │                │
   ▼              ▼                ▼
┌────────┐  ┌───────────────┐  ┌──────────────────────┐
│Security│  │  Evidence      │  │  Trust Engine         │
│Checker │  │  Pipeline      │  │  (trust_engine.py)    │
│(regex) │  │                │  │                       │
│        │  │ 1. Web Search  │  │ • Score = weighted    │
│• Inject│  │    (compound-  │  │   composite           │
│  ion   │  │     beta-mini) │  │ • Decision = rules    │
│• Privacy│ │ 2. Claim       │  │ • BLOCK > FLAG >      │
│        │  │    Extract +   │  │   RELEASE             │
│  No LLM│  │    Verify      │  │                       │
│  needed│  │    (llama-3.3) │  │ Score never overrides  │
│        │  │                │  │ a security block       │
└────────┘  └───────────────┘  └──────────────────────┘
```

## Components

### 1. Request Intake (`main.py`)
- Receives question, AI answer, and optional reference evidence
- Reference evidence is **not required** — auto-retrieval handles the normal case
- Orchestrates all checks and produces the final response

### 2. Security Checker (`security_checker.py`)
- **Deterministic** regex-based pattern matching (no LLM dependency)
- Prompt injection detection: known attack phrases
- Privacy risk detection: SSN-like, credit card, API key, bearer token patterns
- Results include limitation notes acknowledging false positive/negative possibilities
- Runs independently before and regardless of LLM verification

### 3. Evidence Pipeline (`evidence_checker.py` + `groq_client.py`)

#### Stage 1: Evidence Retrieval
- If user provides reference evidence → use it directly
- If not → call Groq `compound-beta-mini` with built-in web search
- Extracts source titles, URLs, and snippets from `executed_tools` response
- Falls back gracefully if search fails or returns no results

#### Stage 2: Claim Verification
- Sends the AI answer + retrieved evidence to `llama-3.3-70b-versatile`
- Extracts factual claims from the answer
- Classifies each claim: `SUPPORTED`, `CONTRADICTED`, or `INSUFFICIENT_EVIDENCE`
- Cross-validates cited passages against actual evidence (anti-hallucination check)
- System prompt treats evidence as untrusted data, not instructions

#### Fallback
- If Groq is not configured → uses original lexical overlap heuristic
- If retrieval fails → reports `INSUFFICIENT_EVIDENCE` honestly
- Never fabricates search results or marks unverified claims as supported

### 4. Trust Engine (`trust_engine.py`)

#### Score Formula
```
base = evidence_coverage × 0.50
     + source_validity × 0.20
     + reference_bonus × 0.30

penalties = contradiction(15) + injection(10) + privacy(5)

trust_score = clamp(base - penalties, 0, 100)
```

#### Decision Rules (Deterministic Precedence)
| Priority | Decision | Condition |
|---|---|---|
| 1 | BLOCK | Prompt injection OR privacy risk signal |
| 2 | FLAG | No reference, contradictions, insufficient evidence + low coverage, or score < 60 |
| 3 | RELEASE | Evidence supports claims, no blocking rules |

**A high score never overrides a mandatory BLOCK.** The trust score is supplementary context; the decision is authoritative.

### 5. Frontend (embedded in `main.py`)
- Single-page responsive HTML/CSS/JS served at `/`
- Question input, AI answer input, optional collapsed evidence input
- Real-time loading states and error messages
- Claim-level verification results with color-coded badges
- Source links (clickable URLs)
- Security screening results
- Retry button for API failures
- All untrusted content is escaped via `textContent`

## Data Flow Integrity

- Evidence from web search is treated as **untrusted data**
- System prompts instruct the LLM to ignore embedded instructions in evidence
- Cited passages are cross-validated against actual retrieved content
- LLM training knowledge is explicitly excluded as evidence
- The system clearly distinguishes "supported by evidence" from "plausible-sounding"

## Error Handling

- Missing API key → graceful fallback with clear reporting
- Invalid credentials → specific error message (no stack traces)
- Rate limits → specific error with retry suggestion
- Timeouts → configurable via `GROQ_TIMEOUT`, specific error message
- Malformed LLM responses → error reported, no fabricated results
- No search results → `INSUFFICIENT_EVIDENCE` state

## Security Model

- API keys loaded from `.env` via `python-dotenv`, never exposed in frontend/logs/responses
- Security checks are deterministic and LLM-independent
- Pattern matching acknowledges false positive/negative limitations
- No unnecessary logging of user content or credentials
- Input validation via Pydantic with length limits
