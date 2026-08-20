from __future__ import annotations

from pathlib import Path

from src.release_guard import REQUIRED_PUBLIC_PATHS, validate_public_release


def _write_public_fixture(root: Path, tracked_files: list[str]) -> None:
    for relative_path in REQUIRED_PUBLIC_PATHS:
        path = root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("placeholder\n", encoding="utf-8")
    (root / "README.md").write_text(
        '<img src="docs/screenshots/overview.png">\n', encoding="utf-8"
    )
    asset = root / "docs/screenshots/overview.png"
    asset.parent.mkdir(parents=True, exist_ok=True)
    asset.write_bytes(b"png")
    tracked_files.append("docs/screenshots/overview.png")


def test_public_release_guard_accepts_required_files_and_tracked_assets(tmp_path: Path) -> None:
    tracked_files = list(REQUIRED_PUBLIC_PATHS)
    _write_public_fixture(tmp_path, tracked_files)

    result = validate_public_release(tmp_path, tracked_files)

    assert result["passed"] is True
    assert result["missing_public_paths"] == []
    assert result["untracked_public_paths"] == []
    assert result["missing_readme_assets"] == []
    assert result["untracked_readme_assets"] == []
    assert result["sensitive_paths"] == []


def test_public_release_guard_blocks_generated_files_and_credentials(tmp_path: Path) -> None:
    tracked_files = list(REQUIRED_PUBLIC_PATHS)
    _write_public_fixture(tmp_path, tracked_files)
    tracked_files += ["data/processed/features.csv", "notes.txt", ".env", ".streamlit/secrets.toml"]
    (tmp_path / "data/processed").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data/processed/features.csv").write_text("generated", encoding="utf-8")
    (tmp_path / ".env").write_text("AQI_API_URL=https://example.com\n", encoding="utf-8")
    (tmp_path / ".streamlit").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".streamlit/secrets.toml").write_text("token = 'redacted'\n", encoding="utf-8")
    fake_key = "A" + "1234567890123456789"
    (tmp_path / "notes.txt").write_text("api_key = '" + fake_key + "'", encoding="utf-8")

    result = validate_public_release(tmp_path, tracked_files)

    assert result["passed"] is False
    assert "data/processed/features.csv" in result["generated_artifacts"]
    assert "notes.txt" in result["credential_hits"]
    assert ".env" in result["sensitive_paths"]
    assert ".streamlit/secrets.toml" in result["sensitive_paths"]


def test_public_release_guard_requires_public_files_to_be_tracked(tmp_path: Path) -> None:
    tracked_files = list(REQUIRED_PUBLIC_PATHS)
    _write_public_fixture(tmp_path, tracked_files)
    tracked_files.remove("docs/deployment.md")

    result = validate_public_release(tmp_path, tracked_files)

    assert result["passed"] is False
    assert result["missing_public_paths"] == []
    assert result["untracked_public_paths"] == ["docs/deployment.md"]
