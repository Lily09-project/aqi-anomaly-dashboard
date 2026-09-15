# Taiwan AQI Monitoring & Forecasting Dashboard

[![Quality Gate](https://github.com/Lily09-project/aqi-anomaly-dashboard/actions/workflows/quality.yml/badge.svg?branch=main)](https://github.com/Lily09-project/aqi-anomaly-dashboard/actions/workflows/quality.yml)
[![Security Audit](https://github.com/Lily09-project/aqi-anomaly-dashboard/actions/workflows/security.yml/badge.svg?branch=main)](https://github.com/Lily09-project/aqi-anomaly-dashboard/actions/workflows/security.yml)

以台灣測站資料打造的 AQI 監測、下一小時預測與異常調查工作台。介面針對桌面與行動裝置設計，提供深色與霧白藍淺色主題。

> Sample Data 僅供本機重現與測試，不代表官方即時警報、醫療建議或污染來源判定。

## 介面預覽

![AQI 資料品質與來源狀態](docs/screenshots/ui-data-health.png)
![預測可信度與模型比較](docs/screenshots/ui-forecast.png)
![異常事件調查](docs/screenshots/ui-anomaly.png)

## 核心能力

- AQI／PM2.5 趨勢、地圖選站與地區比較。
- Moving Average、Linear Regression、Random Forest 的 next-hour 預測與 chronological backtest。
- 80%／95% empirical forecast intervals、coverage、區間寬度與跨級風險。
- Z-score、Isolation Forest 與事件合併的異常證據。
- 資料健康度、更新延遲、缺失值、測站可靠性與模型漂移摘要。
- CSV、文字摘要與 reliability JSON 下載；API 失敗時提供明確 fallback／empty state。

## Quick start

需求：Python 3.10+。CI 以 Python 3.12 與 `requirements-lock-py312.txt` 驗證。

```powershell
git clone https://github.com/Lily09-project/aqi-anomaly-dashboard.git
cd aqi-anomaly-dashboard
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe run_all.py --mode sample
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Windows 快速入口與完整驗收：

```powershell
.\run_project.bat
.\run_project.bat --validate
```

瀏覽器 UI QA（含桌面、行動版、無障礙與 200% 文字重排）：

```powershell
.\.venv\Scripts\python.exe -m playwright install chromium
.\.venv\Scripts\python.exe quality\run_acceptance.py release
```

## 資料與限制

流程為「API 或 Sample Data → 欄位標準化與品質檢查 → 預測／回測與異常偵測 → Dashboard 與下載報告」。預測與異常結果必須搭配資料來源狀態、資料延遲及模型限制解讀；Sample Data 不是即時資料。

API 模式的參數只放在未提交的 `.env` 或部署平台 secrets，絕不寫入 repository。資料欄位契約與部署方式見 [docs/data-contract.md](docs/data-contract.md) 及 [docs/deployment.md](docs/deployment.md)。

## 品質與安全

release profile 會檢查 sample pipeline、pytest、public release、依賴漏洞、browser UI 與 git diff。測試定義見 [quality/test-manifest.json](quality/test-manifest.json)，安全政策見 [SECURITY.md](SECURITY.md)。測試報告與 cache 僅輸出到本機，不納入公開 repository。

## 專案範圍

`app.py` 負責 Streamlit UI；`src/` 提供資料與模型模組；`quality/`、`tests/` 與 `docs/` 提供驗收、測試及操作文件。本專案展示可重現的資料工程、時間序列建模、可解釋異常偵測與產品化流程。
