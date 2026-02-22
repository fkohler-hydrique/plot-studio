\
# Streamlit Dashboard App launcher (uv) - PowerShell
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Set-Location $PSScriptRoot

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "uv not found. Installing with official installer..."
    irm https://astral.sh/uv/install.ps1 | iex
}

uv python install 3.11
uv sync
uv run -- streamlit run app/app.py
