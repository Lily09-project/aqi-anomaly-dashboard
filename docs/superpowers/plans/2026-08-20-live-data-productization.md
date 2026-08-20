# Live Data Productization Implementation Plan

> For agentic workers: REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

Goal: 將目前穩定的 Sample Data-first AQI Dashboard 提升為具備真實資料接入、來源追溯、資料新鮮度提示、官方測站 metadata 與可部署說明的作品集級產品，同時保留離線 Sample fallback 作為面試 Demo 的穩定基線。

Architecture: 沿用現有 run_all.py、src/fetch_aqi_data.py、src/dashboard/ 與 run_manifest，不重寫 pipeline。新增獨立的 source provenance contract，讓 API、Sample、fallback 的狀態由同一份 metadata 驅動 pipeline、Dashboard 與公開報告；前端只消費已整理的資料，不直接處理 API request。測站座標移出業務邏輯，改由可追溯的公開 station registry 提供。

Tech Stack: Python 3.10+、pandas、requests、PyYAML、Streamlit、Plotly、pytest、GitHub Actions、既有 atomic artifact writers。

## Global Constraints

- 保留 python run_all.py --mode sample 與 run_project.bat，不能讓真實 API 失敗導致 Demo 無法啟動。
- Sample Data、API Data、fallback 狀態必須可區分，不能把模擬資料顯示成即時資料。
- API token、credential、完整 query string、原始 API response 不得寫入 Git、Dashboard、manifest 或公開報告。
- 不把 CSV、joblib、JSON metrics、PNG 或 runtime cache 加入 Git。
- 現有資料洩漏防護、時間切分、atomic write、public release gate 與 113 個測試不得退化。
- 新增程式碼的變數、函式、類別與註解使用英文；使用者介面與文件使用繁體中文。
- 不新增資料庫、登入系統、深度學習模型或大型前端框架；先完成資料可信度與產品化邊界。
- 每個 Task 完成後先跑該 Task 的 targeted tests，再建立小型 commit；所有 Task 完成後才跑完整 release verification。

## Why This Is The Next Priority

目前專案已具備完整的本地 pipeline、模型比較、預測區間、異常事件、地圖篩選、安全掃描與公開 release gate。下一個審查者最容易追問的問題是：

1. 這是不是只有模擬資料？
2. API 失敗、資料過期或測站不同步時，系統會不會誤導使用者？
3. 地圖座標與資料來源能不能追溯？
4. 這個 Dashboard 能不能被其他人依照文件部署？

因此下一階段優先做真實資料可信度層，暫不新增更多模型。

---

### Task 1: 建立 API / Sample Data provenance contract

Files:
- Create: src/source_metadata.py
- Create: tests/test_source_metadata.py
- Create: docs/data-contract.md
- Modify: config.yaml
- Modify: .env.example
- Modify: src/fetch_aqi_data.py
- Modify: README.md

Interfaces:
- SourceMetadata：不可變的來源狀態資料結構，至少包含 provider、mode、status、requested_at_utc、fetched_at_utc、row_count、datetime_range、schema_columns、schema_sha256、fallback_reason。
- build_source_metadata(...) -> dict[str, object]：建立可 JSON 序列化且不含 secret 的 metadata。
- redact_source_url(url: str) -> str：只保留 scheme、host、path，不保留 username、password、query、fragment。
- write_source_metadata(path: str | Path, payload: Mapping[str, object]) -> Path：使用既有 atomic JSON writer 寫入。
- fetch_aqi_data(output_path: str | Path | None = None, metadata_path: str | Path | None = None) -> Path | None：保留既有回傳契約，新增 metadata 輸出，不回傳 raw response。

Steps:

- [ ] Step 1: 定義失敗案例與資料契約測試

  在 tests/test_source_metadata.py 先加入：

  ~~~python
  def test_redact_source_url_removes_credentials_query_and_fragment():
      value = redact_source_url(
          "https://user:secret@example.com/aqi?token=private#debug"
      )
      assert value == "https://example.com/aqi"

  def test_source_metadata_marks_sample_data():
      payload = build_source_metadata(
          provider="sample_generator",
          mode="sample",
          status="success",
          row_count=10,
          datetime_range={"min": "2026-08-01T00:00:00", "max": "2026-08-01T09:00:00"},
      )
      assert payload["data_source"] == "Sample Data"
      assert payload["is_simulated_data"] is True
      assert payload["fallback_reason"] is None
  ~~~

