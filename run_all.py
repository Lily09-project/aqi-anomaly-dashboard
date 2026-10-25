"""Run the Taiwan Air Lab pipeline: source data → cleaning → analytics → web export.

    python run_all.py --mode sample                    # test-only synthetic fixture
    python run_all.py --mode api --require-api         # verified Open-Meteo model data
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.export_web import DEFAULT_OUT, export
from src.fetch_aqi_data import fetch_aqi_data
from src.generate_sample_data import generate_sample_aqi
from src.preprocess import preprocess
from src.source_metadata import load_source_metadata, resolve_effective_run_mode
from src.utils import latest_csv, load_config, project_path, resolve_path


def _step(name: str, fn: Callable[[], object]) -> object:
    print(f"[RUN] {name}...")
    try:
        result = fn()
    except Exception as exc:
        print(f"[ERROR] {name} failed: {exc}")
        raise
    print(f"[OK] {name}")
    return result


def run(mode: str = "sample", out_dir: Path | None = None, *, require_api: bool = False) -> dict[str, str]:
    if require_api and mode != "api":
        raise ValueError("--require-api can only be used with --mode api")
    config = load_config()
    for key in ("data.raw_dir", "data.sample_file", "data.cleaned_file"):
        target = resolve_path(config, key)
        (target if key.endswith("_dir") else target.parent).mkdir(parents=True, exist_ok=True)

    input_path: Path | None = None
    if mode == "api":
        input_path = _step("Fetch API data", fetch_aqi_data)  # type: ignore[assignment]
        if input_path is None and not require_api:
            input_path = latest_csv(resolve_path(config, "data.raw_dir"))
            if input_path is None:
                print("Falling back to sample data because the API and local raw data are unavailable.")
                _step("Generate sample data", generate_sample_aqi)
                input_path = resolve_path(config, "data.sample_file")
            else:
                print(f"Using local raw fallback with unverified source metadata: {input_path}")
        elif input_path is None:
            raise RuntimeError("Required public model data is unavailable; refusing to publish a sample-data build.")
    else:
        _step("Generate sample data", generate_sample_aqi)
        input_path = resolve_path(config, "data.sample_file")

    source_metadata = load_source_metadata(config, root=ROOT)
    effective_mode = resolve_effective_run_mode(mode, source_metadata, input_path)
    if require_api and effective_mode != "api":
        raise RuntimeError("Public source metadata or input digest is not verified; refusing to publish.")
    if effective_mode != mode:
        print(f"Effective source mode: {effective_mode} (requested: {mode})")
    _step("Preprocess data", lambda: preprocess(mode=effective_mode, input_path=input_path, source_metadata=source_metadata))
    target = out_dir or project_path(str(DEFAULT_OUT))
    hashes = _step("Run analytics and export web data", lambda: export(target))
    print(f"Pipeline finished. Web data written to {target}")
    return hashes  # type: ignore[return-value]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["sample", "api"], default="sample")
    parser.add_argument("--require-api", action="store_true", help="fail instead of using cached or sample data")
    args = parser.parse_args()
    run(args.mode, require_api=args.require_api)


if __name__ == "__main__":
    main()
