# 台灣 AQI 監測、下一小時預測與異常事件判讀 Dashboard

一個可在本機完整重現的端到端資料產品專案：從空氣品質資料取得、清理、時間序列特徵工程、模型訓練與評估，到繁體中文 Streamlit Dashboard、台灣地圖選站、預測可信度、異常事件整理與自動化測試。

本專案不把重點停留在「模型分數」或單一趨勢圖，而是把模型輸出轉成可以被人檢查、比較與追溯的監測工作流程。使用者可以先從地圖或篩選器選擇區域，再依照測站自身歷史脈絡、近期變化、下一小時預測、預測區間與異常證據，決定哪些測站值得優先檢視。

> 重要說明：Sample Data 是模擬資料，只用於本地 Demo、測試與開發，不代表環境部官方即時監測資料。模型結果也不是官方警報、醫療建議、污染來源判定或行程建議。

## 專案摘要

| 項目 | 說明 |
| --- | --- |
| 專案類型 | End-to-end data science / ML product side project |
| 使用情境 | 台灣多測站 AQI 監測、下一小時趨勢判讀與異常事件初篩 |
| 前端 | Streamlit、Plotly、繁體中文 Dashboard |
| 預測模型 | Moving Average、Linear Regression、Random Forest |
| 異常模型 | Z-score baseline、Isolation Forest |
| 預測任務 | 使用當下與過去資料預測同測站下一小時 AQI |
| 評估設計 | Rolling-origin backtest、時間序列切分、80% / 95% 經驗預測區間 |
| 可重現性 | run_all.py、src/smoke_test.py、pytest、Windows 一鍵啟動檔 |
| 公開原則 | GitHub 只保留程式、設定範例、測試與文件；生成物由流程重新建立 |

## 這個專案的核心價值

### 從模型展示提升為判讀工作流

一般 AQI Demo 往往只有一張趨勢圖與一個預測數字。本專案增加測站脈絡化判讀層：

- 以同測站近 14 天、相同小時且早於目前時間的觀測建立歷史基準。
- 同時觀察目前 AQI、近 6 小時變化、PM2.5、下一小時預測與異常訊號。
- 將異常證據拆成規則式標籤、Z-score 與 Isolation Forest，而不是輸出無法解釋的單一風險分數。
- 以可點選的台灣測站地圖同步更新測站篩選、趨勢、預測、異常與資料品質資訊。

這個排序是人工檢視的優先順序，不是官方警報。每個判讀結論都應能回到資料欄位與計算規則。

### 同時處理預測準確度與預測不確定性

預測頁除了 Actual vs Predicted，也會呈現 80% / 95% 經驗預測區間、區間寬度、final-test coverage，以及區間是否跨過下一個 AQI 分級門檻。

預測區間使用 final test 之前的 rolling-origin out-of-fold 絕對殘差校準；final test 只用於最後報告，不反過來調整區間。這能清楚區分「模型平均預測得準不準」與「這一次預測有多不確定」。

### 多測站比較具備資料新鮮度門檻

地區比較可選擇 2 至 3 個測站，並排比較目前 AQI、下一小時預測、80% 預測區間、本站基準、PM2.5、觀測時間與異常證據。系統會排除相對最新測站落後超過 2 小時的資料，再產生可追溯的比較結果。

## Dashboard 功能

| 頁面 | 主要內容 |
| --- | --- |
| 總覽 | AQI / PM2.5 趨勢、台灣測站地圖、測站脈絡風險排序、活動提示 |
| 地區比較 | 2 至 3 個測站並排比較、資料時差檢查、預測區間與 CSV 匯出 |
| 預測 | Actual vs Predicted、預測誤差、模型比較、rolling backtest、跨級提示 |
| 異常偵測 | 異常事件摘要、時間軸、高風險事件表、各測站異常數與觸發證據 |
| 資料品質 | 資料可靠性、缺失欄位、資料樣本、測站覆蓋、延遲與觀測間隔 |
| 模型指標 | 三種預測模型比較、分測站可靠性與 pseudo-label 限制 |

共用功能包含：

- 首屏顯示專案名稱、資料來源、Sample Data / API Data、最新資料時點與預測週期。
- 縣市、測站與日期區間篩選。
- 深色主題切換；所有色票集中於 src/theme.py，並以對比度檢查保護可讀性。
- KPI：最新 AQI、AQI 等級、平均 AQI、最新 PM2.5、異常觀測、資料筆數、測站數與資料狀態。
- 可下載目前篩選後的公開 CSV 與繁體中文純文字摘要。
- 匯出資料不含 target、lag、rolling window 或其他模型內部特徵。

