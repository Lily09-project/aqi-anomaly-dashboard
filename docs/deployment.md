# 部署

## 本機測試

需要 Python 3.12 與 Node.js 22。離線流程使用固定種子測試 fixture：

    python -m pip install -r requirements.txt -c requirements-lock-py312.txt
    python run_all.py --mode sample
    cd web && npm ci && npm run build && npm run preview

## 公開模型資料

Open-Meteo 免費 API 無需註冊或 API key，限非商業用途。正式資料更新由 Pages workflow 執行：

    python run_all.py --mode api --require-api

流程至少驗證 30 天資料、四個臺灣 CAMS 網格中心、每 3 小時原生時間序列、空品與風場時間對齊、數值範圍及輸入 SHA-256。任何來源或驗證失敗都會停止，不讀取快取或 sample 資料發布。模型資料約 45 公里，非測站實測；逐時分析面板的中間值為插值。

## GitHub Pages

PR workflow 只用 sample fixture 做預覽；main 與排程 workflow 必須即時取得公開來源、通過嚴格驗證後才可部署。只部署 web/dist/，並在部署後檢查公開首頁及資料 manifest。

Open-Meteo 免費 API 適用於非商業用途，並要求 CC BY 4.0 歸屬。商業用途須改用具商業授權的服務方案；不可在未確認授權前沿用免費端點。
