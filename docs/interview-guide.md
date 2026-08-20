# 面試展示講稿與 Demo Guide

這份文件是 Taiwan AQI Monitoring & Forecasting Dashboard 的中文面試講稿。建議使用 Sample Data 進行現場展示，因為它不依賴外部網路、可以重現相同流程，也會在畫面上明確標示「Sample Data（模擬資料）」。如果面試官希望看真實資料，再切換到已設定且通過安全驗證的官方 API endpoint。

## 一分鐘自我介紹版

我做的是一個台灣空氣品質監測與下一小時 AQI 預測平台。它不是只把模型分數畫成圖，而是把資料來源、資料品質、測站比較、預測不確定性與異常事件整理成一個可以追溯的使用流程。使用者可以從台灣地圖或縣市選擇測站，查看 AQI 和 PM2.5 趨勢，再看下一小時的實際值與預測值、80%／95% 預測區間，以及可能需要優先調查的異常案例。

技術上，我使用測站分組的時間序列特徵，target 是同一測站下一小時 AQI，並用 chronological split 和 rolling-origin backtest 避免把未來資料帶進訓練。模型比較包含 Moving Average、Linear Regression 與 Random Forest；異常偵測則同時保留規則式證據、Z-score 與 Isolation Forest。專案也加入 Sample/API provenance、artifact manifest、公開 release gate、測試與 monitoring report，讓 reviewer 能確認結果從哪裡來、哪些結論仍有限制。

## 五分鐘展示順序

### 0:00–0:30：先說明問題與產品價值

「空氣品質資料本身不難取得，難的是讓使用者知道目前哪個測站值得看、預測有多可靠、資料是不是新鮮，以及異常是不是只是資料問題。這個 Dashboard 把這些判讀步驟集中在一個介面，讓模型結果能被查證，而不是只展示一個漂亮的 R2。」

畫面先指向 Header，指出：

- Data Source 會清楚區分 `Sample Data` 與 `API Data`。
- Sample Data 是本地模擬資料，不代表官方即時監測值。
- 目前資料範圍、最新觀測時間與預測週期會一起顯示。

### 0:30–1:20：Overview 與台灣地圖選站

「我先從全台範圍看目前狀態，再用地圖或縣市篩選縮小範圍。篩選條件會同步影響趨勢、預測、異常與資料品質頁，不會發生圖表各自代表不同資料集合的問題。」

操作順序：

1. 點選台灣地圖上的測站或選擇縣市。
2. 查看 Latest AQI、AQI Level、Latest PM2.5、Anomaly Count。
3. 說明 AQI／PM2.5 trend 的時間範圍與測站。
4. 指出地圖座標是由單一 station registry 管理，近似座標會明確標示，不冒充官方精確座標。

### 1:20–2:20：Prediction 頁面

「這裡的任務定義是 next-hour forecasting，也可以理解成以目前已知資料做 nowcasting。target 是同一個測站的下一小時 AQI；當下 AQI 可以是 feature，但 target_aqi 或任何未來值不能回到 feature。」

展示三件事：

- Actual vs Predicted AQI：看模型是否跟得上趨勢。
- Prediction error：看誤差集中在哪些時間段。
- Model comparison：比較 Moving Average、Linear Regression、Random Forest 的 MAE、RMSE、R2，而不是只保留最好的數字。

接著指出 80%／95% empirical forecast interval：「這不是模型保證，而是用 rolling-origin 歷史殘差校準的經驗區間；final test 只用來做最後報告，沒有拿來反向調參。」

### 2:20–3:10：Anomaly Detection 頁面

「異常頁的目的不是宣稱已經找出污染來源，而是提供人工檢視優先順序。」

說明四層證據：

- 規則式 AQI／PM2.5 threshold。
- 同測站歷史基準的 z-score。
- Isolation Forest 的模型訊號。
- 連續異常列合併成 event，方便人閱讀。

最後主動揭露：目前 precision、recall、F1 使用 pseudo-label 做 pipeline evaluation，不等同於真實污染事件準確率；若要正式使用，必須接人工標註或官方事件資料。

### 3:10–3:50：Data Quality 與來源追溯

「我把資料品質放成正式頁面，而不是把 raw JSON 丟給使用者。」

展示 rows、missing cells、station count、date range、source status、latest observation、observation delay 與 station freshness。再說明 API 失敗會 fallback 到 Sample Data，但畫面與 metadata 不會把 fallback 誤標成新鮮 API Data；API key 不寫入 repository、manifest 或前端。

### 3:50–4:30：Model Metrics 與 monitoring

「模型指標頁除了準確度，也會顯示模型可靠性與近期漂移。」

指出：

- 分測站與分 AQI level 指標可暴露平均值掩蓋的弱點。
- `monitoring.json` 比較最近 7 天與之前 14 天，檢查 AQI／PM2.5 分布、MAE 變化和 interval coverage。
- `warning`／`critical` 是診斷訊號，不會自動重訓；是否重訓仍需要人工確認資料品質、來源變更與事件背景。

### 4:30–5:00：工程品質與收尾

「這個專案的重點是從資料到 UI 的完整性。它有 canonical schema、測站隔離的 lag／rolling、時間切分、atomic artifact writes、run manifest、SHA-256、公開 release gate、pytest、Bandit、pip-audit 與 Windows 一鍵啟動驗證。Sample pipeline 可以離線重建，API 也有 URL 驗證、timeout、response size limit 和 fallback。限制則是 Sample Data、pseudo-label 與近似座標都不能直接等同正式環境；下一步會是接人工事件標註、dataset/model registry 與長期監控。」

## 常見追問與回答

### 為什麼不用 random split？

AQI 是時間序列，random split 可能把較晚時間的型態帶進訓練或驗證。專案用 chronological train／validation／final test，並以 rolling-origin backtest 檢查不同歷史窗口。

### 如何證明沒有資料洩漏？

target 使用 `groupby("site_name")["aqi"].shift(-1)`；lag、rolling、差分與 station-hour baseline 都在各測站內計算，rolling 使用當下以前的值。feature contract 會拒絕 target、future 與 prediction 欄位，測試也會驗證下一小時對齊和站點邊界。

### 為什麼需要 Moving Average baseline？

它提供簡單且可解釋的參考點。只有當較複雜模型在時間切分與回測下穩定改善 baseline，才有理由保留它；否則模型複雜度沒有帶來產品價值。

### pseudo-label 會不會讓 anomaly metrics 失真？

會，因此 UI 與 README 都把 precision、recall、F1 標示為 pseudo-label evaluation。它只能驗證 pipeline 行為與規則一致性，不能替代真實標註。正式環境應加入人工審查流程與真實事件資料。

### 為什麼要做 monitoring？

模型在離線 test 很好，不代表資料分布和線上誤差永遠不變。用不重疊的 reference／current windows 同時看 feature drift、prediction error 與 interval coverage，可以先提供可解讀的診斷訊號，再由人決定是否重訓。

## 面試前準備

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python run_all.py --mode sample
streamlit run app.py
```

面試前建議先執行 `run_project.bat --validate`，確認 pipeline、smoke test、pytest 與 public release gate 均通過。展示時不要把 `data/processed`、`models` 或 `reports/metrics` 的生成檔提交到 GitHub；它們應由 pipeline 重建。
