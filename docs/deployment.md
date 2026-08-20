# 部署指南

本專案預設以本機 Sample Data 模式展示；API 模式適合在受控環境中定期執行資料 pipeline。Dashboard 只讀取已產生的 artifacts，不會在頁面 render 時直接呼叫外部 API。

## 環境需求

- Python 3.10 以上，建議 Python 3.12。
- Windows、macOS 或 Linux。
- API 模式需要可連線的 HTTPS 公開資料端點；localhost 開發端點可使用 HTTP。

## 本機 Sample Data

~~~bash
python -m venv .venv
python -m pip install -r requirements.txt
python run_all.py --mode sample
python -m streamlit run app.py --server.address 127.0.0.1
~~~

Python 3.12 的 CI／Demo 環境可套用已驗證的 constraints：

~~~bash
python -m pip install -r requirements.txt -c requirements-lock-py312.txt
~~~

Windows 可直接執行 `run_project.bat`。它會固定切換到批次檔所在專案、建立 `.venv`、安裝依賴、重建 Sample Data、執行 smoke test 與 pytest，再以可用 port 啟動 Dashboard。只驗證不啟動前端時使用：

~~~bat
run_project.bat --validate
~~~

## 本機 API Data

將設定放在本機環境變數或未追蹤的 `.env`。不可把實際值寫入 `.env.example`、`config.yaml`、README、截圖或 Git commit。

~~~text
AQI_API_URL=https://example.gov.tw/path/to/aqi
AQI_API_KEY=
AQI_API_LIMIT=1000
~~~

`AQI_API_KEY` 的實際值只在本機環境或平台 Secret Store 設定。

執行：

~~~bash
python run_all.py --mode api
python -m streamlit run app.py --server.address 127.0.0.1
~~~

API URL 未設定、timeout、redirect、回應過大、格式錯誤或必要欄位不足時，pipeline 會改用 Sample Data。Dashboard、`source_metadata.json` 與 `run_manifest.json` 會標示 fallback，不會把模擬資料描述成即時 API 資料。

## 託管平台

Streamlit Community Cloud 或同類平台可用於展示 UI，但仍需安排獨立的資料更新流程，先產生 processed data、models 與 reports artifacts。Repository 不追蹤這些生成物，因此從 GitHub 啟動空白環境時，必須先執行 `python run_all.py --mode sample`，或由排程工作建立 API artifacts。

- 將 `AQI_API_URL`、`AQI_API_KEY` 放在平台 Secret Store，不提交 `.env` 或 `.streamlit/secrets.toml`。
- 啟動命令使用 `python -m streamlit run app.py`。
- 公開服務應配置 HTTPS、認證或存取控制、egress policy、日誌保留與資源限制。
- 不允許使用者上傳或指定 joblib 路徑；joblib 只能載入本專案 `models/` 內由受控 pipeline 產生的檔案。

## Health Check

資料流程完成後執行：

~~~bash
python src/smoke_test.py
python scripts/validate_public_release.py
pytest -q
~~~

Streamlit 啟動後可檢查 `http://127.0.0.1:<port>/_stcore/health`。回傳 `ok` 只代表服務存活；仍需在 Dashboard Header 與「資料品質」頁確認 Data Source、Source Status、Fetched at、Latest Observation、Observation Delay 與 fallback reason。

## 更新與回復

API 更新失敗時保留錯誤類型與安全化原因，不保存 response body、token 或完整 query string。若新 artifacts 驗證失敗，不應覆蓋已知可用版本；本機 Demo 可重新執行 `python run_all.py --mode sample` 回復到可重現基線。正式環境應對 artifacts 做版本化保存與原子切換。

完整操作步驟見 [operations-checklist.md](operations-checklist.md)，資料來源契約見 [data-contract.md](data-contract.md)。
