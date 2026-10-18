# Z-TRUST — Evidence-Gated AI Decision Firewall

**Tagline:** The AI Firewall for the AI Age.

Z-TRUST verifies AI-generated answers against evidence before a human decision-maker relies on them. It uses Groq-powered LLMs combined with multi-provider web search retrieval (Groq browser search, Tavily, Serper, DuckDuckGo), deterministic security screening, and transparent decision rules.

> **Status:** Production-ready hackathon implementation with functional Groq integration and resilient multi-provider web retrieval. Scores are heuristic decision aids, not guarantees of truth or safety. Human review remains necessary.

## Features

- **Automated Evidence Retrieval** — Built-in search provider adapter supporting:
  - Groq official `browser_search` tool (`openai/gpt-oss-120b`, `openai/gpt-oss-20b`)
  - Alternative search adapters: Tavily API (`TAVILY_API_KEY`), Serper API (`SERPER_API_KEY`)
  - Zero-key web search fallback (DuckDuckGo via `httpx`)
- **Claim-Level Grounded Verification** — Extracts factual claims and evaluates each one against retrieved evidence using Groq LLM (`openai/gpt-oss-120b` or `qwen/qwen3.8-27b`).
- **Resilient Model Resolution** — Automatically discovers available models on your account; falls back seamlessly if daily token limits are reached.
- **Three-Tier Decisions** — `RELEASE`, `FLAG`, or `BLOCK` with deterministic precedence.
- **Security Screening** — Deterministic regex pattern matching for prompt injection and sensitive data exposure, independent of the LLM.
- **Honest Scoring** — Provider errors or missing evidence produce an explicit `INSUFFICIENT_EVIDENCE` state with `trust_score: null` (unassessed), never a false score of 0.
- **Embedded Web UI** — Single-page responsive interface at `/` with claim inspection, source links, security findings, and retry capability.
- **Safe Diagnostics** — `/health` endpoint reports system capabilities and active models without exposing API keys.

## Quick Start (Windows)

```powershell
# 1. Activate virtual environment
.venv\Scripts\Activate.ps1

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure your Groq API key
copy .env.example .env
# Edit .env and paste your Groq API key

# 4. Run the server (or double-click start.bat)
python -m uvicorn main:app --reload
```

Open **http://127.0.0.1:8000** for the web interface, or **http://127.0.0.1:8000/docs** for API docs.

## Quick Start (Linux)

```bash
cd z-trust-main
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env: nano .env

# Run server (or execute ./start.sh)
uvicorn main:app --host 0.0.0.0 --port 8000
```

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `GROQ_API_KEY` | Yes (for Groq) | — | Your Groq API key ([console.groq.com](https://console.groq.com)) |
| `GROQ_MODEL` | No | `openai/gpt-oss-120b` | Model for claim verification (`openai/gpt-oss-120b`, `qwen/qwen3.8-27b`) |
| `GROQ_SEARCH_MODEL` | No | `openai/gpt-oss-120b` | Model for Groq browser search (`openai/gpt-oss-120b`, `openai/gpt-oss-20b`) |
| `SEARCH_PROVIDER` | No | `groq` | Search provider: `groq`, `tavily`, `serper`, `duckduckgo` |
| `TAVILY_API_KEY` | No | — | Optional API key for Tavily AI Search |
| `SERPER_API_KEY` | No | — | Optional API key for Serper Google Search |
| `GROQ_TIMEOUT` | No | `30` | Network request timeout in seconds |
| `HOST` | No | `127.0.0.1` | Server bind host |
| `PORT` | No | `8000` | Server bind port |

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Web frontend |
| `GET` | `/health` | Diagnostic status (reports active models & search providers without secrets) |
| `POST` | `/verify` | Verify an AI answer — accepts `question`, `ai_answer`, and optional `reference_evidence` |

### Example Request

```json
{
  "question": "What city is the capital of Maharashtra?",
  "ai_answer": "Mumbai is the capital of Maharashtra."
}
```

Reference evidence is **optional**. When omitted, Z-TRUST automatically searches the web for verification sources.

## Decision Rules

| Priority | Decision | Trigger |
|---|---|---|
| 1 (highest) | **BLOCK** | Prompt injection OR privacy risk detected |
| 2 | **FLAG** | Insufficient evidence, provider failure, contradicted claims, or score < 60 |
| 3 | **RELEASE** | Claims supported by evidence, no contradictions, no security blocks |

A high trust score **never** overrides a security BLOCK. If retrieval fails, the score is reported as unassessed (`null`), not 0.

## Running Tests

```bash
# Run complete test suite (all provider calls mocked)
python -m pytest tests/ -v
```

## License

MIT License (see `LICENSE`).