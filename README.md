# 台灣 AQI 預測與空氣污染異常偵測 Dashboard

本專案是一個可在本地端完整重現的資料科學 side project，主題為「台灣 AQI 預測與空氣污染異常偵測 Dashboard」。它不是只展示模型數字，而是把 AQI、PM2.5、同測站歷史基準、下一小時預測與異常訊號整理成可追溯的人工檢視順序。專案涵蓋 Open Data / API fallback、時間序列資料清理、特徵工程、下一小時 AQI 預測、污染異常偵測、模型評估、繁體中文 Streamlit Dashboard、pytest 自動測試與 Windows 一鍵執行。

## 專案目標

- 建立可放上 GitHub 與履歷的完整本地端 AI/ML side project。
- 使用時間序列特徵預測同測站下一小時 AQI。
- 使用 pseudo-label 與 Isolation Forest 偵測可能污染異常事件。
- 提供面試可展示的繁體中文 Dashboard。
- 在沒有 API key、沒有網路或 API 失敗時，仍可使用 sample data 跑完整 Demo。
- 將模型結果轉換為「先看哪一個測站、依據是什麼」的透明判讀，而不是只給一個不明來源的風險分數。

## 專案差異化：測站脈絡化判讀

不同地區的正常污染水準不同，單用全台平均或固定門檻容易掩蓋「對某個測站而言不尋常」的變化。因此 Dashboard 在總覽中加入 **測站脈絡風險判讀**：

- 每個測站只以自己近 14 天、相同小時且早於目前時點的 AQI 中位數作為基準。
- 同時顯示目前 AQI、相對本站基準、近 6 小時變化、同時點的下一小時模型預測，以及規則 / Z-score / Isolation Forest 的異常證據。
- 以透明的優先排序協助人工決定先檢視哪一站；排序不是官方 AQI 警報、因果解釋、醫療建議或健康風險指數。
- 台灣測站地圖可直接點選站點，讓地理篩選同步更新趨勢、預測、異常與品質頁面。地圖只顯示目前資料中有可對照座標的測站，不宣稱覆蓋未收錄的地區。

這個設計刻意避免以生成式文字包裝模型結論。每一項判讀都能回查到明確資料欄位與計算規則，適合在面試中討論產品取捨、資料限制與可驗證性。

## 使用資料來源

專案支援兩種資料來源：

- API Data：可在 `config.yaml` 或 `.env` 設定 `AQI_API_URL`。
- Sample Data：若 API 未設定、API 失敗或欄位格式不一致，系統會自動使用本地模擬資料。

Sample data 是模擬資料，只用於本地 Demo、測試與面試展示，不代表真實官方監測資料。預設會產生最近 30 天、8 個中文測站、每小時一筆資料，並模擬日夜週期、週末差異、測站差異、少量缺失值與污染異常事件。若要固定測試日期，可使用 `python src/generate_sample_data.py --start-date 2026-06-01 --days 30`。

## 系統架構

```text
資料取得 / sample fallback
  -> preprocess 欄位標準化、缺失值處理與中文顯示欄位
  -> features 依測站建立 lag / rolling / target
  -> train_predictor 下一小時 AQI 預測
  -> train_anomaly_model 污染異常偵測
  -> evaluate metrics 與 figures
  -> risk_brief 測站脈絡化優先排序與證據摘要
  -> app.py 繁體中文 Streamlit Dashboard / 地圖選站
```

## Repo 結構

```text
aqi-anomaly-dashboard/
├── README.md
├── requirements.txt
├── .gitignore
├── .env.example
├── config.yaml
├── run_all.py
├── run_project.bat
├── run_project_bat內容.txt
├── app.py
├── data/
│   ├── raw/
│   ├── processed/
│   └── sample/
├── models/
├── reports/
│   ├── figures/
│   └── metrics/
├── notebooks/
│   └── 01_eda.ipynb
├── src/
│   ├── fetch_aqi_data.py
│   ├── generate_sample_data.py
│   ├── preprocess.py
│   ├── features.py
│   ├── train_predictor.py
│   ├── train_anomaly_model.py
│   ├── evaluate.py
│   ├── app_helpers.py
│   ├── risk_brief.py
│   ├── smoke_test.py
│   ├── theme.py
│   └── utils.py
└── tests/
    ├── test_sample_data.py
    ├── test_preprocess.py
    ├── test_features.py
    ├── test_model_training.py
    ├── test_evaluate.py
    ├── test_app_import.py
    └── test_run_all.py
```

## 安裝方式

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

## Windows 一鍵執行

如果你使用 Windows，可以直接雙擊：

```text
run_project.bat
```

這個檔案會自動完成：

