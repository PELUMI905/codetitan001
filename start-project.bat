@echo off
setlocal
cd /d "%~dp0"
if not exist backend\.venv (
  python -m venv backend\.venv
)
call backend\.venv\Scripts\activate.bat
pip install -r backend\requirements.txt
if not exist backend\.env copy backend\.env.example backend\.env
start "CodeTitan Travel API" cmd /k "cd /d ""%~dp0backend"" && call .venv\Scripts\activate.bat && uvicorn main:app --reload"
cd /d "%~dp0frontend"
if not exist node_modules npm install
start "CodeTitan Travel React" cmd /k "cd /d ""%~dp0frontend"" && npm run dev"
endlocal
