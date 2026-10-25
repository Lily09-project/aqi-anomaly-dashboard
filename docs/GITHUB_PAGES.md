# GitHub Pages

[開啟 Taiwan Air Lab](https://lily09-project.github.io/aqi-anomaly-dashboard/)

## 發布流程

`.github/workflows/pages.yml`：

1. 安裝鎖定版本的 Python 依賴，執行 `scripts/validate_public_release.py`。
2. `python run_all.py --mode sample` 產生合成資料、分析並寫出 `web/public/data/`。
3. `npm ci && npm run build && npm run size` 建置靜態網站並檢查效能預算。
4. 只上傳 `web/dist/`（不發布儲存庫根目錄）。
5. 合併到 `main` 後部署，並以 `curl` 對線上網址做冒煙測試（首頁標題與 `manifest.json` 的 schema 版本）。

PR 只建置不部署。網站使用相對路徑（Vite `base: "./"`）與 Hash 路由，因此可放在任何子路徑下。

## 網站邊界

- 純靜態：作者的電腦不需要開機，也沒有後端；預報與情境模擬在瀏覽器計算。
- 執行期不呼叫任何第三方服務；CSP 只允許同源資源。
- 每個資料檔載入時以 SHA-256 與 manifest 比對，不符就顯示錯誤，不用不完整的資料計算。
- 使用固定品牌配色、不隨系統色彩偏好切換；支援 `prefers-reduced-motion`、純鍵盤操作；所有圖表都有等價資料表。
- 自動化測試（axe、Playwright）不等同真人螢幕閱讀器或實機驗收。