- [ ] Step 2: 執行 targeted test 確認尚未通過

  Run: pytest tests/test_source_metadata.py -q

  Expected: FAIL，因為 src/source_metadata.py 尚未建立。

- [ ] Step 3: 實作 metadata builder 與 URL redaction

  在 src/source_metadata.py 建立單一責任模組。build_source_metadata 必須將 mode == sample 標記為 Sample Data，將 mode == api 且 status == success 標記為 API Data；fallback 必須保留 fallback_reason 並把實際資料來源標記為 Sample Data。schema hash 只對 canonical column name 排序後計算，不保存資料內容。

- [ ] Step 4: 將 fetch 結果接入 metadata

  在 config.yaml 新增：

  ~~~yaml
  reports:
    source_metadata_file: reports/metrics/source_metadata.json
  ~~~

  在 .env.example 保留 AQI_API_URL、AQI_API_KEY 的名稱說明，但不填入值。fetch_aqi_data.py 每次成功、未設定 URL、HTTP error、欄位不足或 response size 超限都必須寫出 metadata；失敗時只保存錯誤類型與可理解的 fallback reason，不保存完整 exception message 或 response body。

- [ ] Step 5: 驗證並提交

  Run: pytest tests/test_source_metadata.py tests/test_security.py -q

  Expected: 所有 targeted tests PASS，且 git diff --check PASS。

  Commit: git add src/source_metadata.py tests/test_source_metadata.py config.yaml .env.example src/fetch_aqi_data.py docs/data-contract.md README.md && git commit -m "feat: add source provenance contract"

Acceptance criteria: API 成功、API 失敗、Sample mode 三種狀態都能產生同一 schema 的 metadata；metadata 不含 token、query string、raw response；現有 SSRF、redirect、size-limit 測試仍通過。

---

### Task 2: 讓 pipeline 與 run manifest 以實際來源為準

Files:
- Modify: run_all.py
- Modify: src/preprocess.py
- Modify: src/data_health.py
- Modify: src/run_manifest.py
- Modify: src/utils.py（只在需要路徑驗證時修改）
- Modify: tests/test_run_all.py
- Modify: tests/test_data_health.py
- Modify: tests/test_run_manifest.py
- Create: tests/test_api_pipeline_fallback.py

Interfaces:
- load_source_metadata(config: Mapping[str, Any]) -> dict[str, Any]：讀取不存在或格式錯誤時回傳明確的 status=unknown，不能讓 Dashboard crash。
- resolve_effective_run_mode(requested_mode: str, source_metadata: Mapping[str, Any], input_path: Path | None) -> str：只在真正 API 成功且資料由 API 取得時回傳 api，否則回傳 sample。
- run_manifest["run"]["data_source"]、run_manifest["run"]["is_simulated_data"]、run_manifest["source"] 必須由 metadata 驅動。

Steps:

- [ ] Step 1: 先寫 API fallback 與 mode truth tests

  新增測試，驗證 API 失敗且沒有可用 raw data 時會產生 Sample Data，manifest 的 data_source 為 Sample Data，is_simulated_data 為 True。測試不能依賴外部網路，使用 monkeypatch 或 local fixture。

- [ ] Step 2: 實作來源讀取與有效 mode 判定

  run_all.py 必須在 pipeline 開始時清楚區分 requested mode 與 effective mode。API 失敗且沒有可用 raw data 時產生 Sample Data；API 失敗但沿用本地 raw data 時，只有該 raw data 的 metadata 明確標為 API 成功，才可顯示 API Data，否則顯示 Sample Data。

- [ ] Step 3: 將 source metadata 納入 data health 與 manifest

  data_health.json 新增 source_status、provider、fetched_at_utc、source_is_stale、fallback_reason。run_manifest.json 新增 source 摘要與 source_metadata_sha256，但不能寫入 API URL query、token 或 raw response。

