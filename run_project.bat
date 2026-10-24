@echo off
chcp 65001 >nul
setlocal

cd /d "%~dp0"
title Taiwan Air Lab Launcher

if /I "%~1"=="--help" goto :usage
if "%~1"=="" goto :arguments_ready
if /I "%~1"=="--validate" goto :arguments_ready
echo [ERROR] Unsupported argument: %~1
goto :usage_error

:arguments_ready

echo ============================================================
echo Taiwan Air Lab - One Click Launcher
echo ============================================================
echo Project folder:
echo %CD%
echo.

echo [1/9] Checking Python...
set "BASE_PY_EXE="
set "BASE_PY_ARGS="

python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1
if not errorlevel 1 (
    set "BASE_PY_EXE=python"
)

if not defined BASE_PY_EXE (
    py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1
    if not errorlevel 1 (
        set "BASE_PY_EXE=py"
        set "BASE_PY_ARGS=-3"
    )
)

if not defined BASE_PY_EXE (
    for %%P in (
        "%LocalAppData%\Programs\Python\Python312\python.exe"
        "%LocalAppData%\Programs\Python\Python311\python.exe"
    ) do (
        if exist "%%~fP" (
            "%%~fP" -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1
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
    echo [ERROR] Python 3.11 or newer was not found.
    echo Install a supported Python version and enable Add Python to PATH.
    goto :fail
)

echo [2/9] Preparing virtual environment...
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] Existing .venv uses unsupported Python. Preserve or move it before creating a new environment.
        goto :fail
    ) else (
        ".venv\Scripts\python.exe" -m pip --version >nul 2>&1
        if errorlevel 1 (
            echo [ERROR] Existing .venv is broken. Preserve or move it before creating a new environment.
            goto :fail
        )
    )
)

if not exist ".venv\Scripts\python.exe" (
    "%BASE_PY_EXE%" %BASE_PY_ARGS% -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Failed to create .venv.
        goto :fail
    )
)

set "PY=.venv\Scripts\python.exe"
set "PIP_DISABLE_PIP_VERSION_CHECK=1"
set "PYTHONUTF8=1"
set "PYTEST_BASETEMP=.pytest-tmp-%RANDOM%%RANDOM%"
set "CONSTRAINT_ARGS="
"%PY%" -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 12) else 1)" >nul 2>&1
if not errorlevel 1 if exist "requirements-lock-py312.txt" set "CONSTRAINT_ARGS=-c requirements-lock-py312.txt"

echo [3/9] Installing Python dependencies...
"%PY%" -m pip install --disable-pip-version-check --upgrade "pip>=26.2"
if errorlevel 1 goto :dependency_fail
"%PY%" -m pip install --disable-pip-version-check -r requirements.txt %CONSTRAINT_ARGS%
if errorlevel 1 goto :dependency_fail
if /I "%~1"=="--validate" (
    "%PY%" -m pip install --disable-pip-version-check -r requirements-security.txt
    if errorlevel 1 goto :dependency_fail
)
"%PY%" -m pip check
if errorlevel 1 goto :dependency_fail

echo [4/9] Generating data and exporting the analysis for the web app...
"%PY%" run_all.py --mode sample
if errorlevel 1 (
    echo [ERROR] run_all.py failed.
    goto :fail
)

echo [5/9] Compiling Python sources and checking public release contents...
"%PY%" -m compileall -q run_all.py src scripts tests
if errorlevel 1 goto :fail
"%PY%" scripts\validate_public_release.py
if errorlevel 1 goto :fail

echo [6/9] Running pytest...
"%PY%" -W error -m pytest -q -p no:cacheprovider --basetemp "%PYTEST_BASETEMP%"
if errorlevel 1 (
    echo [ERROR] pytest failed.
    goto :fail
)
if exist "%PYTEST_BASETEMP%" rmdir /s /q "%PYTEST_BASETEMP%" >nul 2>nul

if /I "%~1"=="--validate" (
    echo [SECURITY] Running Bandit, Ruff and a strict dependency audit...
    "%PY%" -m bandit -q --severity-level high --confidence-level high -r src scripts run_all.py
    if errorlevel 1 goto :fail
    "%PY%" -m ruff check src scripts tests run_all.py
    if errorlevel 1 goto :fail
    "%PY%" -m pip_audit --strict --progress-spinner off
    if errorlevel 1 goto :fail
)

echo [7/9] Checking Node.js...
where node >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Node.js 22 or newer was not found.
    echo Install Node.js from https://nodejs.org/, then run this file again.
    goto :fail
)

echo [8/9] Installing and checking the web app...
pushd web
call npm ci --no-audit --no-fund
if errorlevel 1 goto :web_fail
if /I "%~1"=="--validate" (
    call npm run typecheck
    if errorlevel 1 goto :web_fail
    call npm run lint
    if errorlevel 1 goto :web_fail
    call npm run coverage
    if errorlevel 1 goto :web_fail
)
call npm run build
if errorlevel 1 goto :web_fail
if /I "%~1"=="--validate" (
    call npm run size
    if errorlevel 1 goto :web_fail
    popd
    echo ============================================================
    echo Validation completed successfully. Web server launch skipped.
    echo ============================================================
    endlocal
    exit /b 0
)

echo [9/9] Starting Taiwan Air Lab at http://127.0.0.1:4173
echo Press Ctrl+C to stop the site. This window must stay open.
call npm run preview -- --host 127.0.0.1
popd
endlocal
exit /b 0

:web_fail
popd
echo [ERROR] The web app could not be installed, checked or built.
goto :fail

:dependency_fail
echo [ERROR] Could not install the required Python packages. Check the internet connection and try again.
goto :fail

:fail
echo.
echo [ERROR] run_project.bat failed.
if /I not "%~1"=="--validate" pause
endlocal
exit /b 1

:usage
echo Usage: run_project.bat [--validate ^| --help]
echo   no argument   Rebuild the sample analysis, run the tests, build the web app and open it locally.
echo   --validate    Run every Python, security and web quality gate without starting the site.
endlocal
exit /b 0

:usage_error
echo Use run_project.bat --help for supported options.
endlocal
exit /b 2
