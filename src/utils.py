from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Callable

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MAX_MODEL_FILE_BYTES = 512 * 1024 * 1024


def project_path(*parts: str | Path) -> Path:
    candidate = PROJECT_ROOT.joinpath(*map(Path, parts)).resolve()
    try:
        candidate.relative_to(PROJECT_ROOT)
    except ValueError as exc:
        raise ValueError("Configured paths must stay inside the project root") from exc
    return candidate


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    config_path = project_path("config.yaml") if path is None else project_path(path)
    with config_path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def resolve_path(config: dict[str, Any], dotted_key: str) -> Path:
    value: Any = config
    for key in dotted_key.split("."):
        value = value[key]
    return project_path(value)


def ensure_parent(path: str | Path) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _atomic_write(path: str | Path, writer: Callable[[Path], None]) -> None:
    """Write an artifact to a temporary sibling before replacing the destination."""
    destination = ensure_parent(path).resolve()
    file_descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    os.close(file_descriptor)
    temporary_path = Path(temporary_name)
    try:
        writer(temporary_path)
        os.replace(temporary_path, destination)
    finally:
        temporary_path.unlink(missing_ok=True)


def write_csv(frame: Any, path: str | Path, **kwargs: Any) -> None:
    """Atomically persist a dataframe so readers never observe a partial CSV."""
    _atomic_write(path, lambda temporary_path: frame.to_csv(temporary_path, **kwargs))


def write_json(path: str | Path, payload: dict[str, Any]) -> None:
    content = json.dumps(payload, indent=2, ensure_ascii=False)
    _atomic_write(path, lambda temporary_path: temporary_path.write_text(content, encoding="utf-8"))


def latest_csv(raw_dir: Path) -> Path | None:
    if not raw_dir.exists():
        return None
    files = sorted(raw_dir.glob("*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None