- [ ] Step 4: 增加 stale policy

  在 config.yaml 新增：

  ~~~yaml
  data:
    stale_after_hours: 3
  ~~~

  使用來源 fetch time 與最新觀測時間分別判斷「來源是否過期」與「資料觀測是否落後」，不能用單一 timestamp 混淆兩者。若 metadata 不存在，狀態必須是 unknown，不能默認為 fresh。

- [ ] Step 5: 驗證與提交

  Run: pytest tests/test_api_pipeline_fallback.py tests/test_run_all.py tests/test_data_health.py tests/test_run_manifest.py -q

  Expected: PASS；run_all.py --mode sample 產生完整 metadata、manifest 與既有 artifacts。

  Commit: git add run_all.py src/preprocess.py src/data_health.py src/run_manifest.py tests/test_api_pipeline_fallback.py tests/test_run_all.py tests/test_data_health.py tests/test_run_manifest.py config.yaml && git commit -m "feat: make pipeline source state explicit"

Acceptance criteria: 任何 API 失敗、舊 raw data、缺失 metadata 的情況都不會被 UI 或 manifest 誤標成新鮮 API Data；Sample pipeline 仍可完整重建。

---

### Task 3: 在 Dashboard 暴露資料新鮮度與 fallback 狀態

Files:
- Modify: src/dashboard/context.py
- Modify: src/dashboard/data_service.py
- Modify: src/dashboard/pages/quality.py
- Modify: src/dashboard/pages/overview.py
- Modify: src/dashboard/components.py
- Modify: app.py
- Modify: tests/test_dashboard_context.py
- Modify: tests/test_dashboard_pages.py
- Modify: tests/test_app_import.py
- Create: tests/test_dashboard_provenance.py

Interfaces:
- DashboardMetrics.source_metadata: dict[str, Any]：沿用目前 DashboardMetrics dataclass，缺檔時為空 dict。
- format_source_status(source_metadata: Mapping[str, Any]) -> dict[str, str]：回傳 label、tone、detail、is_warning，供 header 與 Data Quality 共用。
- source_status_panel(source_metadata: Mapping[str, Any]) -> None：只負責 UI rendering，不在元件內讀檔或發 API request。

Steps:

- [ ] Step 1: 先寫 Dashboard provenance rendering tests

  測試 Sample Data、fallback、stale、unknown 與 API success 五種狀態的文字與 tone。Sample Data 必須是 warning tone，不能只顯示中性文字。

- [ ] Step 2: 將 metadata 載入 Dashboard context

  load_dashboard_artifacts 讀取 reports.source_metadata_file，缺檔、空檔或壞 JSON 必須回傳空 dict；不能把 raw JSON 直接展示在頁面。

- [ ] Step 3: 更新 header 與 Data Quality

  Header 顯示資料來源、provider、最新取得時間與資料狀態。Data Quality 顯示 Source status、Provider、Fetched at UTC、Latest observation、Observation delay、Stale station count；fallback 時才顯示 fallback reason。

  Sample Data 使用明確 warning tone；API stale 使用 warning tone；成功 API 才能使用 positive tone。所有主題都必須維持足夠文字對比。

- [ ] Step 4: 驗證空、壞、舊資料狀態

  使用 fake Streamlit 測試正常、missing metadata、malformed JSON、stale source、empty dataframe 五種狀態，確認無 Python exception、無 raw JSON、無 code snippet 出現在 UI HTML。

- [ ] Step 5: 驗證與提交

  Run: pytest tests/test_dashboard_provenance.py tests/test_dashboard_context.py tests/test_dashboard_pages.py tests/test_app_import.py -q

  Commit: git add src/dashboard/context.py src/dashboard/data_service.py src/dashboard/pages/quality.py src/dashboard/pages/overview.py src/dashboard/components.py app.py tests/test_dashboard_provenance.py tests/test_dashboard_context.py tests/test_dashboard_pages.py tests/test_app_import.py && git commit -m "feat: surface data freshness in dashboard"

