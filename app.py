# -*- coding: utf-8 -*-
"""財經觀點追蹤介面：瀏覽 people/ 底下的講者立場總覽、觀點檔，
以及 shows/ 底下主題式節目（如數字台灣）的當集總結。

講者與節目並列在同一個側欄選單中，各自有獨立版面。

啟動：streamlit run app.py
"""
import re
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent
PEOPLE_DIR = ROOT / "people"
TRANSCRIPT_DIR = ROOT / "transcripts"
COMPARISON_DIR = ROOT / "comparisons"
SHOWS_DIR = ROOT / "shows"

st.set_page_config(page_title="財經觀點追蹤", page_icon="📈", layout="wide")

# 只顯示「常態講者」：累積三集以上的觀點檔、或已彙整 profile.md 的講者。
# 單集受訪者（多為主題式節目一次性來賓）不獨立列於側欄，其論點由該節目的
# 當集總結涵蓋；日後某講者累積到門檻集數，就會自動出現在清單中。
MIN_VIEWS_TO_SHOW = 3


def clean_markdown(text):
    """相對路徑的 .md 連結在 Streamlit 裡點不開，轉成純文字；http 連結保留。"""
    return re.sub(r"\[([^\]]+)\]\((?!http)[^)]+\)", r"\1", text)


def parse_dated_file(f):
    text = f.read_text(encoding="utf-8")
    m = re.match(r"(\d{4}-\d{2}-\d{2})-?(.*)", f.stem)
    date, title = (m.group(1), m.group(2)) if m else ("", f.stem)
    return date, title or f.stem, text


# ---------- 講者（people/） ----------

def person_has_profile(name):
    return (PEOPLE_DIR / name / "profile.md").exists()


def view_count(name):
    views_dir = PEOPLE_DIR / name / "views"
    return sum(1 for _ in views_dir.glob("*.md")) if views_dir.exists() else 0


def is_tracked_speaker(name):
    """常態講者才列於側欄：有 profile.md，或觀點檔已達門檻集數。"""
    return person_has_profile(name) or view_count(name) >= MIN_VIEWS_TO_SHOW


def list_people():
    if not PEOPLE_DIR.exists():
        return []
    return sorted(d.name for d in PEOPLE_DIR.iterdir()
                  if d.is_dir() and is_tracked_speaker(d.name))


@st.cache_data(ttl=60)
def load_views(speaker):
    views = []
    views_dir = PEOPLE_DIR / speaker / "views"
    if views_dir.exists():
        for f in sorted(views_dir.glob("*.md"), reverse=True):
            date, title, text = parse_dated_file(f)
            kw = re.search(r"主題關鍵字：(.+)", text)
            views.append({"date": date, "title": title,
                         "keywords": kw.group(1).strip() if kw else "", "text": text})
    return views


def load_profile(speaker):
    p = PEOPLE_DIR / speaker / "profile.md"
    return p.read_text(encoding="utf-8") if p.exists() else None


# ---------- 節目（shows/） ----------

def show_has_summaries(name):
    d = SHOWS_DIR / name / "summaries"
    return d.exists() and any(d.glob("*.md"))


def list_shows():
    if not SHOWS_DIR.exists():
        return []
    return sorted(d.name for d in SHOWS_DIR.iterdir() if d.is_dir())


@st.cache_data(ttl=60)
def load_show_summaries(show_name):
    items = []
    d = SHOWS_DIR / show_name / "summaries"
    if d.exists():
        for f in sorted(d.glob("*.md"), reverse=True):
            date, title, text = parse_dated_file(f)
            items.append({"date": date, "title": title, "text": text})
    return items


# ---------- 逐字稿（transcripts/） ----------

@st.cache_data(ttl=60)
def list_transcripts():
    items = []
    if TRANSCRIPT_DIR.exists():
        for show_dir in sorted(TRANSCRIPT_DIR.iterdir()):
            if show_dir.is_dir():
                for f in sorted(show_dir.glob("*.md"), reverse=True):
                    items.append({"show": show_dir.name, "name": f.stem, "path": f})
    return items


def render_transcripts_tab(default_show=None):
    st.caption("原始逐字稿，供對照查證引句。")
    transcripts = list_transcripts()
    if not transcripts:
        st.info("transcripts/ 底下還沒有逐字稿。")
        return
    show_names = sorted({t["show"] for t in transcripts})
    index = show_names.index(default_show) if default_show in show_names else 0
    show = st.selectbox("節目", show_names, index=index)
    for t in [x for x in transcripts if x["show"] == show]:
        with st.expander(t["name"]):
            st.markdown(t["path"].read_text(encoding="utf-8"))


def render_compare_tab():
    st.caption("跨講者的觀點比對專題（全域內容）。")
    comp_files = sorted(COMPARISON_DIR.glob("*.md"), reverse=True) if COMPARISON_DIR.exists() else []
    if not comp_files:
        st.info("comparisons/ 底下還沒有比對專題。累積多位講者的觀點檔後，可以請 Claude 產出交叉比對。")
        return
    names = [f.stem for f in comp_files]
    picked = st.selectbox("專題", names, key="compare_picker")
    f = comp_files[names.index(picked)]
    st.markdown(clean_markdown(f.read_text(encoding="utf-8")))