## 系統架構

~~~text
API Data / Sample Data fallback
        │
        ▼
fetch_aqi_data.py       URL 驗證、大小限制、JSON / CSV、欄位 alias
generate_sample_data.py 最近 30 天模擬資料或固定日期測試資料
        │
        ▼
preprocess.py            欄位標準化、numeric 轉換、時間解析、缺失值處理
        │
        ▼
features.py              每測站 lag、rolling、差分與 next-hour target
        ├───────────────┐
        ▼               ▼
train_predictor.py   train_anomaly_model.py
預測、回測、區間     pseudo-label、Z-score、
與可靠性分析         Isolation Forest、事件合併
        │               │
        └───────┬───────┘
                ▼
evaluate.py / model_reliability.py / data_health.py
metrics、figures、資料健康度、分站可靠性
                │
                ▼
app.py + src/dashboard/
Streamlit UI、地圖、篩選、下載與六個功能頁
~~~

### 主要模組

| 模組 | 責任 |
| --- | --- |
| run_all.py | 串起資料、特徵、模型、評估與 smoke test |
| src/fetch_aqi_data.py | API 取得、URL 驗證、回應大小限制與欄位轉換 |
| src/generate_sample_data.py | 產生可重現的多測站模擬資料 |
| src/preprocess.py | 外部欄位轉成 canonical schema |
| src/features.py | 建立不讀取未來值的時間序列特徵與 target |
| src/train_predictor.py | 回測選模、最終訓練、預測與預測區間 |
| src/train_anomaly_model.py | 異常模型、pseudo-label 評估與事件輸出 |
| src/risk_brief.py | 測站歷史脈絡、透明風險排序與異常證據 |
| src/station_comparison.py | 多測站比較、資料新鮮度門檻與公開匯出 |
| src/dashboard/ | Dashboard context、資料服務、頁面、元件與樣式 |
| src/theme.py | 主題色票、圖表顏色與對比度驗證 |
| tests/ | 資料、模型、UI、輸出、效能、安全與整體流程測試 |

## 快速開始

### 需求

- Python 3.10 以上；CI 使用 Python 3.12。
- Windows、macOS 或 Linux。
- Dashboard 需要 Streamlit；依賴由 requirements.txt 管理。
- API mode 需要可連線到指定資料端點；沒有 API 時可使用 sample mode。

### 安裝依賴

Windows PowerShell：

~~~powershell
python -m venv .venv
.\\.venv\\Scripts\\Activate.ps1
python -m pip install -r requirements.txt
~~~

Windows CMD：

~~~bat
python -m venv .venv
.venv\\Scripts\\activate
python -m pip install -r requirements.txt
~~~

macOS / Linux：

~~~bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
~~~

### 執行完整 Sample Pipeline

~~~bash
python run_all.py --mode sample
~~~

流程會依序建立資料夾、產生 Sample Data、前處理、建立特徵、訓練兩類模型、輸出 metrics / figures，最後執行 smoke test。

### 啟動 Dashboard

~~~bash
streamlit run app.py
~~~

通常開啟 http://localhost:8501。若尚未建立資料或模型，先執行 python run_all.py --mode sample。

### Windows 一鍵啟動

在專案根目錄雙擊 [run_project.bat](run_project.bat)，或執行：

~~~bat
run_project.bat
~~~

啟動檔會找 Python、建立或修復 .venv、安裝依賴、執行 sample pipeline、smoke test、pytest，自動尋找可用 port，並在檢查通過後啟動 Streamlit。

只驗證、不啟動網站：

~~~bat
run_project.bat --validate
~~~

run_project_bat內容.txt 是啟動檔文字備份，內容與 run_project.bat 保持一致。

## 資料來源與資料契約

### Sample Data

src/generate_sample_data.py 預設產生從今天往前推算的最近 30 天、每小時一筆、8 個測站資料，模擬日夜與通勤週期、週末差異、測站差異、少量缺失值與污染波動。

欄位包含：

~~~text
datetime, site_name, county, aqi, pm25, pm10, o3,
co, wind_speed, wind_directions
~~~

預設日期會隨執行日更新，避免 Demo 看起來像使用未來資料。若測試需要固定日期：

~~~bash
python src/generate_sample_data.py --start-date 2026-06-01 --days 30
~~~

