# -*- coding: utf-8 -*-
"""共用工具：設定檔載入、已處理紀錄、檔名處理。"""
import json
import re
import sys
from pathlib import Path

import yaml

# Windows 主控台預設 cp950，遇到字幕裡的特殊符號會當掉
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
SOURCES_FILE = ROOT / "sources.yaml"
PROCESSED_FILE = ROOT / "processed.json"


def load_config():
    with open(SOURCES_FILE, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_processed():
    if PROCESSED_FILE.exists():
        with open(PROCESSED_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_processed(processed):
    with open(PROCESSED_FILE, "w", encoding="utf-8") as f:
        json.dump(processed, f, ensure_ascii=False, indent=2)


def sanitize_filename(name, max_len=80):
    """移除 Windows 不允許的字元，截短過長標題。"""
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", name)
    name = re.sub(r"\s+", " ", name).strip().rstrip(".")
    return name[:max_len]


def transcript_path(config, source_name, date_str, title):
    """逐字稿輸出路徑：transcripts/<來源>/<日期>-<標題>.md"""
    out_dir = ROOT / config["settings"]["transcript_dir"] / sanitize_filename(source_name)
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir / f"{date_str}-{sanitize_filename(title)}.md"


def write_transcript(path, meta, text):
    """逐字稿統一格式：YAML frontmatter + 內文。"""
    lines = ["---"]
    for k, v in meta.items():
        lines.append(f"{k}: {json.dumps(v, ensure_ascii=False)}")
    lines.append("---")
    lines.append("")
    lines.append(text)
    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"  已寫入逐字稿：{path.relative_to(ROOT)}")
