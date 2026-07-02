# Polaris 形象影片產生器（工作紀實 · 假認真版）

用 HyperFrames 同款技法（純 HTML 動畫 → headless Chromium 逐格截圖 → ffmpeg 合成）
產出 46 秒、1080p 的專題形象影片。**全程本地渲染、零 API 費用。**

## 場景結構（v2：48s @ 24fps，無片頭片尾字卡）

| 時間 | 場景 | 內容 |
|---|---|---|
| 0–7.5s | 背影工作 | 扁平插畫風：主角背影 + 螢幕程式碼逐行生長、打字微動、咖啡熱氣（SVG 手繪） |
| 7–17.5s | 終端機 | 打字動畫：`git pull` → `pytest -q` 全綠 → `git push` |
| 17–27.5s | 編輯器 | VS Code 風格，`retriever.py` 逐字浮現（期別硬過濾，呼應 issue #77） |
| 27–36.5s | GitHub | commit 列表逐筆滑入（**真實 commit 訊息**，來自本 repo） |
| 36–42.5s | 統計卡 | 208 commits / 84 PRs / 24.1K 行 / 128 tests，數字滾動 |
| 42–48s | 背影收尾 | 同開場背影，但螢幕上的程式碼已寫滿一天的量，淡出 |

（v1 為星空片頭／片尾版本，成品保留在 `polaris_工作紀實_v1.mp4`。）

彩蛋：右上角 REC 計時器；統計卡 footer「以上數字皆有來源。」（引用接地憲法梗）。

## 重新渲染

```bash
pip install playwright imageio-ffmpeg   # Chromium 需可用（或 playwright install chromium）
python render.py                        # 產出 polaris_工作紀實_v1.mp4
```

## 改內容

- 文案／場景時間軸：編輯 `promo.html`（`SC` 常數是各場景起訖秒數，`SEEK(t)` 逐格驅動）。
- 換 commit 列表：改 `COMMITS` 陣列（`git log --oneline --format="%h|%s"` 取新資料）。
- 統計數字:改 `STATS` 陣列。
- 預覽單格：瀏覽器開 `promo.html`，console 執行 `SEEK(秒數)`。

配樂請於後製階段自行加入（本片為無聲版，避免版權問題）。
