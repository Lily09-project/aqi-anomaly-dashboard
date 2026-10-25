# Taiwan Air Lab

[![Quality Gate](https://github.com/Lily09-project/aqi-anomaly-dashboard/actions/workflows/quality.yml/badge.svg?branch=main)](https://github.com/Lily09-project/aqi-anomaly-dashboard/actions/workflows/quality.yml)
[![Security](https://github.com/Lily09-project/aqi-anomaly-dashboard/actions/workflows/security.yml/badge.svg?branch=main)](https://github.com/Lily09-project/aqi-anomaly-dashboard/actions/workflows/security.yml)

臺灣空品分析展示網站，提供區域趨勢、時序關聯、異常型態與情境分析。

## 正式資料

- Open-Meteo 免費公開 API，每日更新，不需註冊或 API key。
- 空品使用 CAMS Global 模型估算：約 45 公里網格、原生每 3 小時；風場使用 Open-Meteo Forecast API。
- AQI 為美國 EPA AQI。資料不是環境部測站實測，也不是即時健康警示。
- 分析管線在模型時點間插值成逐時面板；插值不是新增觀測。
- 合成資料只供測試與 PR 預覽。正式部署必須驗證公開 API，失敗時不發布。
- Open-Meteo 免費服務限非商業用途，需依 CC BY 4.0 標示 Open-Meteo 與 CAMS。

來源：[Air Quality API](https://open-meteo.com/en/docs/air-quality-api) · [CAMS](https://atmosphere.copernicus.eu/) · [使用條款](https://open-meteo.com/en/terms)

## 功能

- 臺灣四區模型格點與空品趨勢
- 24 小時模型預測與活動時段比較
- 地點間時序關聯與異常型態
- 瀏覽器端情境分析
- 資料來源、時間範圍與 SHA-256 完整性檢查

## 本機執行

    python -m pip install -r requirements.txt -c requirements-lock-py312.txt
    python run_all.py --mode sample
    cd web && npm ci && npm run dev

公開模型資料使用 python run_all.py --mode api --require-api。正式部署不得以 sample fixture 代替來源。

## 驗證

    python -m pytest -q
    cd web && npm run typecheck && npm run lint && npm run test && npm run build

更多資訊：[GitHub Pages](docs/GITHUB_PAGES.md) · [資料契約](docs/data-contract.md) · [部署指南](docs/deployment.md)
