# 資料來源與 Provenance Contract

本文件定義 Taiwan Air Lab 如何區分 Sample Data、成功 API Data、API fallback、過期資料與未知來源。管線不會把「有本機 CSV」直接當成即時資料；所有來源判定都以 `reports/metrics/source_metadata.json` 為準。

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
- `source_url`：只保留 scheme 與 host；path、query、fragment、username、password 一律移除。
- `fallback_reason`、`error_type`、`http_status`：可判讀的失敗摘要，不保存完整 exception message 或 response body。

API key 只從 `AQI_API_KEY` 環境變數讀取，request 時以 query parameter 傳給上游，但永遠不寫入 metadata、manifest、log、網站匯出檔或 Git。正式環境應使用 secret store；本地 Demo 可以維持空 key 並執行 Sample mode。

## Freshness boundaries

來源取得時間與資料觀測時間是兩個不同概念：

1. `fetched_at_utc` 表示本機成功取得並解析來源的時間。
2. `datetime_range.max` 表示資料內最新觀測時間。
Sample Data 的期間由 `config.yaml` 的 `sample.end_date` 與 `sample.days` 固定（不讀系統時間），因此每次產生的資料位元組完全相同；網站頁首與資料可信度頁一律標示「模擬資料」。

## 官方資料欄位

本 adapter 對環境部 AQX API 常見欄位做 canonical alias mapping：`SiteName`、`County`、`AQI`、`PM2.5`、`PM10`、`O3`、`CO`、`WIND_SPEED`、`WIND_DIREC` 與 `publishtime` 等欄位會標準化為 pipeline 使用的英文欄位。schema 不完整時不進入分析流程，而是記錄 fallback。

官方資料集與 API 說明：

- 資料集：<https://data.moenv.gov.tw/dataset/detail/aqx_p_432>
- API endpoint：`https://data.moenv.gov.tw/api/v2/AQX_P_432`

網站執行期間不呼叫任何外部 API；API 取得、schema 驗證、fallback 與 provenance metadata 都由 pipeline 處理，前端只讀取 `src/export_web.py` 產生、並在瀏覽器以 SHA-256 驗證的 JSON。成功的 API metadata 會保存輸入資料檔 SHA-256；若 metadata 與目前輸入檔不一致，pipeline 會 fail closed，不把舊 API 狀態套到新檔案。

## 網站匯出

`python run_all.py` 最後一步由 `src/export_web.py` 寫出 `web/public/data/`：`overview`、`propagation`、`anomalies`、`whatif`、`model`、`provenance` 六個 JSON 與 `manifest.json`（各檔 SHA-256）。匯出是確定性的：鍵排序、浮點固定位數、時間戳取自資料本身。網站載入每個檔案時都重新計算 SHA-256，與 manifest 不符就拒絕顯示。

合成資料另外寫出 `data/sample/injected_events.csv`（注入的局部事件）與每個測站相對污染源的傳播延遲；這些「已知答案」只用來評分偵測器，分析程式本身不讀取它們。
