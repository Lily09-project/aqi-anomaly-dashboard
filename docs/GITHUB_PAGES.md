# GitHub Pages

## 發布流程

.github/workflows/pages.yml：

1. 安裝鎖定依賴並掃描公開發行邊界。
2. PR 以可重現 sample fixture 建置預覽。
3. main 或每日排程必須呼叫免註冊 Open-Meteo API，通過來源與資料驗證後才建置正式站。
4. API 失敗、資料過期、格點不完整或輸入雜湊錯誤時，workflow 失敗，不回退 sample。
5. 僅發布 web/dist/，部署後檢查首頁與 manifest。

## 資料界線

- 空品來自 CAMS Global 模型估算，約 45 公里、原生每 3 小時；風場使用 Open-Meteo Forecast API。
- 顯示美國 EPA AQI；資料是區域模型格點，不是環境部測站或健康警示。
- 分析面板在三小時模型時點間插值，這不會新增實測資料。
- 每日更新資料快照；網站執行時不直接連外，並以 manifest SHA-256 驗證每個靜態 JSON。
- Open-Meteo 免費服務限非商業用途，使用時須按 CC BY 4.0 標示 Open-Meteo 與 CAMS。

PR 預覽可使用合成 fixture，但正式 Pages workflow 必須取得並驗證 API 資料。
