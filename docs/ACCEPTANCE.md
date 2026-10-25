# Taiwan Air Lab — 驗收規格

正式網站的資料完成標準是可追溯的公開來源，不是合成值。PR 的固定種子 fixture 只驗證方法和 UI，正式部署必須讀取免註冊 API，且失敗時 fail closed。

## 資料與 UI 驗收

- Open-Meteo Air Quality API 的 CAMS Global 空品與 Open-Meteo Forecast API 風場皆成功；不得帶 API key。
- 回應來源、回應大小、redirect、JSON 欄位、時間順序、臺灣格點範圍、四個唯一格點、連續逐時 API 輸出、底層 CAMS 原生 3 小時解析度、30 天以上資料及 48 小時 freshness 全部通過。
- API 提供的 AQI 標示為美國 EPA AQI；污染物單位、Asia/Taipei 時區、CAMS 約 45 公里模型估算與非測站聲明須清楚。
- Open-Meteo 的逐時輸出含底層 3 小時 CAMS 資料的 API 插值；不得描述為逐時實測或增加模型原生解析度。
- 正式 workflow 使用 python run_all.py --mode api --require-api。API 或 metadata/digest 驗證失敗須使 job 失敗，不得讀舊 CSV 或 sample data 部署。
- UI 保留既有主題和頁面邏輯；只修正資料來源標示、錯誤文案與可重現使用性缺陷。
- 瀏覽器中的所有匯出 JSON 都須與 manifest SHA-256 相符。

## 測試範圍

- Open-Meteo adapter：無 key request、固定 HTTPS hosts、redirect/超大回應/無效座標/重複格點/過期時間/錯誤型別/舊檔保護。
- Pipeline：strict API mode 失敗時不得產生 sample 輸出；成功資料需以輸入 SHA 綁定 metadata。
- Python 與前端單元測試、TypeScript、lint、build、coverage、效能預算、E2E accessibility/security。
- Pages PR 預覽可以使用 fixture，但正式 main workflow 必須 API 驗證成功、部署 smoke test 成功。
- 另行確認 Open-Meteo 免費 API 的非商業條款與 CC BY 4.0 attribution。
