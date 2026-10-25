# 資料來源契約

## 正式資料

正式網站由 GitHub Actions 每日擷取公開模型資料，網站本身只讀取已驗證的靜態 JSON。

| 欄位 | 正式來源 |
| --- | --- |
| 空品與美國 AQI | Open-Meteo Air Quality API 的 CAMS Global |
| 風速、風向 | Open-Meteo Forecast API |
| 地點 | 臺北、臺中、高雄、花蓮四個固定查詢錨點；地圖使用 API 回傳的實際 CAMS 網格中心 |
| 解析度 | CAMS Global 約 45 公里、原生每 3 小時 |
| 時區 | Asia/Taipei |

Open-Meteo 可免註冊、免 API key 呼叫。免費 API 限非商業用途；資料需依 CC BY 4.0 歸屬 Open-Meteo 與 CAMS。請先閱讀 [Open-Meteo 使用條款](https://open-meteo.com/en/terms)。

API 提供美國 EPA AQI 與污染物濃度。臭氧、PM 與 CO 使用 API 回傳的 μg/m³ 單位；風速統一以 m/s 取得。使用者介面明示模型估算、格點解析度、原生時間間隔及非測站資料。健康決策應以環境部官方資訊為準。

既有逐時分析面板會在相鄰 CAMS 時點間插值兩個小時，以維持模型管線格式。插值值不是新觀測，亦不應用來宣稱原生逐時精度；來源 metadata 與資料頁會揭露此處理。

## 來源狀態

| status | data_source | 意義 |
| --- | --- | --- |
| success | Model Estimate | API 回應、四個獨立格點、時間軸、欄位、數值與輸入檔 SHA-256 均通過驗證 |
| success | Sample Data | 本機或 PR 使用的固定種子測試 fixture |
| fallback | Sample Data | 上游 API 失敗；只能用於非正式本機/PR 預覽 |
| unknown | Unknown | metadata 不存在、格式錯誤或無法驗證 |

正式建置執行 python run_all.py --mode api --require-api。API、來源 metadata 或輸入雜湊任一未通過，就以失敗結束；不採用快取 CSV，不回退合成資料，也不部署舊或不完整的輸出。

## Metadata 與安全邊界

reports/metrics/source_metadata.json 僅記錄來源、解析度、時間範圍、欄位摘要、輸入檔 SHA-256 與安全化錯誤類型；不保存 API 回應內容。Open-Meteo adapter 使用固定 HTTPS 端點、限制回應大小、拒絕 redirect、驗證回傳來源與臺灣格點範圍，並在完整驗證前不覆寫既有快照。

公開來源：

- [Open-Meteo Air Quality API](https://open-meteo.com/en/docs/air-quality-api)
- [Open-Meteo Forecast API](https://open-meteo.com/en/docs)
- [CAMS / Copernicus Atmosphere Monitoring Service](https://atmosphere.copernicus.eu/)
- [Open-Meteo 使用條款與授權](https://open-meteo.com/en/terms)

合成 fixture 僅供測試、PR preview 與分析方法已知答案驗證；正式 Pages 工作流程不得以 fixture 代替 API 資料。
