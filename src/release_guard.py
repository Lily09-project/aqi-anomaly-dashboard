from __future__ import annotations

import fnmatch
import re
import subprocess
from pathlib import Path
from typing import Iterable


REQUIRED_PUBLIC_PATHS = (
    ".env.example",
    ".gitignore",
    "README.md",
    "app.py",
    "config.yaml",
    "requirements.txt",
    "run_project.bat",
)

GENERATED_TRACKING_PATTERNS = (
    "data/raw/*.csv",
    "data/sample/*.csv",
    "data/processed/*.csv",
    "models/*.joblib",
    "reports/figures/*.png",
    "reports/metrics/*.json",
)

CREDENTIAL_PATTERNS = (
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN (?:RSA|OPENSSH|EC|DSA) PRIVATE KEY-----"),
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"api[_-]?key\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{16,}", re.IGNORECASE),
)


SENSITIVE_EXACT_PATHS = {
    ".streamlit/secrets.toml",
    "secrets.json",
    "secrets.toml",
    "config/secrets.json",
    "config/secrets.yaml",
}


def _tracked_files(repo_root: Path) -> list[str]:
    result = subprocess.run(
        ["git", "-C", str(repo_root), "ls-files"],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return [line.strip().replace("\\", "/") for line in result.stdout.splitlines() if line.strip()]


def _matches_any(path: str, patterns: Iterable[str]) -> bool:
    return any(fnmatch.fnmatch(path, pattern) for pattern in patterns)


def _is_sensitive_path(path: str) -> bool:
    normalized = path.replace("\\", "/").strip("/").lower()
    basename = normalized.rsplit("/", 1)[-1]
    if basename == ".env":
        return True
    if basename.startswith(".env.") and basename != ".env.example":
        return True
    return normalized in SENSITIVE_EXACT_PATHS or basename in {"secrets.json", "secrets.toml"}


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def _readme_assets(repo_root: Path) -> list[str]:
    readme = _read_text(repo_root / "README.md")
    assets = re.findall(r"(?:src|href)=\"([^\"]+)\"", readme)
    return [asset.replace("\\", "/") for asset in assets if asset.startswith("docs/")]


def validate_public_release(repo_root: str | Path, tracked_files: Iterable[str] | None = None) -> dict[str, object]:
    """Validate that the repository is safe and complete for a public release."""
    root = Path(repo_root).resolve()
    tracked = sorted(set(tracked_files if tracked_files is not None else _tracked_files(root)))
    missing_public_paths = [path for path in REQUIRED_PUBLIC_PATHS if not (root / path).exists()]
    missing_readme_assets = [
        asset for asset in _readme_assets(root) if not (root / asset).exists()
    ]
    untracked_readme_assets = [
        asset for asset in _readme_assets(root) if asset not in tracked
    ]
    generated_artifacts = [
        path for path in tracked if _matches_any(path, GENERATED_TRACKING_PATTERNS)
    ]
    sensitive_paths = [path for path in tracked if _is_sensitive_path(path)]
    credential_hits: list[str] = []
    for relative_path in tracked:
        if relative_path.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".ipynb")):
            continue
        content = _read_text(root / relative_path)
        for pattern in CREDENTIAL_PATTERNS:
            if pattern.search(content):
                credential_hits.append(relative_path)
                break
    return {
        "passed": not any(
            (
                missing_public_paths,
                missing_readme_assets,
                untracked_readme_assets,
                generated_artifacts,
                sensitive_paths,
                credential_hits,
            )
        ),
        "tracked_files": len(tracked),
        "missing_public_paths": missing_public_paths,
        "missing_readme_assets": missing_readme_assets,
        "untracked_readme_assets": untracked_readme_assets,
        "generated_artifacts": generated_artifacts,
        "sensitive_paths": sensitive_paths,
        "credential_hits": credential_hits,
    }