Sample Data 只代表可重現的測試情境，不可用來推論真實空氣品質或官方警示。

### API Data

API URL 可以放在 config.yaml 的 api.url，或放入未提交的 .env：

~~~dotenv
AQI_API_URL=https://your-aqi-endpoint.example/api/data
~~~

API parser 支援 JSON records / result / data 結構與 CSV，並把來源欄位轉成 canonical schema。必要欄位為 datetime、site_name、county、aqi、pm25、pm10、o3、co、wind_speed 與 wind_directions。

API 讀取具備：

- 非 localhost 的 HTTP 端點拒絕，正式端點必須使用 HTTPS。
- timeout 上下限。
- 10 MB 回應大小上限。
- 欄位不足、格式錯誤或連線失敗時自動 fallback 到 Sample Data。

## 模型方法

### 下一小時 AQI 預測

任務是 next-hour forecasting / nowcasting：使用同測站目前與過去可取得的資訊，預測該測站下一小時 AQI。

Target 定義：

~~~python
target_next_hour_aqi = groupby(site_name)["aqi"].shift(-1)
~~~

特徵包含：

- 時間：hour、day_of_week、month、is_weekend。
- 當下觀測：aqi、pm25、pm10、o3、co、wind_speed。
- 滯後：lag_1_aqi、lag_3_aqi、pm25_lag_1。
- 滾動：rolling_3h_aqi、rolling_6h_aqi、rolling_12h_aqi、pm25_rolling_3h。
- 變化：aqi_diff、pm25_diff。
- 測站脈絡：只使用目前時間以前的 station_hour_baseline_aqi。

候選模型：

1. Moving Average：可解釋 baseline。
2. Linear Regression：低複雜度線性模型。
3. Random Forest Regressor：處理非線性與特徵交互作用。

模型先以 pre-test rolling-origin backtest 比較平均 RMSE；學習模型必須優於 Moving Average 才能勝出。選定後才用 train + validation 重新訓練，最後在 final test 報告 MAE、RMSE 與 R2。

### 預測可信度

forecast_confidence.json 會保存 80% / 95% 經驗預測區間的校準資訊：

1. 在 final test 之前建立 rolling-origin out-of-fold prediction。
2. 收集模型絕對殘差作為校準資料。
3. 以有限樣本 conformal quantile 建立區間寬度。
4. 在 final test 計算 empirical coverage 與平均區間寬度。
5. 比較 AQI 門檻 50、100、150、200、300，產生跨級關注提示。

這些區間是歷史誤差下的 empirical coverage，不是對未來污染分布的保證機率。

### 異常偵測

目前的 pseudo-label 規則為：

~~~text
AQI > 100
或 PM2.5 > 35
或 AQI > 測站 rolling mean + 2.5 × rolling std
~~~

模型與 baseline：

- Z-score baseline。
- Isolation Forest。

輸出包含 precision、recall、F1、anomaly rate 與 pseudo-label positive rate。這些指標代表模型對規則標籤的重現程度，不等同於真實污染事件準確率。

異常觀測會依測站與時間間隔合併成 aqi_anomaly_events.csv，提供事件起迄、持續時間、峰值 AQI / PM2.5、最大異常分數與觸發證據。

## 資料洩漏防護

- target 只使用同測站下一筆、且時間間隔為 1 小時的 AQI。
- target_aqi 與 target_next_hour_aqi 不會進入 feature columns。
- lag 與 rolling 全部依 site_name 分組，測站之間不會互相污染。
- rolling 先 shift(1) 再計算，避免把當前或未來 target 混入窗口。
- 缺失值只在同測站內 forward fill，不使用會讀到未來值的 backward fill。
- 測站歷史基準以時間順序逐筆建立，只讀取該測站當下以前的資料。
- train、validation、final test 依 timestamp 邊界切分，不使用 random split。
- 不同測站在相同 timestamp 會留在同一切分側，避免時點污染。
- final test 不參與選模、預測區間校準或門檻調整。
- Dashboard 與文件明確揭露使用當下 AQI 預測下一小時 AQI 是 nowcasting。

## 輸出檔案

執行 python run_all.py --mode sample 後，會在本機產生：

~~~text
data/
├── sample/sample_aqi.csv
└── processed/
    ├── aqi_cleaned.csv
    ├── aqi_features.csv
    ├── aqi_predictions.csv
    ├── aqi_anomaly_results.csv
    └── aqi_anomaly_events.csv

