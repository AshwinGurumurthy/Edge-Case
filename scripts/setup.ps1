# Windows / PowerShell setup for the WARROOM multi-agent architecture.
# Usage:  ./scripts/setup.ps1
$ErrorActionPreference = "Stop"

Write-Host "==> Creating virtual environment (.venv)"
python -m venv .venv

Write-Host "==> Activating venv"
. .\.venv\Scripts\Activate.ps1

Write-Host "==> Installing dependencies"
python -m pip install --upgrade pip
pip install -r requirements.txt

if (-not (Test-Path ".env")) {
    Write-Host "==> Creating .env from .env.example (add your ANTHROPIC_API_KEY)"
    Copy-Item .env.example .env
}

Write-Host "==> Pulling a local model for the Reviewer subtree (mistral)"
Write-Host "    (skip if you already have a model; edit OLLAMA_MODEL in .env)"
try { ollama pull mistral } catch { Write-Host "   ollama not found or pull skipped" }

Write-Host "`nDone. Run:  python -m src.main"