1. 檢查 Python
2. 建立 `.venv`
3. 安裝 `requirements.txt`
4. 執行 sample mode
5. 執行 smoke test
6. 執行 pytest
7. 啟動 Streamlit Dashboard

`run_project.bat` 內容維持 ASCII-only，避免 Windows CMD 中文編碼誤判；若偵測到舊的 `.venv` 無法執行 pip，會自動重建虛擬環境。

如果不能雙擊執行，也可以在專案根目錄用 PowerShell 或 CMD 執行：

```bat
run_project.bat
```

若 Windows 阻擋執行，請在檔案上按右鍵選擇「解除封鎖」，或改用終端機手動執行下方指令。

`run_project_bat內容.txt` 與 `run_project.bat` 內容完全相同，方便下載後重新命名或複製。

## 一鍵執行指令

```bash
python run_all.py --mode sample
```

API 模式：

```bash
python run_all.py --mode api
```

若 API 失敗，流程會自動 fallback 到 sample data。

## Streamlit 執行方式

```bash
streamlit run app.py
```

若尚未產生資料或模型，請先執行：

```bash
python run_all.py --mode sample
```

## Dashboard 功能

Dashboard 為繁體中文網站，包含：

- 專案介紹與資料來源狀態
- 側邊欄深色主題切換
- 縣市、測站與日期區間篩選
- KPI cards：最新 AQI、AQI 等級、平均 AQI、最新 PM2.5、異常事件數、資料筆數、測站數
- 可點選的台灣測站地圖：標記大小代表目前 AQI，形狀與顏色共同標示關注程度，點選後同步套用測站篩選
- 測站脈絡風險排序：比較本站近 14 天同時段基準、近 6 小時變化、下一小時預測與異常證據
- AQI 趨勢圖
- PM2.5 趨勢圖
- 實際下一小時 AQI vs 預測下一小時 AQI
- 預測誤差圖
- 異常污染時間軸
- 高風險異常事件表格
- 各測站異常事件數
- 資料品質表格
- 預測模型與異常偵測模型指標
- 專案限制與 pseudo-label 說明

Dashboard 顯示使用 `county_display` 與 `site_name_display`，保留原始 `county`、`site_name` 供資料追蹤，但圖表、hover、sidebar 與表格均以中文顯示欄位為主。

## 模型方法

### 下一小時 AQI 預測

此任務是 next-hour forecasting / nowcasting：使用目前與過去資料預測同一測站下一小時 AQI。

Target：

```python
target_next_hour_aqi = groupby(site_name)["aqi"].shift(-1)
```

模型：

- Moving Average baseline
- Linear Regression
- Random Forest Regressor

評估指標：

- MAE
- RMSE
- R2
- baseline MAE / RMSE / R2

### 污染異常偵測

異常偵測使用 pseudo-label，規則如下：

- `AQI > 100`
- 或 `PM2.5 > 35`
- 或 AQI 高於該測站 rolling mean + `2.5 * rolling std`

模型：

- Z-score baseline
- Isolation Forest

評估指標：

- precision
- recall
- f1
- anomaly_rate
- pseudo_label_positive_rate

注意：異常偵測指標是對 pseudo-label 的評估，不是真實人工標註污染事件。

## 避免資料洩漏的做法

- target 使用 `groupby(site_name)["aqi"].shift(-1)`，只預測同測站下一小時 AQI。
- feature columns 不包含 `target_aqi` 或 `target_next_hour_aqi`。
- lag / rolling features 都依 `site_name` 分組計算。
- rolling features 先 `shift(1)` 再 rolling，只使用過去資料。
- 缺失值只在同測站內使用 `ffill()`，不使用會讀到未來值的 `bfill()` 或全期間中位數。
- target 只有在同測站下一筆資料剛好相隔 1 小時時才保留。
- `county_display` 與 `site_name_display` 只作為顯示欄位，不放進模型 feature columns。
- train/test 使用完整 timestamp 邊界切分，同一時刻的不同測站不會分散在兩側，也不使用 random split。
- 使用當下 AQI 預測下一小時 AQI 是 nowcasting 設定，Dashboard 與 README 均明確說明。

## 評估輸出

流程完成後會產生：

```text
models/
├── aqi_predictor.joblib
└── anomaly_detector.joblib

data/processed/
├── aqi_cleaned.csv
├── aqi_features.csv
├── aqi_predictions.csv
├── aqi_anomaly_results.csv
└── aqi_anomaly_events.csv

reports/metrics/
├── predictor_metrics.json
├── anomaly_metrics.json
├── backtest_metrics.json
├── data_health.json
└── evaluation_summary.json

reports/figures/
├── aqi_trend.png
├── prediction_vs_actual.png
└── anomaly_cases.png
```

## 測試與驗證

