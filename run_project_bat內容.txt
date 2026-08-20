@echo off
chcp 65001 >nul
setlocal

cd /d "%~dp0"
title Taiwan AQI Dashboard Launcher

echo ============================================================
echo Taiwan AQI Prediction Dashboard - One Click Launcher
echo ============================================================
echo Project folder:
echo %CD%
echo.

echo [1/8] Checking Python...
set "BASE_PY_EXE="
set "BASE_PY_ARGS="

python --version >nul 2>&1
if not errorlevel 1 (
    set "BASE_PY_EXE=python"
)

if not defined BASE_PY_EXE (
    py -3 --version >nul 2>&1
    if not errorlevel 1 (
        set "BASE_PY_EXE=py"
        set "BASE_PY_ARGS=-3"
    )
)

if not defined BASE_PY_EXE (
    for %%P in (
        "%LocalAppData%\Programs\Python\Python312\python.exe"
        "%LocalAppData%\Programs\Python\Python311\python.exe"
        "%LocalAppData%\Programs\Python\Python310\python.exe"
        "%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
    ) do (
        if exist "%%~fP" (
            "%%~fP" --version >nul 2>&1
            if not errorlevel 1 (
                set "BASE_PY_EXE=%%~fP"
                set "BASE_PY_ARGS="
                goto :python_found
            )
        )
    )
)

:python_found
if not defined BASE_PY_EXE (
    echo [ERROR] Python was not found.
    echo Install Python 3.10 or newer and enable Add Python to PATH.
    pause
    exit /b 1
)

echo [2/8] Preparing virtual environment...
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -m pip --version >nul 2>&1
    if errorlevel 1 (
        echo [INFO] Existing .venv is broken. Recreating it...
        rmdir /s /q ".venv"
    )
)

if not exist ".venv\Scripts\python.exe" (
    "%BASE_PY_EXE%" %BASE_PY_ARGS% -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Failed to create .venv.
        pause
        exit /b 1
    )
)

set "PY=.venv\Scripts\python.exe"
set "AQI_TMP=%CD%\.tmp"
if not exist "%AQI_TMP%" mkdir "%AQI_TMP%"
set "TMP=%AQI_TMP%"
set "TEMP=%AQI_TMP%"
set "PIP_DISABLE_PIP_VERSION_CHECK=1"
set "PYTHONUTF8=1"
set "PYTEST_BASETEMP=.tmp\pytest_%RANDOM%%RANDOM%"
set "PYTEST_ADDOPTS=--basetemp=%PYTEST_BASETEMP% -p no:cacheprovider"
set "STREAMLIT_PORT="
set "CONSTRAINT_ARGS="
"%PY%" -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 12) else 1)" >nul 2>&1
if not errorlevel 1 if exist "requirements-lock-py312.txt" set "CONSTRAINT_ARGS=-c requirements-lock-py312.txt"

echo [3/8] Checking pip...
"%PY%" -m pip --version
if errorlevel 1 (
    echo [ERROR] pip is not available in .venv.
    pause
    exit /b 1
)

echo [4/8] Installing dependencies...
"%PY%" -m pip install --disable-pip-version-check -r requirements.txt %CONSTRAINT_ARGS%
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies from requirements.txt.
    pause
    exit /b 1
)

echo [5/8] Running sample pipeline...
"%PY%" run_all.py --mode sample
if errorlevel 1 (
    echo [ERROR] run_all.py failed.
    pause
    exit /b 1
)

echo [6/8] Checking public release contents...
"%PY%" scripts\validate_public_release.py
if errorlevel 1 (
    echo [ERROR] Public release guard failed.
    pause
    exit /b 1
)

echo [7/8] Running smoke test...
"%PY%" src\smoke_test.py
if errorlevel 1 (
    echo [ERROR] smoke test failed.
    pause
    exit /b 1
)

echo [8/8] Running pytest...
"%PY%" -m pytest -q
if errorlevel 1 (
    echo [ERROR] pytest failed.
    pause
    exit /b 1
)

echo ============================================================
echo All checks passed. Starting Streamlit Dashboard.
for /f "delims=" %%P in ('%PY% src\find_free_port.py') do set "STREAMLIT_PORT=%%P"
if not defined STREAMLIT_PORT set "STREAMLIT_PORT=8507"
echo AQI Dashboard URL: http://localhost:%STREAMLIT_PORT%
echo If the browser does not open, paste the URL above into Chrome.
echo ============================================================
echo.

if /I "%~1"=="--validate" set "AQI_SKIP_STREAMLIT=1"
if "%AQI_SKIP_STREAMLIT%"=="1" (
    echo [OK] Streamlit launch skipped by validation mode.
    exit /b 0
)

"%PY%" -m streamlit run app.py --server.port %STREAMLIT_PORT% --server.address localhost

pause
endlocal
