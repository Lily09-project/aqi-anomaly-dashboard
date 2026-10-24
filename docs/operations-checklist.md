# 操作檢查表

用於本機展示、資料更新與公開發布前的人工確認，不取代正式監控或告警系統。

## 更新前

- 確認 Git 工作樹乾淨，避免把未確認的修改混入結果。
- 確認 `.env`、API key 與平台 secrets 沒有被 Git 追蹤。
- 執行 `python scripts/validate_public_release.py`。

## 更新後

- `python -W error -m pytest -q --cov=src.analytics --cov=src.export_web --cov-fail-under=90` 全數通過。
- `web/public/data/manifest.json` 的雜湊與網站「資料可信度」頁的瀏覽器端驗證一致（6/6 相符）。
- `cd web && npm run typecheck && npm run lint && npm run coverage && npm run build && npm run size && npm run e2e` 全數通過。
- 開啟網站確認頁首的資料標籤（「模擬資料」或「環境部快照」）正確，頁尾的資料期間合理。
- 「模型監控」頁：若覆蓋率被標為「區間太窄」，或漂移出現「警示」，代表需要重新檢查資料或重新訓練，不要直接發布。

## Fallback 判讀

- API 模式失敗時，`reports/metrics/source_metadata.json` 的 `status` 為 `fallback`，網站會顯示「模擬資料」。
- fallback 原因只保存安全化的代碼，不包含 response body、token 或完整 exception。
- 不將 fallback 的畫面截圖描述成即時資料。

## 公開前

- `git ls-files` 中沒有 CSV、執行期 JSON、`web/public/data/`、`web/dist/`、`.env`。
- 執行 `ruff`、`bandit`、`pip-audit`、`npm audit`。
- README 截圖不含個人路徑、token 或誤導性的即時資料文字。
- `run_project.bat --validate` 在乾淨環境可完成。
