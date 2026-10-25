from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _launcher() -> str:
    return (ROOT / "run_project.bat").read_text(encoding="utf-8")


def test_validation_mode_never_claims_the_site_will_start() -> None:
    launcher = _launcher()
    validation_exit = launcher.index("Validation completed successfully. Web server launch skipped.")
    start_message = launcher.index("Starting Taiwan Air Lab")
    assert validation_exit < start_message


def test_launcher_validation_is_complete_and_unknown_arguments_fail_closed() -> None:
    launcher = _launcher()
    for command in (
        '"%PY%" -m pip check',
        '"%PY%" run_all.py --mode sample',
        '"%PY%" -m compileall -q run_all.py src scripts tests',
        "scripts\\validate_public_release.py",
        '"%PY%" -W error -m pytest -q -p no:cacheprovider --basetemp "%PYTEST_BASETEMP%"',
        '"%PY%" -m pip install --disable-pip-version-check -r requirements-security.txt',
        '"%PY%" -m pip install --disable-pip-version-check --upgrade "pip>=26.2"',
        '"%PY%" -m bandit -q --severity-level high --confidence-level high -r src scripts run_all.py',
        '"%PY%" -m ruff check src scripts tests run_all.py',
        '"%PY%" -m pip_audit --strict --progress-spinner off',
        "call npm ci --no-audit --no-fund",
        "call npm run typecheck",
        "call npm run lint",
        "call npm run coverage",
        "call npm run build",
        "call npm run size",
    ):
        assert command in launcher, command
    assert 'if /I "%~1"=="--help" goto :usage' in launcher
    assert "[ERROR] Unsupported argument: %~1" in launcher
    assert "exit /b 2" in launcher
    assert 'rmdir /s /q "%PYTEST_BASETEMP%"' in launcher
    assert 'if /I not "%~1"=="--validate" pause' in launcher


def test_launcher_serves_the_site_on_loopback_only() -> None:
    launcher = _launcher()
    assert "call npm run preview -- --host 127.0.0.1" in launcher
    assert "0.0.0.0" not in launcher


def test_launcher_rejects_unsupported_python_versions() -> None:
    launcher = _launcher()
    assert launcher.count("sys.version_info >= (3, 11)") >= 3
    assert "Python 3.11 or newer was not found" in launcher


def test_launcher_preserves_existing_environments_on_validation_failure() -> None:
    launcher = _launcher()
    assert 'rmdir /s /q ".venv"' not in launcher
    assert "Existing .venv uses unsupported Python. Preserve or move it" in launcher
    assert "Existing .venv is broken. Preserve or move it" in launcher


def test_pytest_defaults_to_project_local_temp_directory() -> None:
    assert "--basetemp=.pytest-tmp" in (ROOT / "pytest.ini").read_text(encoding="utf-8")


def test_security_audit_checks_the_locked_dependency_graph() -> None:
    workflow = (ROOT / ".github" / "workflows" / "security.yml").read_text(encoding="utf-8")
    assert "python -m pip_audit -r requirements-lock-py312.txt --no-deps" in workflow
    assert "npm audit" in workflow


def test_quality_gate_executes_windows_launcher_and_the_web_gate() -> None:
    workflow = (ROOT / ".github" / "workflows" / "quality.yml").read_text(encoding="utf-8")
    assert "windows-launcher:" in workflow
    assert "runs-on: windows-latest" in workflow
    assert "run_project.bat --validate" in workflow
    for step in ("npm run typecheck", "npm run lint", "npm run coverage", "npm run size", "npm run e2e"):
        assert step in workflow, step


def test_pages_publishes_only_the_built_web_app() -> None:
    workflow = (ROOT / ".github" / "workflows" / "pages.yml").read_text(encoding="utf-8")
    assert "path: web/dist" in workflow
    assert "smoke:" in workflow
