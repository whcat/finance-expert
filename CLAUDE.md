# Finance_expert 專案指引

追蹤財經 YouTube/Podcast，萃取講者市場觀點。流程：抓取 → Whisper 逐字稿 → 以「人」為主體萃取觀點。

## 架構決策（不要照直覺改）

- **逐字稿以「來源」歸檔、觀點以「人」歸檔**：`transcripts/<節目>/` 放逐字稿，`people/<講者>/views/` 放觀點檔。這是刻意選擇，方便跨節目追蹤同一講者的觀點轉變，不要改回以節目為主體。
- **人名正規化**：萃取觀點前先查 `people/_aliases.yaml`，把講者在不同節目的稱呼、Whisper 常見誤轉寫法對應到同一個標準名，避免同一人裂成多個資料夾。新增別名要往這個檔案加，不要另開新機制。
- **分析規則的唯一來源是 `background.md`**：每位講者一份觀點檔、明確區分事實與〔推測〕、不做投資建議、輸出一律繁體中文。萃取前先讀這份檔案，不要憑印象套用格式。
- 轉錄用本機 faster-whisper（已評估過 NotebookLM 和 Groq API，仍決定維持本機方案，細節見 `PROGRESS.md`）；輸出用 opencc s2twp 轉繁體。YouTube 優先抓現成字幕（youtube-transcript-api），沒有字幕才用 yt-dlp 下載音檔轉錄。

## 講者是否建檔：三集門檻

只為**累積三集以上**的常態講者建立個人觀點檔（`people/<標準名>/views/`）與 `profile.md`。單集或未滿三集的來賓，觀點由該集的「當集總結」涵蓋即可，不要單獨建檔。

此門檻對所有講者一律套用，包含研究員等看似常任但目前集數不足的角色——不要因為身份特殊就加白名單，等自然累積到第三集再回頭補建。

`app.py` 用 `is_tracked_speaker()`（`MIN_VIEWS_TO_SHOW=3`）在側欄同步落實此規則：未達門檻的講者觀點檔不刪、只隱藏，累積到門檻會自動出現。

## 模型選用

執行觀點萃取前，依集數類型用 `/model` 切換：
- 單人節目例行萃取 → Sonnet 5
- 多人訪談的講者分離、profile 彙整 → Opus 4.8
- 三人以上快速交鋒等最難任務 → Fable 5
- Haiku 不可用於核心萃取任務

## 已知風險 / 環境陷阱

- **Streamlit 固定用 port 8502**（設定在 `.streamlit/config.toml`，不進版控）。**8501 是另一個專案在用**（`專案系列\Claud AI Project\Stock analysis` 的 `py/streamlit_app.py`）——處理 python/streamlit 程序（尤其是批次關閉）時務必先確認 port，曾經誤殺過對方的程序。
- git／gh 是後來才裝的（winget），有時終端機 PATH 沒更新，需要時用完整路徑：`C:\Program Files\Git\cmd\git.exe`、`C:\Program Files\GitHub CLI\gh.exe`。

## 公開部署：必須先徵求同意

- 平常改動 app 或內容後，**預設只在 localhost（port 8502）驗證與呈現**，不要主動 `git commit`/`git push`。
- 這個 repo（GitHub `whcat/finance-expert`）接了 Streamlit Community Cloud 自動部署——**任何 `git push` 都會直接更新公開網站**，等同於發布行為。要推上 GitHub 或更新公開網頁前，一定要先問使用者「要推上公開網頁嗎？」，得到明確同意才執行。
- **逐字稿不公開**（版權考量），`.gitignore` 已排除 `transcripts/`、`audio_cache/`、`processed.json`、logs。公開版只有觀點檔、profile、節目總結、比對專題——新增內容類型時要對照這個界線，別不小心把逐字稿相關檔案排除規則改鬆。

## 目前追蹤狀態

- `sources.yaml` 中「數字台灣」自 2026-07-12 起 `enabled: false`（使用者指示不再維持更新）。例行 `fetch.py` 會自動跳過，歷史集數（HD619–HD622）保留。除非使用者重新下指令，否則不要主動改回 `true` 或手動抓取這個來源的新集數。
