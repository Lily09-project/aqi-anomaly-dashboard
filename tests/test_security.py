from __future__ import annotations

import pytest

from src.fetch_aqi_data import _read_limited_response, _validate_api_url
from src.utils import load_model


class _FakeResponse:
    def __init__(self, chunks: list[bytes], content_length: str | None = None) -> None:
        self.headers = {}
        if content_length is not None:
            self.headers["content-length"] = content_length
        self._chunks = chunks

    def iter_content(self, chunk_size: int) -> list[bytes]:
        return self._chunks


def test_api_url_requires_https_except_for_loopback() -> None:
    assert _validate_api_url("https://example.com/aqi") == "https://example.com/aqi"
    assert _validate_api_url("http://127.0.0.1:8000/aqi") == "http://127.0.0.1:8000/aqi"
    with pytest.raises(ValueError):
        _validate_api_url("http://example.com/aqi")
    with pytest.raises(ValueError):
        _validate_api_url("file:///etc/passwd")


def test_api_response_size_is_limited() -> None:
    response = _FakeResponse([b"123456"], content_length="6")
    with pytest.raises(ValueError):
        _read_limited_response(response, max_bytes=5)


def test_model_loader_rejects_paths_outside_models_directory(tmp_path) -> None:
    with pytest.raises(ValueError):
        load_model(tmp_path / "untrusted.joblib")


def test_model_loader_rejects_non_joblib_artifacts() -> None:
    with pytest.raises(ValueError):
        load_model("models/untrusted.pkl")
