# 操作檢查表

這份檢查表用於本機 Demo、API 更新與公開展示前的人工確認。它不取代正式監控、告警或事故管理系統。

## 更新前

- 確認目前 Git revision 與工作樹狀態，避免把未確認修改混入執行結果。
- 確認 `.env`、API key、token 與平台 secrets 未被 Git 追蹤。
- 確認 API URL 使用 HTTPS，且沒有 credentials、fragment 或敏感 query string。
- 確認 `data/`、`models/`、`reports/` 有足夠空間，舊 artifacts 有可回復版本。
- 先執行 `python scripts/validate_public_release.py`。

## 更新後

- 執行 `python src/smoke_test.py` 與 `pytest -q`。
- 確認 `source_metadata.json` 的 status、data_source、row_count、datetime_range 與 schema hash。
- 確認 `data_health.json` 的 missing cells、station count、observation delay 與 stale station count。
- 確認 `run_manifest.json` 的 run mode、source summary、config hash、requirements hash 與 artifacts hash。
- 開啟 Dashboard，確認 Header、KPI、地圖、預測、異常、資料品質與模型指標皆能載入。
- 確認頁面沒有 raw JSON、Python traceback、HTML/code snippet 或 secret 顯示。

## Fallback 判讀

- Source Status 顯示 API fallback 時，確認 Data Source 同時顯示 Sample Data。
- 確認 fallback reason 是安全化代碼或使用者可理解文字，不包含 response body、token 或完整 exception message。
- 不將 fallback 畫面截圖描述成即時資料。
- 面試 Demo 可繼續使用 Sample Data，但須保留模擬資料警示。

## Stale Data 判讀

- 分開檢查 source fetch time 與 latest observation time；兩者代表不同問題。
- API 取得時間過久時檢查排程、網路與 provider 狀態。
- 最新觀測落後時檢查 upstream 資料內容，不以重新整理 UI 假裝資料已更新。
- stale 或 unknown 狀態不得顯示 positive tone，也不得用於宣稱即時監測。

## Rollback

- 停止使用驗證失敗的新 artifacts，不手動修改 JSON 數字或模型輸出。
- 正式環境切回上一組完整、同版本的 data/model/report artifact set。
- 本機展示執行 `python run_all.py --mode sample` 重建可重現基線。
- 回復後重新執行 smoke test、pytest、public release gate 與 Streamlit health check。
- 記錄失敗時間、provider、error type、影響範圍與採取措施；不要記錄 secret 或 raw response。

## 公開前

- 執行 `git ls-files`，確認沒有 CSV、joblib、runtime JSON、`.env` 或 Streamlit secrets。
- 執行 dependency audit 與 Bandit high-severity scan。
- 確認 README 截圖不含個人路徑、token、原始 API 回應或誤導性即時資料文字。
- 確認 Sample Data、pseudo-label、next-hour nowcasting 與非官方警報限制仍清楚可見。
- 確認 `run_project.bat --validate` 在乾淨環境可完成。
