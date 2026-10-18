#!/usr/bin/env bash
set -e

echo "============================================"
echo " Z-TRUST - AI Verification Firewall"
echo "============================================"
echo ""

# Check for .env file
if [ ! -f .env ]; then
    echo "[WARNING] .env file not found."
    echo "Copying .env.example to .env..."
    cp .env.example .env
    echo "Please edit .env and paste your GROQ_API_KEY."
    echo "The server will start but verification will be limited."
    echo ""
fi

# Activate virtual environment if present
if [ -d ".venv" ] && [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
else
    echo "[INFO] No local .venv found. Using current Python environment."
fi

HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8000}"

echo "Starting Z-TRUST server on ${HOST}:${PORT}..."
echo "  Web UI:   http://${HOST}:${PORT}"
echo "  API Docs: http://${HOST}:${PORT}/docs"
echo "  Health:   http://${HOST}:${PORT}/health"
echo ""

exec python3 -m uvicorn main:app --host "$HOST" --port "$PORT"
