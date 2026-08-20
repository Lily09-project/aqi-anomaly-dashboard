from __future__ import annotations

from src.dashboard.provenance import format_source_status, source_status_panel


def test_sample_data_is_explicit_warning_status() -> None:
    status = format_source_status(
        {
            "status": "success",
            "data_source": "Sample Data",
            "provider": "sample_generator",
        }
    )

    assert status["label"] == "Sample Data · 模擬資料"
    assert status["tone"] == "warning"
    assert status["is_warning"] is True
    assert "不代表官方即時觀測" in status["detail"]


def test_api_fallback_and_stale_states_are_not_positive() -> None:
    fallback = format_source_status(
        {
            "status": "fallback",
            "data_source": "Sample Data",
            "fallback_reason": "api_request_failed",
        }
    )
    stale = format_source_status(
        {
            "status": "success",
            "data_source": "API Data",
            "provider": "moenv_aqx_p_432",
            "source_is_stale": True,
            "fetched_at_utc": "2026-08-20T00:00:00Z",
        }
    )

    assert fallback["label"] == "Sample Data · API fallback"
    assert fallback["is_warning"] is True
    assert "API 請求失敗" in fallback["detail"]
    assert stale["tone"] == "warning"
    assert stale["is_warning"] is True


def test_api_success_is_positive_and_panel_does_not_render_raw_json() -> None:
    class FakeStreamlit:
        rendered = ""

        def markdown(self, value: str, unsafe_allow_html: bool = False) -> None:
            self.rendered = value

    fake = FakeStreamlit()
    status = source_status_panel(
        {
            "status": "success",
            "data_source": "API Data",
            "provider": "moenv_aqx_p_432",
            "fetched_at_utc": "2026-08-20T08:00:00Z",
            "datetime_range": {"max": "2026-08-20T07:00:00Z"},
        },
        st_api=fake,
    )

    assert status["label"] == "API Data · 已更新"
    assert status["tone"] == "positive"
    assert "metadata_version" not in fake.rendered
    assert "moenv_aqx_p_432" in fake.rendered
    assert "08:00 UTC" in fake.rendered


def test_unknown_metadata_is_warning_and_human_readable() -> None:
    status = format_source_status({})

    assert status["label"] == "來源未知 · 需重新產生資料"
    assert status["tone"] == "warning"
    assert "raw" not in status["detail"].lower()