models/
├── aqi_predictor.joblib
└── anomaly_detector.joblib

reports/
├── figures/
│   ├── aqi_trend.png
│   ├── prediction_vs_actual.png
│   └── anomaly_cases.png
└── metrics/
    ├── predictor_metrics.json
    ├── anomaly_metrics.json
    ├── backtest_metrics.json
    ├── forecast_confidence.json
    ├── data_health.json
    └── evaluation_summary.json
~~~

這些生成物由 .gitignore 排除。公開 repo 只保留程式碼、設定、測試、文件與 .gitkeep，clone 後可重新建立資料與模型。

## 測試與品質驗證

常用指令：

~~~bash
python -m pip install -r requirements.txt
python run_all.py --mode sample
python src/smoke_test.py
pytest -q
~~~

測試涵蓋：

- Sample Data 日期、欄位、筆數與固定日期參數。
- Preprocess alias、numeric、datetime 與缺失值處理。
- Features lag、rolling、差分、target 與測站邊界。
- 模型訓練、joblib 載入、預測長度、時間切分與回測選模。
- MAE、RMSE、R2、anomaly precision / recall / F1、JSON 與圖檔。
- 預測區間校準、coverage、區間寬度與 final test 隔離。
- Dashboard import、缺資料、缺模型、頁面 renderer 與主題載入。
- UI 對比度、深色卡片、焦點、停用、觸控尺寸、響應式樣式與表格。
- 地圖選站、測站比較、公開欄位匯出、事件合併與資料品質。
- API URL、回應大小、模型路徑與敏感設定安全檢查。
- run_all.py 與 run_project.bat --validate 的完整流程。

效能基準：

~~~bash
python src/benchmark_dashboard.py
~~~

效能數值只適合在同一台機器、同一組輸出資料前後比較，不應直接當成跨環境 SLA。

## 公開與安全性

- .env、Streamlit secrets、API key、token 與密碼不得提交到 Git。
- data/raw、data/sample、data/processed、models 與 reports 的生成物預設不追蹤。
- API Data 只接受 HTTPS；只有 localhost 開發端點可以使用 HTTP。
- API 請求有 timeout 與 10 MB 回應上限。
- Joblib 只從專案 models/ 載入 .joblib；不要載入來源不明的模型檔。
- GitHub Actions 的 Quality Gate 會重建 sample pipeline 並執行 pytest。
- GitHub Actions 的 Security Audit 會執行 pip-audit，並阻擋生成資料、模型與報表被追蹤。

本機依賴檢查：

~~~bash
python -m pip install pip-audit
python -m pip_audit --local
~~~

## Repo 結構

~~~text
aqi-anomaly-dashboard/
├── README.md
├── app.py
├── run_all.py
├── run_project.bat
├── config.yaml
├── requirements.txt
├── .env.example
├── data/                          # Generated local data, ignored by Git
├── models/                        # Generated local models, ignored by Git
├── reports/                       # Generated local reports, ignored by Git
├── notebooks/01_eda.ipynb
├── src/
│   ├── fetch_aqi_data.py
│   ├── generate_sample_data.py
│   ├── preprocess.py
│   ├── features.py
│   ├── train_predictor.py
│   ├── train_anomaly_model.py
│   ├── forecast_confidence.py
│   ├── model_reliability.py
│   ├── risk_brief.py
│   ├── station_comparison.py
│   ├── anomaly_events.py
│   ├── data_health.py
│   ├── evaluate.py
│   ├── smoke_test.py
│   ├── theme.py
│   └── dashboard/
└── tests/
~~~

## 設定與可調整策略

主要設定集中在 config.yaml：

- api.url、timeout 與資料路徑。
- train.feature_columns、validation / test ratio 與 backtest folds。
- forecast_confidence.levels 與 AQI 門檻。
- anomaly contamination、AQI / PM2.5 pseudo-label 門檻與事件間隔。
- risk policy 的 lookback、近期窗口、基準門檻與排序權重。

若新增主題，請在 src/theme.py 加入完整色票，通過 validate_theme_contrast() 與 pytest，並避免在 app.py 或頁面檔案散落顏色常數。

## 專案限制

