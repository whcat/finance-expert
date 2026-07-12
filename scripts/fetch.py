# -*- coding: utf-8 -*-
"""抓取新內容。

YouTube：先試著抓現成字幕（快、免轉錄）；沒字幕的下載音檔進 audio_cache 等待轉錄。
Podcast：從 RSS 抓新集數的 mp3 進 audio_cache 等待轉錄。

用法：python scripts/fetch.py
"""
import json
import re
import shutil
import urllib.request
from datetime import datetime
from pathlib import Path
from time import mktime

import feedparser
import yt_dlp

from common import (ROOT, load_config, load_processed, save_processed,
                    sanitize_filename, transcript_path, write_transcript)

CAPTION_LANGS = ["zh-TW", "zh-Hant", "zh", "zh-Hans", "zh-CN", "en"]


def clean_description(text, max_len=1200):
    """節目說明常列出來賓名單，是講者辨識的重要線索；去 HTML、截長度。"""
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_len]


def try_fetch_captions(video_id):
    """有字幕就回傳純文字，沒有回傳 None。"""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        try:  # v1.x API
            fetched = YouTubeTranscriptApi().fetch(video_id, languages=CAPTION_LANGS)
            snippets = fetched.snippets
            return " ".join(s.text.strip() for s in snippets if s.text.strip())
        except AttributeError:  # 舊版 API
            data = YouTubeTranscriptApi.get_transcript(video_id, languages=CAPTION_LANGS)
            return " ".join(d["text"].strip() for d in data if d["text"].strip())
    except Exception as e:
        print(f"  無現成字幕（{type(e).__name__}），改走音檔轉錄")
        return None


def download_audio(url, out_stem, audio_dir):
    """下載純音檔到 audio_cache，回傳實際檔案路徑。

    有 ffmpeg 時轉成 mp3；沒有時保留原始格式（webm/m4a），
    faster-whisper 都能直接讀，避免 PATH 問題讓整批抓取中斷。
    """
    opts = {
        "format": "bestaudio/best",
        "outtmpl": str(audio_dir / f"{out_stem}.%(ext)s"),
        "quiet": True, "no_warnings": True,
    }
    if shutil.which("ffmpeg"):
        opts["postprocessors"] = [{"key": "FFmpegExtractAudio",
                                   "preferredcodec": "mp3",
                                   "preferredquality": "64"}]
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([url])
    files = [p for p in audio_dir.glob(f"{out_stem}.*") if p.suffix != ".json"]
    return files[0] if files else None


def queue_audio_meta(audio_dir, out_stem, meta):
    """音檔旁放一份 metadata，transcribe.py 會讀。"""
    (audio_dir / f"{out_stem}.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def process_youtube(config, processed):
    audio_dir = ROOT / config["settings"]["audio_dir"]
    max_items = config["settings"]["max_new_items"]

    for channel in config.get("youtube") or []:
        if not channel.get("enabled"):
            continue
        name = channel["name"]
        print(f"[YouTube] {name}")
        done = set(processed.setdefault(f"yt:{name}", []))

        # 只抓清單不下載，取最近的影片；網址沒指定分頁時預設看 /videos
        channel_url = channel["url"].rstrip("/")
        if not channel_url.endswith(("/videos", "/streams", "/shorts")):
            channel_url += "/videos"
        list_opts = {"extract_flat": True, "playlist_items": f"1-{max_items * 3}",
                     "quiet": True, "no_warnings": True}
        with yt_dlp.YoutubeDL(list_opts) as ydl:
            info = ydl.extract_info(channel_url, download=False)

        new_count = 0
        for entry in info.get("entries") or []:
            if new_count >= max_items:
                break
            vid = entry["id"]
            if vid in done:
                continue
            title = entry.get("title", vid)
            url = f"https://www.youtube.com/watch?v={vid}"
            print(f"  處理：{title}")

            # 補抓上傳日期
            with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True}) as ydl:
                detail = ydl.extract_info(url, download=False)
            upload_date = detail.get("upload_date", "")
            date_str = (f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:8]}"
                        if upload_date else datetime.now().strftime("%Y-%m-%d"))

            meta = {"source": name, "title": title, "date": date_str,
                    "url": url, "type": "youtube",
                    "description": clean_description(detail.get("description"))}
            text = try_fetch_captions(vid)
            if text:
                meta["method"] = "captions"
                write_transcript(transcript_path(config, name, date_str, title),
                                 meta, text)
            else:
                stem = sanitize_filename(f"{name}-{date_str}-{title}", 100)
                try:
                    download_audio(url, stem, audio_dir)
                except Exception as e:
                    # 單支影片下載失敗（如 YouTube 403）不要中斷整批抓取，下次執行再試
                    print(f"  音檔下載失敗（{type(e).__name__}），跳過本支、下次再試")
                    continue
                queue_audio_meta(audio_dir, stem, meta)
                print(f"  音檔已排入轉錄佇列：{stem}.mp3")

            done.add(vid)
            processed[f"yt:{name}"] = sorted(done)
            save_processed(processed)
            new_count += 1

        if new_count == 0:
            print("  沒有新影片")


def process_podcasts(config, processed):
    audio_dir = ROOT / config["settings"]["audio_dir"]
    max_items = config["settings"]["max_new_items"]

    for show in config.get("podcasts") or []:
        if not show.get("enabled"):
            continue
        name = show["name"]
        print(f"[Podcast] {name}")
        done = set(processed.setdefault(f"pod:{name}", []))

        feed = feedparser.parse(show["rss"])
        if feed.bozo and not feed.entries:
            print(f"  RSS 解析失敗：{feed.bozo_exception}")
            continue

        new_count = 0
        for entry in feed.entries:
            if new_count >= max_items:
                break
            eid = entry.get("id") or entry.get("link") or entry.get("title")
            if eid in done:
                continue
            title = entry.get("title", "untitled")
            audio_url = next((l.get("href") for l in entry.get("links", [])
                              if "audio" in l.get("type", "")), None)
            if not audio_url and entry.get("enclosures"):
                audio_url = entry.enclosures[0].get("href")
            if not audio_url:
                print(f"  找不到音檔連結，跳過：{title}")
                done.add(eid)
                continue

            if entry.get("published_parsed"):
                date_str = datetime.fromtimestamp(
                    mktime(entry.published_parsed)).strftime("%Y-%m-%d")
            else:
                date_str = datetime.now().strftime("%Y-%m-%d")

            print(f"  下載：{title}")
            stem = sanitize_filename(f"{name}-{date_str}-{title}", 100)
            ext = Path(audio_url.split("?")[0]).suffix or ".mp3"
            req = urllib.request.Request(audio_url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
            with urllib.request.urlopen(req) as resp, \
                    open(audio_dir / f"{stem}{ext}", "wb") as f:
                shutil.copyfileobj(resp, f)
            queue_audio_meta(audio_dir, stem, {
                "source": name, "title": title, "date": date_str,
                "url": entry.get("link", audio_url), "type": "podcast",
                "description": clean_description(entry.get("summary", ""))})
            print(f"  音檔已排入轉錄佇列：{stem}{ext}")

            done.add(eid)
            processed[f"pod:{name}"] = sorted(done)
            save_processed(processed)
            new_count += 1

        if new_count == 0:
            print("  沒有新集數")


def main():
    config = load_config()
    (ROOT / config["settings"]["audio_dir"]).mkdir(exist_ok=True)
    processed = load_processed()
    process_youtube(config, processed)
    process_podcasts(config, processed)
    print("\n完成。若有音檔排入佇列，接著執行：python scripts/transcribe.py")


if __name__ == "__main__":
    main()
