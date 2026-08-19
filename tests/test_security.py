from __future__ import annotations

import pytest

import src.fetch_aqi_data as fetch_module
from src.fetch_aqi_data import _read_limited_response, _validate_api_url
from src.utils import load_config, load_model, project_path, resolve_path


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
    assert _validate_api_url("http://[::1]:8000/aqi") == "http://[::1]:8000/aqi"
    with pytest.raises(ValueError):
        _validate_api_url("http://example.com/aqi")
    with pytest.raises(ValueError):
        _validate_api_url("file:///etc/passwd")
    with pytest.raises(ValueError):
        _validate_api_url("https://user:password@example.com/aqi")
    with pytest.raises(ValueError):
        _validate_api_url("https://example.com/aqi#fragment")
    with pytest.raises(ValueError):
        _validate_api_url("https://10.0.0.10/aqi")
    with pytest.raises(ValueError):
        _validate_api_url("http://192.168.1.10/aqi")
    with pytest.raises(ValueError):
        _validate_api_url("https://169.254.169.254/latest")


def test_api_fetch_disables_redirects(monkeypatch: pytest.MonkeyPatch) -> None:
    class RedirectResponse:
        status_code = 302
        headers: dict[str, str] = {}
        encoding = "utf-8"

        def __init__(self) -> None:
            self.closed = False

        def close(self) -> None:
            self.closed = True

        def raise_for_status(self) -> None:
            raise AssertionError("redirect response must be rejected before raise_for_status")

    response = RedirectResponse()
    captured: dict[str, object] = {}

    def fake_get(*args: object, **kwargs: object) -> RedirectResponse:
        captured.update(kwargs)
        return response

    import requests

    monkeypatch.setattr(
        fetch_module,
        "load_config",
        lambda: {"api": {"url": "https://example.com/aqi", "timeout_seconds": 5}, "data": {"raw_dir": "data/raw"}},
    )
    monkeypatch.setattr(requests, "get", fake_get)

    assert fetch_module.fetch_aqi_data() is None
    assert captured["allow_redirects"] is False
    assert response.closed is True


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


def test_configured_paths_cannot_escape_project_root() -> None:
    with pytest.raises(ValueError):
        project_path("..", "outside.txt")
    with pytest.raises(ValueError):
        load_config("../outside-config.yaml")
    with pytest.raises(ValueError):
        resolve_path({"data": {"output": "../outside.csv"}}, "data.output")