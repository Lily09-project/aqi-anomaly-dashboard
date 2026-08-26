from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_dashboard_exposes_keyboard_skip_link() -> None:
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    styles_source = (ROOT / "src" / "dashboard" / "styles.py").read_text(encoding="utf-8")

    assert 'class="skip-link"' in app_source
    assert 'href="#dashboard-main"' in app_source
    assert 'id="dashboard-main"' in app_source
    assert 'tabindex="-1"' in app_source
    assert ".skip-link" in styles_source
    assert ".skip-link:focus-visible" in styles_source
    assert "scroll-margin-top" in styles_source


def test_validation_mode_does_not_claim_dashboard_will_start() -> None:
    launcher_source = (ROOT / "run_project.bat").read_text(encoding="utf-8")

    validation_gate = launcher_source.index('if /I "%~1"=="--validate"')
    start_message = launcher_source.index("Starting Streamlit Dashboard")

    assert validation_gate < start_message
    assert "Validation completed successfully. Streamlit launch skipped." in launcher_source


def test_pytest_defaults_to_project_local_temp_directory() -> None:
    pytest_config = (ROOT / "pytest.ini").read_text(encoding="utf-8")

    assert "--basetemp=.tmp/pytest-default" in pytest_config


def test_streamlit_runtime_contract_matches_dashboard_api() -> None:
    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    constraints = (ROOT / "requirements-lock-py312.txt").read_text(encoding="utf-8")

    assert "streamlit>=1.58,<2" in requirements
    assert "streamlit==1.58.0" in constraints


def test_launcher_rejects_unsupported_python_versions() -> None:
    launcher_source = (ROOT / "run_project.bat").read_text(encoding="utf-8")

    assert launcher_source.count("sys.version_info >= (3, 10)") >= 3
    assert "Python 3.10 or newer was not found" in launcher_source


def test_security_audit_checks_the_locked_dependency_graph() -> None:
    workflow = (ROOT / ".github" / "workflows" / "security.yml").read_text(encoding="utf-8")

    assert "pip-audit -r requirements-lock-py312.txt --no-deps" in workflow


def test_overview_map_and_priority_stack_on_tablet() -> None:
    overview = (ROOT / "src" / "dashboard" / "pages" / "overview.py").read_text(encoding="utf-8")
    styles = (ROOT / "src" / "dashboard" / "styles.py").read_text(encoding="utf-8")

    assert 'st.container(key="overview_map_queue")' in overview
    assert ".st-key-overview_map_queue" in styles
    assert "flex-direction: column" in styles
def test_quality_gate_executes_windows_launcher() -> None:
    workflow = (ROOT / ".github" / "workflows" / "quality.yml").read_text(encoding="utf-8")

    assert "windows-launcher:" in workflow
    assert "runs-on: windows-latest" in workflow
    assert "run: run_project.bat --validate" in workflow
