from __future__ import annotations

import json
import pickle
from pathlib import Path
from typing import Any

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def project_path(*parts: str | Path) -> Path:
    return PROJECT_ROOT.joinpath(*map(Path, parts))


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    config_path = project_path("config.yaml") if path is None else Path(path)
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


def write_json(path: str | Path, payload: dict[str, Any]) -> None:
    p = ensure_parent(path)
    with p.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


def save_model(path: str | Path, model: Any) -> None:
    p = ensure_parent(path)
    try:
        import joblib  # type: ignore

        joblib.dump(model, p)
    except ImportError:
        with p.open("wb") as f:
            pickle.dump(model, f)


def load_model(path: str | Path) -> Any:
    p = Path(path)
    try:
        import joblib  # type: ignore

        return joblib.load(p)
    except ImportError:
        with p.open("rb") as f:
            return pickle.load(f)


def latest_csv(raw_dir: Path) -> Path | None:
    if not raw_dir.exists():
        return None
    files = sorted(raw_dir.glob("*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None
