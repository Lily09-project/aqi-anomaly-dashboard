from __future__ import annotations

from streamlit.testing.v1 import AppTest


PAGE_MARKERS = {
    "總覽": "AQI 趨勢",
    "地區比較": "目前與下一小時",
    "預測": "實際 AQI 與預測 AQI",
    "異常偵測": "事件調查摘要",
    "資料品質": "資料可靠性",
    "模型指標": "模型健康度與漂移",
}


def _app() -> AppTest:
    return AppTest.from_file("app.py", default_timeout=30).run()


def test_reviewer_can_open_every_dashboard_page_without_runtime_errors() -> None:
    app = _app()

    for page, marker in PAGE_MARKERS.items():
        navigation = app.get("button_group")[0]
        navigation.set_value(page)
        app.run()

        assert not app.exception, f"{page} rendered an exception"
        assert marker in [element.value for element in app.subheader]


def test_user_can_change_theme_filters_and_custom_date_range() -> None:
    app = _app()
    theme, county, station, date_range = app.selectbox

    theme.set_value("deep_teal")
    county.set_value("臺北市")
    app.run()

    assert not app.exception
    assert app.selectbox[0].value == "deep_teal"
    assert app.selectbox[1].value == "臺北市"
    assert "松山測站" in app.selectbox[2].options

    app.selectbox[2].set_value("松山測站")
    app.selectbox[3].set_value("自訂日期")
    app.run()

    assert not app.exception
    assert app.selectbox[2].value == "松山測站"
    assert len(app.date_input) == 1
    assert len(app.button) == 2
    assert len(app.get("download_button")) >= 3


def test_reviewer_can_inspect_monitoring_history_and_decision_state() -> None:
    app = _app()
    navigation = app.get("button_group")[0]
    navigation.set_value("模型指標")
    app.run()

    assert not app.exception
    assert "監控歷史與重訓決策" in [element.value for element in app.subheader]
    metric_labels = [element.label for element in app.metric]
    assert "監控批次" in metric_labels
    assert "最新狀態" in metric_labels
    assert "建議行動" in metric_labels
