# Finance Expert — 財經節目觀點追蹤流程

從 YouTube / Podcast 自動取得逐字稿，再以「講者」為主體萃取市場觀點、追蹤觀點轉變。

## 流程總覽

```
sources.yaml（追蹤清單）
   │
   ▼  python scripts/fetch.py
YouTube 有字幕 ──────────────► transcripts/<節目>/<日期>-<標題>.md
YouTube 無字幕 / Podcast ────► audio_cache/（待轉錄）
   │
   ▼  python scripts/transcribe.py（faster-whisper，輸出繁體）
transcripts/<節目>/<日期>-<標題>.md
   │
   ▼  在 Claude Code 裡：「用 background.md 分析 transcripts 裡的新逐字稿」
people/<講者>/views/<日期>-<節目>-<集名>.md
```

## 日常使用

1. `python scripts/run_pipeline.py` — 依序跑 `fetch.py` → `transcribe.py`，結束後列出本次新增、還沒萃取觀點的逐字稿（也可以分開單獨執行這兩支）
2. 開 Claude Code，說：**「用 background.md 分析 transcripts 裡還沒處理的逐字稿」**
3. `streamlit run app.py` — 開啟觀點瀏覽介面（http://localhost:8502，port 固定在 `.streamlit/config.toml`），可依講者瀏覽立場總覽、觀點時間軸、搜尋全文、對照原始逐字稿

## 設定

- **追蹤清單**：編輯 `sources.yaml`，把來源的 `enabled` 改成 `true`
- **人名別名**：編輯 `people/_aliases.yaml`，讓同一人在不同節目的稱呼歸到同一資料夾
- **Whisper 模型**：`sources.yaml` 的 `whisper_model`（`medium` 是速度/品質的平衡點；有 NVIDIA GPU 可改 `large-v3`）

## 資料夾說明

| 路徑 | 內容 |
|---|---|
| `transcripts/<節目>/` | 原始逐字稿（以來源為主體，不動的原始檔） |
| `people/<講者>/views/` | 單次觀點萃取（以人為主體） |
| `people/<講者>/profile.md` | 講者立場總覽（定期由 views 彙整） |
| `audio_cache/` | 待轉錄音檔（轉完自動刪除；手動丟音檔進來也會被處理） |
| `processed.json` | 已處理集數紀錄（想重抓某來源就刪掉對應的 key） |

## 環境需求

- Python 3.12＋套件：`pip install yt-dlp youtube-transcript-api feedparser faster-whisper opencc-python-reimplemented pyyaml`
- ffmpeg（`winget install Gyan.FFmpeg`）
