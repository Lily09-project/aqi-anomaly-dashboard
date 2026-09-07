@echo off
chcp 65001 >nul
setlocal

cd /d "%~dp0"
title Taiwan AQI Dashboard Launcher

if /I "%~1"=="--help" goto :usage
if "%~1"=="" goto :arguments_ready
if /I "%~1"=="--validate" goto :arguments_ready
echo [ERROR] Unsupported argument: %~1
goto :usage_error

:arguments_ready

echo ============================================================
echo Taiwan AQI Prediction Dashboard - One Click Launcher
echo ============================================================
echo Project folder:
echo %CD%
echo.

echo [1/10] Checking Python...
set "BASE_PY_EXE="
set "BASE_PY_ARGS="

python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if not errorlevel 1 (
    set "BASE_PY_EXE=python"
)

if not defined BASE_PY_EXE (
    py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
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
    ) do (
        if exist "%%~fP" (
            "%%~fP" -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
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
    echo [ERROR] Python 3.10 or newer was not found.
    echo Install a supported Python version and enable Add Python to PATH.
    if /I not "%~1"=="--validate" pause
    exit /b 1
)

echo [2/10] Preparing virtual environment...
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
    if errorlevel 1 (
        echo [INFO] Existing .venv uses unsupported Python. Recreating it...
        rmdir /s /q ".venv"
    ) else (
        ".venv\Scripts\python.exe" -m pip --version >nul 2>&1
        if errorlevel 1 (
            echo [INFO] Existing .venv is broken. Recreating it...
            rmdir /s /q ".venv"
        )
    )
)

if not exist ".venv\Scripts\python.exe" (
    "%BASE_PY_EXE%" %BASE_PY_ARGS% -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Failed to create .venv.
        if /I not "%~1"=="--validate" pause
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
set "PYTEST_BASETEMP=.pytest-tmp-%RANDOM%%RANDOM%"
set "PYTEST_ADDOPTS=--basetemp=%PYTEST_BASETEMP% -p no:cacheprovider"
set "STREAMLIT_PORT="
set "CONSTRAINT_ARGS="
set "AQI_CONSTRAINTS_APPLIED="
"%PY%" -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 12) else 1)" >nul 2>&1
if not errorlevel 1 if exist "requirements-lock-py312.txt" (
    set "CONSTRAINT_ARGS=-c requirements-lock-py312.txt"
    set "AQI_CONSTRAINTS_APPLIED=1"
)

echo [3/10] Checking pip...
"%PY%" -m pip --version
if errorlevel 1 (
    echo [ERROR] pip is not available in .venv.
    if /I not "%~1"=="--validate" pause
    exit /b 1
)

echo [4/10] Installing dependencies...
"%PY%" -m pip install --disable-pip-version-check --upgrade "pip>=26.2"
if errorlevel 1 (
    echo [ERROR] Failed to upgrade pip to the audited minimum version.
    if /I not "%~1"=="--validate" pause
    exit /b 1
)
"%PY%" -m pip install --disable-pip-version-check -r requirements.txt %CONSTRAINT_ARGS%
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies from requirements.txt.
    if /I not "%~1"=="--validate" pause
    exit /b 1
)

if /I "%~1"=="--validate" (
    "%PY%" -m pip install --disable-pip-version-check -r requirements-security.txt
    if errorlevel 1 (
        echo [ERROR] Failed to install validation security tools.
        exit /b 1
    )
)

echo [5/10] Running sample pipeline...
"%PY%" run_all.py --mode sample
if errorlevel 1 (
    echo [ERROR] run_all.py failed.
    if /I not "%~1"=="--validate" pause
    exit /b 1
)

echo [6/10] Checking installed dependency consistency...
"%PY%" -m pip check
if errorlevel 1 (
    echo [ERROR] Installed dependencies are inconsistent.
    if /I not "%~1"=="--validate" pause
    exit /b 1
)

echo [7/10] Compiling Python sources...
"%PY%" -m compileall -q app.py run_all.py src scripts tests
if errorlevel 1 (
    echo [ERROR] Python compilation check failed.
    if /I not "%~1"=="--validate" pause
    exit /b 1
)

echo [8/10] Checking public release contents...
"%PY%" scripts\validate_public_release.py
if errorlevel 1 (
    echo [ERROR] Public release guard failed.
    if /I not "%~1"=="--validate" pause
    exit /b 1
)

echo [9/10] Running smoke test...
"%PY%" src\smoke_test.py
if errorlevel 1 (
    echo [ERROR] smoke test failed.
    if /I not "%~1"=="--validate" pause
    exit /b 1
)

echo [10/10] Running pytest...
"%PY%" -W error -m pytest -q -p no:cacheprovider --basetemp "%PYTEST_BASETEMP%"
if errorlevel 1 (
    echo [ERROR] pytest failed.
    if /I not "%~1"=="--validate" pause
    exit /b 1
)
if exist "%PYTEST_BASETEMP%" rmdir /s /q "%PYTEST_BASETEMP%" >nul 2>nul

if /I "%~1"=="--validate" (
    echo [SECURITY 1/2] Running high-confidence Bandit scan...
    "%PY%" -m bandit -q --severity-level high --confidence-level high -r app.py src scripts
    if errorlevel 1 exit /b 1
    echo [SECURITY 2/2] Running strict dependency vulnerability audit...
    "%PY%" -m pip_audit --strict --progress-spinner off
    if errorlevel 1 exit /b 1
    set "AQI_SKIP_STREAMLIT=1"
)
if "%AQI_SKIP_STREAMLIT%"=="1" (
    echo ============================================================
    echo Validation completed successfully. Streamlit launch skipped.
    echo ============================================================
    exit /b 0
)

echo ============================================================
echo All checks passed. Starting Streamlit Dashboard.
for /f "delims=" %%P in ('%PY% src\find_free_port.py') do set "STREAMLIT_PORT=%%P"
if not defined STREAMLIT_PORT set "STREAMLIT_PORT=8507"
echo AQI Dashboard URL: http://localhost:%STREAMLIT_PORT%
echo If the browser does not open, paste the URL above into Chrome.
echo ============================================================
echo.

"%PY%" -m streamlit run app.py --server.port %STREAMLIT_PORT% --server.address localhost

pause
endlocal
exit /b 0

:usage
echo Usage: run_project.bat [--validate ^| --help]
echo   no argument   Rebuild sample artifacts, verify them, and start Streamlit.
echo   --validate    Run pipeline, zero-warning tests, compile, release, smoke, and security checks only.
endlocal
exit /b 0

:usage_error
echo Use run_project.bat --help for supported options.
endlocal
exit /b 2
