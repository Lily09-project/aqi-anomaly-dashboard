# 更新與發布檢查

## 每日公開更新

- workflow 使用免註冊 Open-Meteo API 取得 CAMS Global 空品與風場。
- 確認來源狀態為 Model Estimate，四個格點不同，最少 30 天、最新資料不超過 48 小時。
- 檢查逐時 API 序列、底層 CAMS 原生 3 小時解析度、臺灣網格座標、資料時間對齊、非負值與輸入 SHA-256。
- API、驗證、建置或 smoke test 任一失敗時，不發布新站點。
- 確認 UI 顯示模型來源、約 45 公里格點、API 逐時輸出、3 小時原生解析度及「非測站實測」。

## 自動化驗證

- Python 單元與管線測試、來源 metadata digest 驗證。
- TypeScript、lint、UI tests、Vite build、效能預算及 E2E。
- Ruff、Bandit、pip-audit、npm audit 與公開發行邊界掃描。
- sample fixture 只供 PR 預覽和測試，不可用作正式部署資料。

## 公開內容

- README、資料來源頁與來源歸屬連結保持一致。
- 不公開 API key、.env、原始個資或本機路徑。
- 不將模型網格稱為環境部測站，不把相關性描述成污染因果或實際傳播。
