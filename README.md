# 台灣 AQI 預測與空氣污染異常偵測 Dashboard

本專案是一個可在本地端完整重現的資料科學 side project，主題為「台灣 AQI 預測與空氣污染異常偵測 Dashboard」。專案涵蓋 Open Data / API fallback、AQI / PM2.5 時間序列資料清理、特徵工程、下一小時 AQI 預測、污染異常偵測、模型評估、繁體中文 Streamlit Dashboard、pytest 自動測試與 Windows 一鍵執行。

## 專案目標

- 建立可放上 GitHub 與履歷的完整本地端 AI/ML side project。
- 使用時間序列特徵預測同測站下一小時 AQI。
- 使用 pseudo-label 與 Isolation Forest 偵測可能污染異常事件。
- 提供面試可展示的繁體中文 Dashboard。
- 在沒有 API key、沒有網路或 API 失敗時，仍可使用 sample data 跑完整 Demo。

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
  -> app.py 繁體中文 Streamlit Dashboard
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
└── aqi_anomaly_results.csv

reports/metrics/
├── predictor_metrics.json
├── anomaly_metrics.json
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

## 未來改進

- 串接穩定的 data.gov.tw 或環境部 AQI 開放資料。
- 加入測站經緯度與地圖視覺化。
- 整合 Open-Meteo 歷史天氣資料。
- 依測站、季節與時段校準異常門檻。
- 加入模型漂移監控與排程重訓。

## 履歷描述

簡短版：

- 建立台灣 AQI 下一小時預測與污染異常偵測 Dashboard，整合資料清理、時間序列特徵工程、模型評估、Streamlit 視覺化、pytest 測試與 Windows 一鍵執行。

詳細版：

- Built an end-to-end local AQI forecasting and anomaly detection project with API/sample-data fallback, preprocessing, leakage-aware station-level time-series features, model training, evaluation, and a Traditional Chinese Streamlit dashboard.
- Implemented next-hour AQI nowcasting with Moving Average, Linear Regression, and Random Forest, plus pseudo-label anomaly detection with Z-score and Isolation Forest.
- Added reproducible local execution through `run_all.py`, `src/smoke_test.py`, pytest coverage, and Windows `run_project.bat`.

## 面試 1 分鐘介紹稿

這個專案是一個台灣 AQI 預測與污染異常偵測 Dashboard。我把資料流程拆成 API 或 sample data fallback、前處理、時間序列特徵工程、下一小時 AQI 預測、異常偵測、模型評估與 Streamlit 前端。模型任務是 next-hour nowcasting，也就是使用當下與過去資料預測同測站下一小時 AQI。為了避免資料洩漏，我用 `site_name` 分組計算 lag 與 rolling features，target 則用同測站 `shift(-1)`，train/test 採時間序列切分。前端是繁體中文 Dashboard，可以展示 AQI/PM2.5 趨勢、預測誤差、異常事件、資料品質與模型指標。即使沒有 API，也能透過 sample mode 和 `run_project.bat` 在本地端完整重現 Demo。