Acceptance criteria: 使用者不需要打開 JSON 或看 console，就能在首屏與 Data Quality 頁面判斷資料是真實、模擬、fallback、過期或未知；所有狀態在淺色與深色主題下都有足夠對比。

---

### Task 4: 建立可追溯的 station registry 並修正地圖資料責任

Files:
- Create: config/stations.yaml
- Create: src/station_registry.py
- Create: tests/test_station_registry.py
- Modify: src/app_helpers.py
- Modify: src/dashboard/maps.py
- Modify: src/risk_brief.py
- Modify: tests/test_risk_brief.py
- Modify: README.md

Interfaces:
- load_station_registry(path: str | Path | None = None) -> dict[str, dict[str, Any]]：載入公開 station metadata，壞檔或缺檔回傳空 registry。
- lookup_station(site_name: str, county: str | None = None) -> dict[str, Any] | None：以 canonical site name 優先，county 作為輔助條件。
- get_station_coordinates(...)：保留既有呼叫方式，但回傳來源時新增 coordinate_source，不能讓 county centroid 被誤認為官方測站座標。

Steps:

- [ ] Step 1: 先寫 registry 與 coordinate-source tests

  測試 station exact match、unknown station、缺座標、county fallback，以及 coordinate_source 的值是否清楚。

- [ ] Step 2: 建立公開 station registry

  config/stations.yaml 每筆至少包含 site_name、county、latitude、longitude、coordinate_source、source_note。所有值必須來自可引用的官方公開 station metadata；若暫時只能使用 county centroid，明確標成 approximate_county_centroid，不得冒充 station coordinate。

- [ ] Step 3: 將 map 與 risk brief 改用 registry

  src/dashboard/maps.py 的 hover template 顯示 coordinate source；缺少精確座標時保留地圖功能，但 UI 顯示「近似位置」提示。src/app_helpers.py 不再維護第二套座標常數，避免資料散落。

- [ ] Step 4: 驗證與提交

  Run: pytest tests/test_station_registry.py tests/test_risk_brief.py tests/test_dashboard_pages.py -q

  Commit: git add config/stations.yaml src/station_registry.py tests/test_station_registry.py src/app_helpers.py src/dashboard/maps.py src/risk_brief.py tests/test_risk_brief.py README.md && git commit -m "feat: add traceable station registry"

Acceptance criteria: 地圖座標只有一個來源；使用者能分辨官方精確座標、近似位置與無座標；Sample Data 與 API Data 都不會因座標缺失而 crash。

---

### Task 5: 補上可部署與 reviewer-ready 的執行文件

Files:
- Create: docs/deployment.md
- Create: docs/operations-checklist.md
- Modify: README.md
- Modify: .github/workflows/quality.yml
- Modify: .github/workflows/security.yml
- Modify: run_project.bat（只在需要顯示 effective source 或 health result 時修改）
- Modify: tests/test_release_guard.py

Interfaces:
- docs/deployment.md 必須提供 local Sample、local API、Streamlit Community Cloud 或同等託管環境的設定步驟，並明確說明 secrets 應放在平台 secret store。
- docs/operations-checklist.md 必須提供資料更新前、更新後、失敗 fallback、stale data 與 rollback 的檢查表。

Steps:

- [ ] Step 1: 撰寫部署與操作文件

  文件必須包含 Python version、install command、Sample demo command、API environment variables、Streamlit secrets 注意事項、health check、stale/fallback 判讀、公開部署不可使用 .env 提交 secrets 的說明。

- [ ] Step 2: 加入 deterministic CI contract tests

  GitHub Actions 只跑 mock/local contract，不依賴外部官方 API；至少執行 validate_public_release.py、sample pipeline、pytest -q、high-severity Bandit 與 dependency audit。不要在 CI 將 generated artifacts commit 回 repository。

- [ ] Step 3: 補充 release guard 測試

  驗證 config/stations.yaml、docs/data-contract.md、docs/deployment.md 是必要公開檔案；驗證 source metadata、.env、模型與 generated JSON 不會被誤追蹤或寫入公開文件。

