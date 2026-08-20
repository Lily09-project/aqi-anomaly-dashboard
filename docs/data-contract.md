# 資料來源與 Provenance Contract

本文件定義 Taiwan AQI Dashboard 如何區分 Sample Data、成功 API Data、API fallback、過期資料與未知來源。Dashboard 不會把「有本機 CSV」直接當成即時資料；所有來源判定都以 `reports/metrics/source_metadata.json` 為準。

## 來源狀態

| `status` | `data_source` | 使用情境 | UI 解讀 |
| --- | --- | --- | --- |
| `success` | `Sample Data` | 本地模擬資料產生成功 | 明確標示模擬資料，不代表官方觀測 |
| `success` | `API Data` | API 回應通過 schema 驗證並寫入 raw CSV | 可顯示 API 來源與取得時間 |
| `fallback` | `Sample Data` | API 未設定、失敗、超時、redirect、超大回應或 schema 不完整 | 以警示色顯示 fallback 原因，不冒充即時資料 |
| `unknown` | `Unknown` | metadata 不存在、格式錯誤或舊版輸出未含來源契約 | 視為不可確認，不默認 fresh |

`data_source` 與 `is_simulated_data` 是使用者可見的真實來源標籤。API request 失敗時，即使沿用 `data/raw` 舊檔，也不會自動標示為新鮮 API Data。

## Metadata schema

`source_metadata.json` 只保存可公開的 metadata：

- `provider`：來源 adapter，例如 `moenv_aqx_p_432`。
- `mode`、`status`、`data_source`、`is_simulated_data`：來源與 fallback truth。
- `requested_at_utc`、`fetched_at_utc`：請求與成功解析時間。
- `row_count`、`datetime_range`：資料量與觀測時間範圍。
- `schema_columns`、`schema_sha256`：欄位契約，不保存資料列內容。
- `source_url`：只保留 scheme、host、path；query、fragment、username、password 一律移除。
- `fallback_reason`、`error_type`、`http_status`：可判讀的失敗摘要，不保存完整 exception message 或 response body。

API key 只從 `AQI_API_KEY` 環境變數讀取，request 時以 query parameter 傳給上游，但永遠不寫入 metadata、manifest、log、Dashboard 或 Git。正式環境應使用 secret store；本地 Demo 可以維持空 key 並執行 Sample mode。

## Freshness boundaries

來源取得時間與資料觀測時間是兩個不同概念：

1. `fetched_at_utc` 表示本機成功取得並解析來源的時間。
2. `datetime_range.max` 表示資料內最新觀測時間。
3. `data.stale_after_hours` 只用於判斷來源或觀測是否落後，不會修改原始時間。

Sample Data 的日期由 sample generator 以目前日期往前產生，仍然必須在 UI 顯示 Sample Data（模擬資料）。

## 官方資料欄位

本 adapter 對環境部 AQX API 常見欄位做 canonical alias mapping：`SiteName`、`County`、`AQI`、`PM2.5`、`PM10`、`O3`、`CO`、`WIND_SPEED`、`WIND_DIREC` 與 `publishtime` 等欄位會標準化為 pipeline 使用的英文欄位。schema 不完整時不進入模型流程，而是記錄 fallback。

官方資料集與 API 說明：

- 資料集：<https://data.moenv.gov.tw/dataset/detail/aqx_p_432>
- API endpoint：`https://data.moenv.gov.tw/api/v2/AQX_P_432`

本專案不在 Dashboard render 階段直接呼叫上游 API；API 取得、schema 驗證、fallback 與 provenance metadata 都由 pipeline 處理，前端只讀取已驗證的本地 artifacts。

## 監控報表

`data/processed/aqi_monitoring_predictions.csv` 保存兩種已評分資料：`rolling_origin_oof` 是每個 walk-forward fold 的 out-of-fold 預測，`final_test` 是最後測試窗口。每筆資料都保存 `training_cutoff`，且必須早於預測時間；這個檔案不取代只代表 final test 的 `aqi_predictions.csv`。

`reports/metrics/monitoring.json` 比較兩個不重疊的時間窗口：預設為最近 7 天（current window）與其之前 14 天（reference window）。報表會整理 AQI／PM2.5 分布偏移、預測 MAE 變化與 80%／95% 預測區間 coverage。`warning` 或 `critical` 只代表需要人工檢查的診斷訊號，不會自動替換模型或發送官方警報；資料不足時會明確標記 `insufficient_data`。單次短資料流程若沒有足夠 OOF rows，會保留 final-test 結果並明確降級，不會製造假的 reference window。

`reports/metrics/monitoring_history.json` 保存跨次 pipeline 的扁平決策快照，不保存 raw rows。`snapshot_id` 由資料截止時間、資料來源、模型與 monitoring contract 產生；相同批次重跑會更新原紀錄。歷史依 `recorded_at_utc` 排序，預設只保留最近 90 筆，並以 atomic write 更新。建議行動只有 `observe`、`investigate`、`review_retraining` 與 `collect_more_data` 四種；它們是人工審查輸入，不是自動部署命令。Dashboard 只呈現本地化摘要、MAE 趨勢與表格，不直接顯示 raw JSON。
