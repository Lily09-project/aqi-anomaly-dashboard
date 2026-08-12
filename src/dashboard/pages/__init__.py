from src.dashboard.context import PageContext
from src.dashboard.pages.anomaly import render as render_anomaly
from src.dashboard.pages.comparison import render as render_comparison
from src.dashboard.pages.metrics import render as render_metrics
from src.dashboard.pages.overview import render as render_overview
from src.dashboard.pages.prediction import render as render_prediction
from src.dashboard.pages.quality import render as render_quality

PAGE_RENDERERS: dict[str, object] = {
    "總覽": render_overview,
    "地區比較": render_comparison,
    "預測": render_prediction,
    "異常偵測": render_anomaly,
    "資料品質": render_quality,
    "模型指標": render_metrics,
}

__all__ = ["PAGE_RENDERERS", "PageContext"]