- [ ] Step 4: 驗證與提交

  Run: python scripts/validate_public_release.py、pytest tests/test_release_guard.py -q、git diff --check。

  Commit: git add docs/deployment.md docs/operations-checklist.md README.md .github/workflows/quality.yml .github/workflows/security.yml tests/test_release_guard.py run_project.bat && git commit -m "docs: prepare live data deployment"

Acceptance criteria: 新使用者可以只依照 README 與 deployment 文件啟動 Sample 或 API mode；CI 不需要 secrets 也能驗證完整資料契約；公開 gate 不允許 generated artifacts 或 secrets 混入。

---

### Task 6: 最終驗收、截圖與公開發布

Files:
- Modify: README.md
- Create or replace only sanitized assets under docs/screenshots/
- No generated data/model/report files may be committed.

Steps:

- [ ] Step 1: 執行完整測試矩陣

  ~~~powershell
  python -m compileall -q app.py src tests run_all.py scripts
  python run_all.py --mode sample
  python src/smoke_test.py
  pytest -q
  python scripts/validate_public_release.py
  pip check
  pip-audit --local
  bandit --severity-level high --confidence-level high -r app.py src scripts
  run_project.bat --validate
  ~~~

- [ ] Step 2: 執行 API mode contract test

  使用 local mocked HTTP fixture 驗證 success、redirect、oversized response、invalid schema、timeout 與 fallback，不直接把不穩定的外部 API 納入必要 CI gate。

- [ ] Step 3: 執行 Streamlit health check

  啟動 streamlit run app.py --server.address 127.0.0.1，確認 /healthz 與首頁回傳 200；檢查首屏 source status、KPI、Data Quality、地圖與 empty state。測試後停止 process，將 log 與生成物移至 C:\Users\user\Documents\Codex\多餘。

- [ ] Step 4: 產生 reviewer-ready 截圖

  只保留不含 token、raw response、模型檔與個人路徑的截圖：首屏 source status、地圖選站、Data Quality freshness、Prediction confidence、Anomaly evidence。README 每張圖附上畫面目的與啟動指令。

- [ ] Step 5: 執行公開內容審查並提交

  確認 git status --short 只有預期文件與程式碼；確認 git ls-files 沒有 CSV、joblib、runtime JSON、.env 或 secrets。更新 README 的實際測試數字與 commit SHA。

  Commit: git add README.md docs/screenshots && git commit -m "docs: finalize live data portfolio release"

- [ ] Step 6: 推送並驗證遠端

  ~~~powershell
  git push origin feat/forecast-confidence
  git ls-remote origin refs/heads/feat/forecast-confidence
  ~~~

  Expected: remote SHA 等於 local git rev-parse HEAD，工作樹乾淨，GitHub Actions quality/security workflows 被觸發。

Final acceptance criteria:

- Sample mode 仍能在無網路時完成完整 Demo。
- API mode 能明確顯示成功、fallback、stale、unknown，不誤導資料來源。
- 每次 pipeline run 都有 source provenance、data health 與 run manifest。
- 地圖座標可追溯且不再維護重複座標常數。
- README、deployment guide、測試與截圖足以讓 reviewer 在 5 分鐘內理解價值與限制。
- Public release gate、pytest、pipeline、smoke test、Streamlit health、pip-audit、Bandit 全部通過。

## Explicitly Defer

以下項目先不做，避免降低完成度：

- 不新增 LSTM、Transformer 或其他模型，只為了增加模型數量。
- 不把完整 raw API data、joblib 或 metrics commit 到 GitHub。
- 不新增登入、權限、資料庫或即時 websocket，除非先有實際使用者與部署需求。
- 不把 external API call 放進 Dashboard renderer；資料取得仍由 pipeline 或受控 service 負責。
- 不把 pseudo-label anomaly F1 描述成真實污染事件準確率。

## Recommended Execution Order

1. Task 1: source provenance contract。
2. Task 2: pipeline source truth and freshness policy。
3. Task 3: Dashboard freshness UI。
4. Task 4: station registry and map attribution。
5. Task 5: deployment and reviewer documentation。
6. Task 6: full verification, screenshots and GitHub release。

這個順序能先建立資料可信度，再讓 UI 顯示可信度，最後才做部署與展示；每一階段都能獨立測試與回退。