```bash
pip install -r requirements.txt
python run_all.py --mode sample
python src/smoke_test.py
pytest -q
streamlit run app.py
```

測試涵蓋：

- sample data 產生與欄位完整性
- API 欄位 alias mapping
- `ND`、`NA`、`-`、`x` 等異常字串轉 numeric
- preprocess 缺失值處理
- 因果式補值不讀取未來觀測
- lag / rolling features 不跨測站污染
- train/test 不共享相同 timestamp
- `target_next_hour_aqi` 正確建立
- 測站脈絡判讀只使用該站目前時點以前的觀測，未來資料與其他測站都不會進入基準
- anomaly detector 只用前段時間資料訓練，並以後段時間 pseudo-label 評估
- predictor / anomaly detector 可訓練、儲存、載入與預測
- metrics JSON 與 figures 產生
- `app.py` 可安全 import
- `run_project.bat` 與 `run_project_bat內容.txt` 內容一致
- `run_all.py` sample mode 完整流程
- 深色主題欄位完整性與文字對比檢查
- Plotly 圖表主題化函式使用目前主題的背景、文字與格線色

## 深色主題與可讀性

Dashboard 預設使用深色主題，使用者可以在側邊欄「選擇深色主題」切換不同視覺風格。所有主題集中於 `src/theme.py` 的 `THEME_OPTIONS`，不要在 `app.py` 或其他檔案分散硬寫顏色。

目前提供的深色主題：

- 午夜藍：`midnight_blue`
- 深海綠：`deep_teal`
- 炭黑橘：`charcoal_orange`
- 深藍金：`navy_gold`
- 石板紫：`slate_purple`

每個主題都包含 `background`、`surface`、`card`、`sidebar`、`primary`、`secondary`、`accent`、`danger`、`success`、`warning`、`text`、`muted_text`、`border`、`table_header`、`chart_grid`。Dashboard 的 Sidebar、KPI cards、section notes、Plotly 圖表、hover tooltip、表格與提示訊息都會依目前主題同步套用。

專案提供 `validate_theme_contrast()` 檢查文字與背景對比，避免文字看不清楚。最低要求包含：

- `text` vs `background` >= 4.5
- `text` vs `card` >= 4.5
- `muted_text` vs `background` >= 3.0
- `muted_text` vs `card` >= 3.0
- `danger` vs `background` >= 3.0
- `accent` vs `background` >= 3.0

檢查也涵蓋 `surface`、`sidebar` 與卡片背景，確保表格、篩選元件、hover tooltip 和收合式資料摘要在每個主題都能清楚閱讀。

異常點使用 `danger`，警告使用 `warning`，正常狀態使用 `success`。若要新增主題，必須通過 `validate_theme_contrast()` 與 pytest。

## 常見錯誤排除

- 找不到資料檔：執行 `python run_all.py --mode sample`。
- 找不到模型檔：執行 `python run_all.py --mode sample` 重新訓練。
- API 失敗：確認 `config.yaml` 或 `.env` 的 API URL；沒有 API 時直接使用 sample mode。
- 欄位名稱不一致：在 `src/fetch_aqi_data.py` 與 `src/preprocess.py` 補 alias mapping。
- 套件未安裝：執行 `pip install -r requirements.txt`。
- Streamlit 無法啟動：確認已啟用 `.venv`，或直接雙擊 `run_project.bat`。

## 專案限制

- Sample data 是模擬資料，不代表真實官方監測紀錄。
- 異常偵測 metrics 使用 pseudo-label，不能視為真實事件準確率。
- 本專案是本地端技術展示，不是正式環境監測系統。
- API schema 可能因來源不同而變動，需要維護 alias mapping。
- 模型以傳統機器學習與 baseline 為主，不使用 GPU 或大型深度學習模型。
- 測站脈絡排序是透明的人工檢視輔助，不應取代環境部正式 AQI 資訊、污染源調查或健康建議。
- 地圖座標內建涵蓋 sample data 測站，其他 API 測站會使用可用的縣市中心點；正式部署應改用官方測站經緯度資料。

## 評估設計與可靠性

預測流程採三段式時間序列切分：早期資料用於訓練，中段資料只用於模型選擇，最後一段資料只用於最終報告。候選模型依 validation RMSE 選擇後，才以 train + validation 重新訓練並在 final test 產生 `MAE`、`RMSE`、`R2`。這避免了用最終測試資料挑選模型的選擇偏差。

此外，`backtest_metrics.json` 會使用 rolling-origin backtest：每一個時間窗皆只用先前資料訓練、用後續資料評估。Dashboard 的「預測」與「模型指標」分頁會顯示其平均表現，讓 Demo 不只呈現單一切分的分數。

