\
@echo off
setlocal enabledelayedexpansion

REM ------------------------------------------------------------
REM Streamlit Dashboard App launcher (uv)
REM - Installs uv if needed
REM - Installs Python 3.11 (managed by uv)
REM - Syncs dependencies
REM - Runs the app
REM ------------------------------------------------------------

cd /d "%~dp0"

echo.
echo ================================
echo  Streamlit Dashboard App (uv)
echo ================================
echo.

REM --- Check uv
where uv >nul 2>nul
if %errorlevel%==0 goto :HAVE_UV

echo uv not found on PATH. Attempting to install...

REM 1) Try WinGet (preferred if available)
where winget >nul 2>nul
if %errorlevel%==0 (
  echo Installing uv via WinGet...
  winget install --id=astral-sh.uv -e --silent
)

REM Re-check uv
where uv >nul 2>nul
if %errorlevel%==0 goto :HAVE_UV

REM 2) Fallback to official PowerShell installer
echo Installing uv via PowerShell installer...
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

REM Re-check uv (may require new shell if PATH updated)
where uv >nul 2>nul
if %errorlevel%==0 goto :HAVE_UV

echo.
echo ERROR: uv still not available. 
echo - Try opening a new terminal and re-running this script, or
echo - Install uv manually (see README).
echo.
pause
exit /b 1

:HAVE_UV
echo uv detected.

REM --- Ensure pinned Python is available (3.11)
echo Ensuring Python 3.11 is installed (managed by uv)...
uv python install 3.11

REM --- Create/Update environment + lockfile
echo Syncing project environment (.venv)...
uv sync

REM --- Run Streamlit in the uv-managed env
echo Launching Streamlit...
uv run -- streamlit run app/app.py

endlocal
