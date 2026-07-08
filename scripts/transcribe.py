# -*- coding: utf-8 -*-
"""把 audio_cache 裡排隊的音檔用 faster-whisper 轉成逐字稿。

輸出統一轉繁體中文，寫入 transcripts/，成功後刪除音檔。

用法：python scripts/transcribe.py [檔名關鍵字]
  不帶參數＝轉錄佇列中全部音檔；帶關鍵字＝只轉檔名含關鍵字的音檔。
"""
import json
import sys
from pathlib import Path

from opencc import OpenCC

from common import ROOT, load_config, transcript_path, write_transcript

AUDIO_EXTS = {".mp3", ".m4a", ".wav", ".ogg", ".opus", ".aac", ".flac", ".webm"}
cc = OpenCC("s2twp")  # 簡體 → 台灣正體（含慣用詞）


def transcribe_file(model, audio_path, language):
    segments, info = model.transcribe(
        str(audio_path),
        language=language,
        batch_size=8,
        vad_filter=True,  # 過濾長靜音，podcast 開頭廣告空白常見
        initial_prompt="以下是台灣財經節目的逐字稿，請使用繁體中文。",
    )
    parts = []
    for seg in segments:
        parts.append(seg.text.strip())
        print(f"\r  進度 {seg.end / info.duration * 100:5.1f}%（{seg.end:.0f}/{info.duration:.0f} 秒）",
              end="", flush=True)
    print()
    return cc.convert(" ".join(parts))


def main():
    config = load_config()
    audio_dir = ROOT / config["settings"]["audio_dir"]
    language = config["settings"].get("language", "zh")
    model_size = config["settings"].get("whisper_model", "medium")

    keyword = sys.argv[1] if len(sys.argv) > 1 else None
    queue = [p for p in audio_dir.iterdir()
             if p.suffix.lower() in AUDIO_EXTS] if audio_dir.exists() else []
    if keyword:
        queue = [p for p in queue if keyword in p.name]
    if not queue:
        print("audio_cache 裡沒有符合條件的待轉錄音檔。")
        return

    print(f"載入 faster-whisper 模型：{model_size}（第一次執行會下載模型檔）")
    from faster_whisper import WhisperModel, BatchedInferencePipeline
    # int8 量化 + 批次推論：CPU 上約 2-4 倍加速，精度損失極小
    model = WhisperModel(model_size, device="auto", compute_type="int8",
                         cpu_threads=8)
    model = BatchedInferencePipeline(model=model)

    for audio_path in queue:
        meta_path = audio_path.with_suffix(".json")
        if meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        else:  # 手動丟進來的音檔也能處理
            meta = {"source": "手動加入", "title": audio_path.stem,
                    "date": "unknown", "url": "", "type": "manual"}

        print(f"轉錄中：{audio_path.name}")
        try:
            text = transcribe_file(model, audio_path, language)
        except Exception as e:
            print(f"  轉錄失敗：{e}，保留音檔下次重試")
            continue

        meta["method"] = f"whisper-{model_size}"
        write_transcript(
            transcript_path(config, meta["source"], meta["date"], meta["title"]),
            meta, text)
        audio_path.unlink()
        if meta_path.exists():
            meta_path.unlink()

    print("\n全部完成。逐字稿在 transcripts/，可以開始做觀點分析。")


if __name__ == "__main__":
    main()