異常觀測會輸出為 `aqi_anomaly_events.csv`。同一測站、在設定允許間隔內連續發生的異常會合併成一個事件，保留起迄時間、持續小時數、峰值 AQI / PM2.5、最大異常分數與觸發證據；不同測站永遠不會合併。這讓使用者能從「點狀異常」切換為可調查的事件單位。

`data_health.json` 會檢查資料筆數、缺失率、重複的測站時間戳、延遲測站與最大觀測間隔。Dashboard 的資料品質頁會以 metric cards 呈現這些資訊，不會暴露 raw JSON。

風險排序門檻與權重集中在 `config.yaml` 的 `risk_policy`，包括 AQI、PM2.5、相對基準偏離、預測上升與異常訊號。它是透明的人工檢視優先序，不是官方警報或健康風險結論。

新增輸出：

```text
data/processed/aqi_anomaly_events.csv
reports/metrics/backtest_metrics.json
reports/metrics/data_health.json
```

GitHub Actions 的 `Quality Gate` 會在 `main` 的 push / pull request 上重新產生 sample pipeline 並執行 pytest；公開 repo 不提交原始資料、處理後資料、模型或報告產物。

## 未來改進

- 串接穩定的 data.gov.tw 或環境部 AQI 開放資料。
- 以官方測站座標資料取代目前內建的 Demo 座標對照表。
- 整合 Open-Meteo 歷史天氣資料。
- 依測站、季節與時段校準異常門檻。
- 加入模型漂移監控與排程重訓。
- 串接官方測站座標、風場與衛星觀測資料，建立可追溯的事件調查流程。

## 履歷描述

簡短版：

- 建立台灣 AQI 下一小時預測與污染異常偵測 Dashboard，整合資料清理、時間序列特徵工程、模型評估、Streamlit 視覺化、pytest 測試與 Windows 一鍵執行。
- 設計測站脈絡化的污染檢視流程，以本站同時段基準、短期變化、預測與異常證據進行可解釋的人工優先排序，並以可點選台灣地圖串接篩選工作流。

詳細版：

- Built an end-to-end local AQI forecasting and anomaly detection project with API/sample-data fallback, preprocessing, leakage-aware station-level time-series features, model training, evaluation, and a Traditional Chinese Streamlit dashboard.
- Implemented next-hour AQI nowcasting with Moving Average, Linear Regression, and Random Forest, plus pseudo-label anomaly detection with Z-score and Isolation Forest.
- Added a station-context decision layer that ranks inspection priority from station-specific historical baselines, recent movement, forecast and explicit anomaly evidence instead of opaque alert copy.
- Added reproducible local execution through `run_all.py`, `src/smoke_test.py`, pytest coverage, and Windows `run_project.bat`.

## 面試 1 分鐘介紹稿

這個專案是一個台灣 AQI 預測與污染異常偵測 Dashboard。我先把資料流程拆成 API 或 sample data fallback、前處理、時間序列特徵工程、下一小時 AQI 預測、異常偵測、模型評估與 Streamlit 前端。模型任務是 next-hour nowcasting，也就是使用當下與過去資料預測同測站下一小時 AQI。為了避免資料洩漏，我用 `site_name` 分組計算 lag 與 rolling features，target 則用同測站 `shift(-1)`，train/test 採時間序列切分。和一般模型展示不同的是，我在總覽增加一個測站脈絡判讀層：以該站近 14 天同時段基準、近 6 小時變化、下一小時預測和三類異常訊號，透明地排序人工應先檢視的站點，並在地圖上直接選站。這個排序不宣稱是官方警報，而是讓每個結論都有資料證據可回查。即使沒有 API，也能透過 sample mode 和 `run_project.bat` 在本地端完整重現 Demo。

## Security

- `.env` 與 Streamlit secrets 不納入 Git；請只提交 `.env.example`，不要把 API key、token 或密碼寫入設定檔。
- `data/raw`、`data/sample`、`data/processed`、`models` 與 `reports` 的實際產物只在本機生成，Git 僅保留 `.gitkeep`；避免 API 資料、模型二進位檔或報表被誤推到 GitHub。
- API Data 僅接受 HTTPS；本機開發可使用 `localhost`、`127.0.0.1` 或 `::1` 的 HTTP，並限制連線逾時與回應大小。
- 模型載入僅允許 `models/` 下的 `.joblib` 產物；不要載入來源不明的模型檔。Joblib 仍屬於可執行序列化格式，模型應由本專案流程重新產生。
- GitHub Actions 會在 push 與 pull request 執行 `pip-audit`；本次修復將 GitPython 與 Pillow 提升到沒有已知漏洞的版本範圍。

本地安全檢查：

```bash
python -m pip install pip-audit
python -m pip_audit --local
```