# ---------- 側欄：講者在上、節目在下，分開兩組 ----------
st.sidebar.title("📈 財經觀點追蹤")

person_names = sorted(list_people(), key=lambda n: (not person_has_profile(n), n))
show_names = sorted(list_shows(), key=lambda n: (not show_has_summaries(n), n))

if not person_names and not show_names:
    st.info("`people/` 和 `shows/` 底下都還沒有內容。先執行觀點萃取後再回來。")
    st.stop()

if "active_kind" not in st.session_state:
    st.session_state.active_kind = "person" if person_names else "show"


def _pick_person():
    """點講者時清空節目選取：radio 值沒變化不會觸發 on_change，
    若讓節目維持選取狀態，之後再點同一個節目會切不回去。"""
    st.session_state.active_kind = "person"
    if show_names:
        st.session_state.show_radio = None


def _pick_show():
    st.session_state.active_kind = "show"
    if person_names:
        st.session_state.person_radio = None


st.sidebar.caption("講者")
person_choice = None
if person_names:
    person_choice = st.sidebar.radio(
        "講者", person_names, key="person_radio",
        on_change=_pick_person, label_visibility="collapsed",
    )
else:
    st.sidebar.caption("（尚無講者資料）")

st.sidebar.divider()

st.sidebar.caption("節目")
show_choice = None
if show_names:
    show_choice = st.sidebar.radio(
        "節目", show_names, key="show_radio", index=None,
        on_change=_pick_show, label_visibility="collapsed",
    )
else:
    st.sidebar.caption("（尚無節目總結）")

if st.session_state.active_kind == "show" and show_choice:
    picked = {"type": "show", "name": show_choice}
elif person_choice:
    picked = {"type": "person", "name": person_choice}
elif show_choice:
    picked = {"type": "show", "name": show_choice}
else:
    picked = {"type": "person", "name": person_names[0]} if person_names \
        else {"type": "show", "name": show_names[0]}

st.sidebar.divider()
query = st.sidebar.text_input("🔍 搜尋內容", placeholder="例如：記憶體、升息、台積電")
st.sidebar.caption("搜尋會比對全文，支援多個關鍵字（空格分隔，需全部命中）。")

# ---------- 主畫面 ----------
st.title(picked["name"])

if picked["type"] == "person":
    speaker = picked["name"]
    views = load_views(speaker)
    if query.strip():
        terms = query.split()
        views = [v for v in views if all(t in v["text"] for t in terms)]
    if views:
        st.caption(f"觀點檔 {len(views)} 份 ｜ 涵蓋 {views[-1]['date']} ～ {views[0]['date']}"
                   + (f" ｜ 搜尋條件：{query}" if query.strip() else ""))

    tab_profile, tab_views, tab_compare, tab_transcripts = st.tabs(
        ["📋 立場總覽", "🗂 觀點時間軸", "🔀 交叉比對", "📄 逐字稿庫"])

    with tab_profile:
        profile = load_profile(speaker)
        if profile:
            st.markdown(clean_markdown(profile))
        else:
            st.info("這位講者還沒有 profile.md。累積幾份觀點檔後，可以請 Claude 彙整立場總覽。")

    with tab_views:
        if not views:
            st.warning("沒有符合條件的觀點檔。")
        for i, v in enumerate(views):
            label = f"{v['date']}｜{v['title']}"
            if v["keywords"]:
                label += f"　`{v['keywords']}`"
            with st.expander(label, expanded=(i == 0 and bool(query.strip()))):
                st.markdown(clean_markdown(v["text"]))

    with tab_compare:
        render_compare_tab()

    with tab_transcripts:
        render_transcripts_tab()

else:
    show_name = picked["name"]
    summaries = load_show_summaries(show_name)
    if query.strip():
        terms = query.split()
        summaries = [s for s in summaries if all(t in s["text"] for t in terms)]
    if summaries:
        st.caption(f"節目總結 {len(summaries)} 份 ｜ 涵蓋 {summaries[-1]['date']} ～ {summaries[0]['date']}"
                   + (f" ｜ 搜尋條件：{query}" if query.strip() else ""))

    tab_summary, tab_show_transcripts, tab_compare = st.tabs(
        ["📺 節目總結", "📄 逐字稿庫", "🔀 交叉比對"])

    with tab_summary:
        if not summaries:
            st.info(f"{show_name} 底下還沒有節目總結。主題式對談節目萃取觀點時，"
                    "可以請 Claude 額外產出當集總結（見 background.md 規則）。")
        for i, s in enumerate(summaries):
            label = f"{s['date']}｜{s['title']}"
            with st.expander(label, expanded=(i == 0 and bool(query.strip()))):
                st.markdown(clean_markdown(s["text"]))

    with tab_show_transcripts:
        render_transcripts_tab(default_show=show_name)

    with tab_compare:
        render_compare_tab()
