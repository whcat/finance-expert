# -*- coding: utf-8 -*-
"""日常一鍵流程：抓取新集數 → 轉錄音檔佇列 → 列出待萃取觀點的逐字稿。

觀點萃取仍需要 Claude 手動執行（讀 background.md 分析），這支只自動化
「抓取」與「轉錄」兩步，並在最後提醒有哪些新逐字稿還沒萃取。

用法：python scripts/run_pipeline.py
"""
import subprocess
import sys

from common import ROOT, load_config


def run_step(script_name):
    print(f"\n{'=' * 10} 執行 {script_name} {'=' * 10}")
    result = subprocess.run([sys.executable, f"scripts/{script_name}"], cwd=ROOT)
    if result.returncode != 0:
        print(f"\n{script_name} 失敗（exit {result.returncode}），流程中止。")
        sys.exit(result.returncode)


def list_transcripts():
    config = load_config()
    transcript_dir = ROOT / config["settings"]["transcript_dir"]
    if not transcript_dir.exists():
        return set()
    return set(transcript_dir.glob("*/*.md"))


def main():
    before = list_transcripts()

    run_step("fetch.py")
    run_step("transcribe.py")

    new_files = sorted(list_transcripts() - before)

    print("\n" + "=" * 40)
    if new_files:
        print(f"本次新增 {len(new_files)} 篇逐字稿，待萃取觀點：")
        for f in new_files:
            print(f"  - {f.relative_to(ROOT)}")
        print("\n下一步：開 Claude Code，說「用 background.md 分析 transcripts 裡還沒處理的逐字稿」")
    else:
        print("沒有新逐字稿，流程結束。")


if __name__ == "__main__":
    main()
