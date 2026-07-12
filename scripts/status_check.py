# -*- coding: utf-8 -*-
"""一鍵檢查兩件「不會自動更新」的事：

1. 待萃取：哪些逐字稿還沒被萃取成觀點檔／當集總結。
2. 待回驗：profile 預測表裡「驗證時點」已過、但結果還停在「待驗證／進行中」的預測。

用法：python scripts/status_check.py
只讀不寫，純提醒用。
"""
import re
from datetime import date
from pathlib import Path

from common import ROOT, load_config

TODAY = date.today()

# 各節目的萃取產物落點，用來判斷某集逐字稿是否已萃取。
#   ("single", 講者)  單人節目 → 該講者 views/ 有同日期檔案即算已萃取
#   ("summary", 節目) 多人主題節目 → shows/<節目>/summaries/ 有同日期檔案即算已萃取
# 新增追蹤來源時，記得在這裡補一行對應規則。
SHOW_EXTRACTION = {
    "Gooaye 股癌": ("single", "謝孟恭"),
    "游庭皓的財經皓角": ("single", "游庭皓"),
    "美股投資學-財女珍妮": ("single", "王怡人"),
    "數字台灣": ("summary", "數字台灣"),
    "MacroMicro財經M平方": ("summary", "MacroMicro財經M平方"),
}

# 已決定「不萃取」的逐字稿（純產品宣傳／非市場內容等），用日期關鍵字比對，
# 避免每次檢查都被重複標為待萃取。新增略過項時在此加一行並註明原因。
SKIP_TRANSCRIPTS = {
    "2026-05-18",  # MM「AI is Coming」純 MM Max AI 產品上線廣告，無市場內容（2026-07-12 使用者同意跳過）
}


def file_dates(folder):
    """回傳資料夾底下所有檔名開頭 YYYY-MM-DD 的日期字串集合。"""
    if not folder.exists():
        return set()
    dates = set()
    for f in folder.glob("*.md"):
        m = re.match(r"(\d{4}-\d{2}-\d{2})", f.name)
        if m:
            dates.add(m.group(1))
    return dates


def check_unextracted():
    config = load_config()
    transcript_dir = ROOT / config["settings"]["transcript_dir"]
    people_dir = ROOT / "people"
    shows_dir = ROOT / "shows"

    pending = []       # (節目, 日期, 逐字稿檔名)
    unknown_shows = []
    if not transcript_dir.exists():
        return pending, unknown_shows

    for show_dir in sorted(transcript_dir.iterdir()):
        if not show_dir.is_dir():
            continue
        show = show_dir.name
        rule = SHOW_EXTRACTION.get(show)
        if rule is None:
            unknown_shows.append(show)
            continue
        kind, target = rule
        if kind == "single":
            done = file_dates(people_dir / target / "views")
        else:  # summary
            done = file_dates(shows_dir / target / "summaries")

        for f in sorted(show_dir.glob("*.md")):
            m = re.match(r"(\d{4}-\d{2}-\d{2})", f.name)
            if m and m.group(1) not in done and m.group(1) not in SKIP_TRANSCRIPTS:
                pending.append((show, m.group(1), f.name))
    return pending, unknown_shows


def resolve_deadline(when):
    """把『驗證時點』字串盡量解析成一個到期日；解析不出來回傳 None。"""
    when = when.strip()
    # YYYY-MM-DD
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", when)
    if m:
        return date(int(m[1]), int(m[2]), int(m[3]))
    # YYYY QN（季）
    m = re.search(r"(\d{4})\s*Q([1-4])", when)
    if m:
        end_month = int(m[2]) * 3
        return date(int(m[1]), end_month, 28)
    # YYYY-MM
    m = re.search(r"(\d{4})-(\d{2})", when)
    if m:
        return date(int(m[1]), int(m[2]), 28)
    # N 月中／初／底／月（假設當年）
    m = re.search(r"(\d{1,2})\s*月(中|初|底)?", when)
    if m:
        day = {"初": 5, "中": 15, "底": 28, None: 28}[m.group(2)]
        return date(TODAY.year, int(m[1]), day)
    # M/D，如 6/18、7/8
    m = re.search(r"(?<!\d)(\d{1,2})/(\d{1,2})(?!\d)", when)
    if m:
        return date(TODAY.year, int(m[1]), int(m[2]))
    # 純年份，如 2028、2030
    m = re.search(r"(?<!\d)(20\d{2})(?!\d|\-)", when)
    if m:
        return date(int(m[1]), 12, 31)
    return None  # 持續／短期／中期／未來數月 等模糊詞


def check_predictions():
    people_dir = ROOT / "people"
    overdue = []   # (講者, 日期, 預測, 驗證時點, 到期日)
    undated = []   # (講者, 日期, 預測, 驗證時點)  結果仍待驗證但驗證時點無明確日期
    for prof in sorted(people_dir.glob("*/profile.md")):
        speaker = prof.parent.name
        for line in prof.read_text(encoding="utf-8").splitlines():
            cells = [c.strip() for c in line.split("|")[1:-1]]
            if len(cells) != 4:
                continue
            pred_date, pred, when, result = cells
            if not re.match(r"\d{4}-\d{2}-\d{2}", pred_date):  # 跳過表頭與分隔線
                continue
            if "待驗證" not in result and "進行中" not in result:
                continue
            deadline = resolve_deadline(when)
            if deadline is None:
                undated.append((speaker, pred_date, pred, when))
            elif deadline < TODAY:
                overdue.append((speaker, pred_date, pred, when, deadline))
    return overdue, undated


def main():
    print(f"檢查基準日：{TODAY}\n")

    pending, unknown = check_unextracted()
    print("=" * 50)
    print("【待萃取】有逐字稿、還沒萃取成觀點檔／當集總結：")
    if pending:
        for show, d, name in pending:
            print(f"  - {show} ｜ {d} ｜ {name}")
    else:
        print("  （無，所有逐字稿都已萃取）")
    if unknown:
        print("  ⚠️ 下列節目不在 SHOW_EXTRACTION 對照表，無法判斷，請補規則：")
        for s in unknown:
            print(f"     - {s}")

    overdue, undated = check_predictions()
    print("\n" + "=" * 50)
    print("【待回驗】驗證時點已過、結果仍停在待驗證／進行中：")
    if overdue:
        for speaker, d, pred, when, deadline in sorted(overdue, key=lambda x: x[4]):
            print(f"  - {speaker} ｜ {d} 預測 ｜ 驗證時點「{when}」(≈{deadline}) 已過")
            print(f"      {pred[:60]}")
    else:
        print("  （無逾期未回驗的預測）")

    if undated:
        print(f"\n  另有 {len(undated)} 則待驗證預測的驗證時點是模糊詞（持續／中期等），需人工判斷，略。")


if __name__ == "__main__":
    main()
