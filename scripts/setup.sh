#!/usr/bin/env bash
# macOS / Linux setup for the WARROOM multi-agent architecture.
# Usage:  bash scripts/setup.sh
set -euo pipefail

echo "==> Creating virtual environment (.venv)"
python3 -m venv .venv

echo "==> Activating venv"
# shellcheck disable=SC1091
source .venv/bin/activate

echo "==> Installing dependencies"
python -m pip install --upgrade pip
pip install -r requirements.txt

if [ ! -f .env ]; then
  echo "==> Creating .env from .env.example (add your ANTHROPIC_API_KEY)"
  cp .env.example .env
fi

echo "==> Pulling a local model for the Reviewer subtree (mistral)"
echo "    (skip if you already have a model; edit OLLAMA_MODEL in .env)"
ollama pull mistral || echo "   ollama not found or pull skipped"

echo ""
echo "Done. Run:  python -m src.main"
