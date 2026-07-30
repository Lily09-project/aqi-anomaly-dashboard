from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODEL_ROOT = (PROJECT_ROOT / "models").resolve()
MAX_MODEL_FILE_BYTES = 512 * 1024 * 1024


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
    p = _model_path(path, require_exists=False)
    ensure_parent(p)
    try:
        import joblib  # type: ignore
    except ImportError:
        raise RuntimeError("joblib is required for model artifacts") from None
    joblib.dump(model, p)


def load_model(path: str | Path) -> Any:
    p = _model_path(path, require_exists=True)
    try:
        import joblib  # type: ignore
    except ImportError:
        raise RuntimeError("joblib is required for model artifacts") from None
    return joblib.load(p)


def _model_path(path: str | Path, require_exists: bool) -> Path:
    """Restrict model artifacts to the local models directory before loading."""
    model_path = Path(path).expanduser().resolve()
    try:
        model_path.relative_to(MODEL_ROOT)
    except ValueError as exc:
        raise ValueError("Model artifacts must be stored inside the project models directory") from exc
    if model_path.suffix.lower() != ".joblib":
        raise ValueError("Only .joblib model artifacts are supported")
    if require_exists:
        if not model_path.is_file():
            raise FileNotFoundError(model_path)
        if model_path.stat().st_size > MAX_MODEL_FILE_BYTES:
            raise ValueError("Model artifact exceeds the maximum supported size")
    return model_path


def latest_csv(raw_dir: Path) -> Path | None:
    if not raw_dir.exists():
        return None
    files = sorted(raw_dir.glob("*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None
