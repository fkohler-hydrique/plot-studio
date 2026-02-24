# Streamlit Dashboard App (uv)

This project uses `uv` to manage Python and dependencies for a Streamlit dashboard.

## Quick Start (Windows)

Run:

```bat
run_app.bat
```

The launcher will:

1. Detect `uv` (or install it: WinGet first, then PowerShell fallback).
2. Ensure Python `3.11` is available.
3. Run `uv sync` to install/update dependencies in `.venv`.
4. Start Streamlit with `uv run -- streamlit run app/app.py`.
5. Open your browser automatically once the Streamlit local URL is available.

## Logging

- The full launcher output is shown in the terminal and written to `logs/run_app_YYYYMMDD_HHMMSS.log`.
- Log rotation is automatic: only the 5 most recent log files are kept.
- Logs are ignored by git via `.gitignore`.

## Launcher Files

- `run_app.bat`: Windows entry point (calls PowerShell launcher).
- `run_app.ps1`: Main launcher logic (setup, logging, rotation, app start).

## Manual Run (Any OS with uv installed)

```bash
uv python install 3.11
uv sync
uv run -- streamlit run app/app.py
```

## Notes

- `uv.lock` should be committed for reproducible installs.
- Streamlit config is in `.streamlit/config.toml`.