- Sample Data 是模擬資料，不能取代官方監測資料。
- API schema 可能變動，需持續維護 alias mapping 與資料品質規則。
- 異常偵測以 pseudo-label 為基準，沒有真實人工事件標註時，precision / recall / F1 只能解讀為規則一致性。
- 預測區間是歷史誤差下的 empirical coverage；資料分布改變時需要重新校準。
- 模型未納入完整氣象場、交通、排放源、地形與衛星觀測，因此不能做污染因果解釋。
- 測站脈絡排序是人工檢視輔助，不是官方警報或健康風險分數。
- 地區比較不代表個人暴露量、交通時間或健康適宜性。
- 地圖座標對 Sample Data 有內建對照；正式部署應改用官方測站經緯度資料。

## 未來改進方向

1. 串接穩定的環境部或 data.gov.tw 開放資料，建立資料版本與更新時間。
2. 以官方測站經緯度、測站狀態與維護資訊取代 Demo 座標。
3. 加入可信氣象來源，評估風速、風向、降雨與邊界層條件。
4. 依測站、季節與時段校準異常門檻，並導入人工事件標註。
5. 加入資料漂移、預測漂移、coverage 漂移與模型重訓監控。
6. 以排程工作與容器化部署支援每日更新。
7. 加入模型版本、資料版本與評估報告 lineage，讓每次結果可回溯。

## 履歷使用版本

### 中文履歷 bullet

- 建立台灣 AQI 端到端資料產品，整合 API / Sample Data fallback、資料清理、測站級時間序列特徵、下一小時 AQI 預測、異常事件偵測、模型評估與繁體中文 Streamlit Dashboard。
- 設計測站脈絡化判讀與多測站比較流程，以歷史基準、近期變化、資料新鮮度、預測區間與異常證據產生可追溯的人工檢視優先順序，並以台灣地圖串接選站互動。
- 實作 leakage-aware rolling-origin 評估與 80% / 95% 經驗預測區間，揭露分測站可靠性、AQI 區間表現、coverage、區間寬度與 pseudo-label 限制。
- 建立可重現的 pipeline、smoke test、pytest、依賴安全稽核與 Windows 一鍵啟動流程，並將生成資料與模型排除在公開 GitHub repo 外。

### English resume bullets

- Built an end-to-end Taiwan AQI monitoring product with API/sample-data fallback, preprocessing, station-aware time-series features, next-hour forecasting, anomaly detection, evaluation reports, and a Traditional Chinese Streamlit dashboard.
- Designed an evidence-first station triage layer using station-specific historical baselines, recent movement, data freshness, forecast intervals, and explicit anomaly signals instead of opaque alert scores.
- Implemented leakage-aware rolling-origin model selection and 80% / 95% empirical forecast intervals, with station-level reliability, AQI-band metrics, coverage, interval width, and sample-size reporting.
- Delivered reproducible local execution through run_all.py, smoke tests, pytest, dependency auditing, GitHub Actions quality gates, and a Windows one-click launcher while keeping generated artifacts out of the public repository.

## 一分鐘面試介紹稿

這是一個台灣 AQI 監測與下一小時預測 Dashboard。我把整個流程拆成資料取得、前處理、測站級時間序列特徵、預測模型、異常偵測、評估與前端判讀。預測任務是使用目前與過去資料預測同測站下一小時 AQI，因此我用同測站 shift(-1) 建立 target，所有 lag / rolling 特徵都依測站分組並先 shift，train、validation 與 final test 依時間切分，避免把未來資訊帶進模型。專案的差異化不只是模型，而是判讀流程：總覽會用每個測站自己的歷史基準、近期變化、下一小時預測與異常證據排序人工檢視優先級，並可直接從台灣地圖選站；地區比較則會先檢查資料時差，再並排呈現 2 至 3 個測站的目前 AQI、預測、預測區間與異常脈絡。為了避免只展示單一漂亮分數，我用 rolling-origin 回測選模，只有學習模型優於 Moving Average 才會勝出，並用 final test 之前的殘差校準 80% / 95% 預測區間，同時揭露分測站可靠性與區間 coverage。異常偵測則明確標示是 pseudo-label 評估，不把規則一致性說成真實事件準確率。最後，整個專案可以透過 run_all.py、pytest、smoke test 與 Windows 一鍵啟動重現，生成資料與模型不提交到 GitHub，讓程式碼、測試與資料責任都能被檢查。

## 使用範圍

目前專案主要作為個人 side project、作品集、面試展示與本地測試使用。若要正式部署或對外提供健康、行程或環境決策服務，應先補足官方資料授權、資料品質 SLA、模型監控、人工標註、風險揭露與適用的法規審查。
