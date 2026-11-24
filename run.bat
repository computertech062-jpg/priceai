@echo off
REM ============================================================
REM  PriceAI - one-click start
REM  Double-click this file. It will:
REM    1. install missing Python packages (first time only)
REM    2. create .env with a SECRET_KEY (first time only)
REM    3. train the model if it doesn't exist (first time only)
REM    4. start the server and open the website in your browser
REM  To stop: close this window (or press Ctrl+C).
REM ============================================================
setlocal
cd /d "%~dp0"
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
if "%PORT%"=="" set PORT=8000
set URL=http://127.0.0.1:%PORT%

REM --- already running? just open the browser ---
python -c "import urllib.request; urllib.request.urlopen('%URL%/api/health', timeout=2)" >nul 2>&1
if not errorlevel 1 (
  echo PriceAI is already running: %URL%
  if not defined NO_BROWSER start "" "%URL%"
  exit /b 0
)

REM --- Python ---
python --version >nul 2>&1
if errorlevel 1 (
  echo [X] Python was not found. Install Python 3.11+ from https://www.python.org and tick "Add to PATH".
  pause
  exit /b 1
)

REM --- packages (first time only) ---
python -c "import fastapi, uvicorn, sqlalchemy, sklearn, pandas, jwt, dotenv" >nul 2>&1
if errorlevel 1 (
  echo Installing required packages, please wait...
  python -m pip install -r requirements.txt
  if errorlevel 1 ( echo [X] Package installation failed. & pause & exit /b 1 )
)

REM --- .env with a fixed SECRET_KEY, so users stay logged in after a restart ---
if not exist ".env" (
  python -c "import secrets; open('.env','w').write('SECRET_KEY=' + secrets.token_urlsafe(48) + '\n')"
  echo Created .env with a new SECRET_KEY.
)

REM --- model (first time only, about 1-2 minutes) ---
if not exist "backend\artifacts\model.joblib" (
  echo Training the model for the first time, please wait...
  python -m backend.ml.train
  if errorlevel 1 ( echo [X] Training failed. & pause & exit /b 1 )
)

REM --- open the browser as soon as the server answers ---
if not defined NO_BROWSER (
  start "" /b python -c "import time, urllib.request, webbrowser; exec('for _ in range(90):\n try:\n  urllib.request.urlopen(\"%URL%/api/health\", timeout=2); webbrowser.open(\"%URL%\"); break\n except Exception: time.sleep(1)')"
)

echo.
echo  PriceAI is starting:  %URL%
echo  Close this window to stop the server.
echo.
python -m uvicorn backend.main:app --host 127.0.0.1 --port %PORT%
if errorlevel 1 pause
