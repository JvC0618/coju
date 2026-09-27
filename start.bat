@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" goto install
where py >nul 2>nul
if errorlevel 1 (python -m venv .venv) else (py -3.12 -m venv .venv)
if errorlevel 1 goto failed
:install
if exist ".venv\coju-ready" goto run
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto failed
type nul > ".venv\coju-ready"
:run
".venv\Scripts\python.exe" -m streamlit run app.py --server.address 127.0.0.1 --browser.gatherUsageStats false
goto end
:failed
echo Install Python 3.12 and check your network. See README.md.
pause
:end
endlocal

