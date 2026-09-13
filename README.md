# Taiwan AQI Monitoring & Forecasting Dashboard

[![Quality Gate](https://github.com/Lily09-project/aqi-anomaly-dashboard/actions/workflows/quality.yml/badge.svg?branch=main)](https://github.com/Lily09-project/aqi-anomaly-dashboard/actions/workflows/quality.yml)
[![Security Audit](https://github.com/Lily09-project/aqi-anomaly-dashboard/actions/workflows/security.yml/badge.svg?branch=main)](https://github.com/Lily09-project/aqi-anomaly-dashboard/actions/workflows/security.yml)

以台灣測站資料建立的可重現 AQI 監測、下一小時預測與異常調查工作台。介面支援桌面與行動裝置，並可在側欄切換深色或「霧白藍」淺色主題。

> Sample Data 僅供本機重現與測試，不代表官方即時警報、醫療建議或污染來源判定。

## 介面預覽

![AQI 資料品質與來源狀態](docs/screenshots/ui-data-health.png)
![預測可信度與模型比較](docs/screenshots/ui-forecast.png)
![異常事件調查](docs/screenshots/ui-anomaly.png)

## 核心能力

- 多測站 AQI／PM2.5 趨勢、地圖選站與地區比較。
- 下一小時 AQI 預測，提供 Moving Average、Linear Regression、Random Forest 比較。
- 80%／95% empirical forecast intervals，並顯示 coverage、區間寬度與跨級風險。
- Z-score、Isolation Forest 與事件合併的異常證據。
- 資料健康度、更新延遲、缺失值、測站可靠性與模型漂移摘要。
- 可下載目前篩選範圍的 CSV、文字摘要與 reliability JSON。
- API 失敗、資料不足或模型缺失時提供明確 fallback／empty state。

## 資料流程與方法

~~~text
API 或 Sample Data
        ↓
欄位標準化與資料品質檢查
        ↓
測站時間序列特徵與 next-hour target
        ├─ 預測、回測與 forecast intervals
        └─ 異常偵測與事件摘要
        ↓
Streamlit Dashboard、下載報告與 run manifest
~~~

預測使用 chronological split 與 rolling-origin backtest；異常指標以 pseudo-label 評估，結果應搭配資料來源狀態與限制解讀。

## Quick start

需求：Python 3.10+。CI 以 Python 3.12 及 `requirements-lock-py312.txt` 驗證。

```powershell
git clone https://github.com/Lily09-project/aqi-anomaly-dashboard.git
cd aqi-anomaly-dashboard
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe run_all.py --mode sample
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Windows 快速入口會建立環境、重建 Sample Data 並啟動應用程式：

```powershell
.\run_project.bat
```

只執行完整驗收、不啟動網站：

```powershell
.\run_project.bat --validate
```

需要 browser UI QA 時，先安裝 Playwright Chromium，再執行：

```powershell
.\.venv\Scripts\python.exe -m playwright install chromium
.\.venv\Scripts\python.exe quality\run_acceptance.py release
```

API 模式需要在未提交的 .env 或部署平台 secrets 設定必要參數；不要把金鑰寫入 repository。

## 品質與安全

release profile 會檢查 launcher contract、sample pipeline、pytest、public release、依賴漏洞、browser UI 與 git diff。測試定義集中在 [quality/test-manifest.json](quality/test-manifest.json)，報告輸出到本機 `reports/acceptance/`，不應提交生成物。

Repository 不追蹤 API 金鑰、`.env`、Streamlit secrets、cache、測試暫存或生成報告。安全政策與公開檔案邊界見 [SECURITY.md](SECURITY.md)；部署與資料欄位契約見 [docs/deployment.md](docs/deployment.md) 及 [docs/data-contract.md](docs/data-contract.md)。

## 專案範圍

本專案展示資料工程、時間序列建模、可解釋異常偵測、Streamlit 產品化、UI 測試與公開發布治理。`app.py` 負責 UI；`src/` 提供資料與模型模組；`quality/`、`tests/` 與 `docs/` 提供驗收、測試及操作文件。Sample Data 是模擬資料；API 的可用性、資料延遲與上游欄位變動仍需在實際部署中監控。
