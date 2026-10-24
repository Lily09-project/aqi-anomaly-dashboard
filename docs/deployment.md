# 部署指南

## 環境需求

- Python 3.12（3.11 以上可執行；鎖定檔針對 3.12）。
- Node.js 22。
- Windows、macOS 或 Linux。

## 本機（合成資料）

```bash
python -m venv .venv
python -m pip install -r requirements.txt -c requirements-lock-py312.txt
python run_all.py --mode sample
cd web && npm ci && npm run build && npm run preview   # http://127.0.0.1:4173
```

Windows 可直接執行 `run_project.bat`：建立 `.venv`、安裝依賴、產生資料與匯出、跑 pytest、建置網站並在本機 127.0.0.1 啟動。`run_project.bat --validate` 會額外執行 Bandit、Ruff、pip-audit、TypeScript 型別檢查、ESLint、Vitest 覆蓋率與效能預算，但不啟動網站；未知參數會以結束碼 2 拒絕執行。既有但損壞或版本不符的 `.venv` 不會被刪除，而是請使用者先自行搬移。

## 本機（環境部 API）

設定放在本機環境變數或未追蹤的 `.env`，不可寫入 `.env.example`、`config.yaml`、README 或 Git：

```text
AQI_API_URL=https://data.moenv.gov.tw/api/v2/AQX_P_432
AQI_API_KEY=
AQI_API_LIMIT=1000
```

```bash
python run_all.py --mode api
```

API 未設定、逾時、redirect、回應過大、格式錯誤或欄位不足時，管線改用合成資料；`provenance.json` 與網站頁首會標示，不會把模擬資料描述成即時資料。注意：API 只提供最新一小時的觀測，必須另外排程保存快照、累積至少 14 天逐時歷史才能訓練與測試模型；歷史不足時匯出會以 `InsufficientHistoryError` 明確停止，不會產生看似正常的結果。

## 靜態託管

`web/dist/` 是完整的靜態網站，可放在 GitHub Pages、任何物件儲存或 CDN。正式部署前應確認：

- 只發布 `web/dist/`，不要發布儲存庫根目錄。
- 保留 `index.html` 內的 Content-Security-Policy。
- 若改用自己的網域，更新 `pages.yml` 冒煙測試的網址。

GitHub Pages 的完整流程見 [GITHUB_PAGES.md](GITHUB_PAGES.md)，日常檢查見 [operations-checklist.md](operations-checklist.md)。

## 更新與回復

匯出是確定性的：相同輸入一定得到位元組相同的輸出，`manifest.json` 記錄每個檔案的 SHA-256。若新資料驗證失敗，不要手動修改 JSON；重新執行 `python run_all.py --mode sample` 即可回到可重現基線，或重新部署上一個成功的 `web/dist/`。
