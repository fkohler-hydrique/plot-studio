# Streamlit Dashboard App (uv)

This repo uses **uv** to:
- install a pinned Python version (via `.python-version`)
- create a project-local virtual environment (`.venv`)
- install dependencies from `pyproject.toml` (and lock them in `uv.lock`)

## Quick start (Windows)

Double-click:

- `run_app.bat`

It will:
1) install `uv` if missing (Winget first, then PowerShell installer fallback)
2) ensure Python 3.11 is installed
3) `uv sync` to create `.venv` + install deps
4) launch the Streamlit app

## Quick start (macOS / Linux)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv python install 3.11
uv sync
uv run -- streamlit run app/app.py
```

## Notes
- `uv.lock` is created/updated automatically by uv the first time you run `uv sync`/`uv run`. Commit it for reproducible installs.
- Streamlit config is in `.streamlit/config.toml`.
