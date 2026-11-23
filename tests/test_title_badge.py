# -*- coding: utf-8 -*-
# JUN_Memo v01.09 시험 (오프스크린 PySide6)   python tests/test_title_badge.py
# 노트 제목(범위 배지 옆): 저장 · 공유 파일 · 다시 읽기 · 검색 · 목록 카드 · 창 제목 · 옛 파일 호환,
# 목록 카드의 범위 배지 높이가 카드마다 같다(📌 · 제목 · 글자 수와 상관없이)
import json
import os
import shutil
import sys
import tempfile
import time

os.environ["QT_QPA_PLATFORM"] = "offscreen"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
TMP = tempfile.mkdtemp(prefix="jun_memo_title_")
os.environ["JUN_MEMO_SHARED"] = os.path.join(TMP, "shared")
os.environ["APPDATA"] = os.path.join(TMP, "appdata")

from PySide6.QtWidgets import QApplication   # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)

from app.core import store as st   # noqa: E402
from app.ui import controller as ctl   # noqa: E402
from app.ui import list_window as lwm   # noqa: E402

R = []


def check(name, cond, extra=""):
    R.append(bool(cond))
    print(("PASS " if cond else "FAIL ") + name + ("  | " + str(extra) if extra != "" else ""))


def pump(ms=50):
    end = time.time() + ms / 1000.0
    while True:
        app.processEvents()
        if time.time() >= end:
            break
        time.sleep(0.01)


try:
    local, shared = os.path.join(TMP, "local"), os.path.join(TMP, "shared")
    s = st.NoteStore(local, shared)
    a = s.new_note(scope=st.SCOPE_SHARED)
    check("new note has an empty title", a["title"] == "")
    t0 = a["modified"]
    time.sleep(0.01)
    check("set_title changes it and bumps modified", s.set_title(a["id"], "  Shopping \n list ") and
          a["title"] == "Shopping list" and a["modified"] > t0)
    check("same title again = no change", not s.set_title(a["id"], "Shopping list"))
    check("a note with only a title is not empty", not s.is_empty(a["id"]))
    b = s.new_note()
    s.set_content(b["id"], "<p>milk</p>", "milk")
    check("search finds the title too", [n["id"] for n in s.ordered("shopping")] == [a["id"]])
    s.save()
    sf = json.load(open(os.path.join(shared, a["id"] + ".json"), encoding="utf-8"))
    check("title is in the shared file", sf.get("title") == "Shopping list")
    check("title kept after restart", st.NoteStore(local, shared).get(a["id"])["title"] == "Shopping list")
    # 옛 파일 (title 없음)
    sf.pop("title")
    with open(os.path.join(shared, a["id"] + ".json"), "w", encoding="utf-8") as fh:
        json.dump(sf, fh)
    old = st.NoteStore(local, shared)
    check("old file without a title reads as empty title", old.get(a["id"])["title"] == "")
    m = os.path.getmtime(os.path.join(shared, a["id"] + ".json"))
    time.sleep(0.05)
    old.save()
    check("old shared file is not rewritten just for the new key",
          os.path.getmtime(os.path.join(shared, a["id"] + ".json")) == m)

    # ---- 노트 창 · 목록 (controller)
    shutil.rmtree(local, ignore_errors=True)
    c = ctl.Controller(st.NoteStore(local, shared))
    nid = c.new_note(scope=st.SCOPE_LOCAL)
    win = c.windows[nid]
    check("note window has a title box beside the scope badge",
          win.ipf_title.parent() is win.header and win.ipf_title.x() > win.lbl_scope.x(), win.ipf_title.placeholderText())
    win.ipf_title.setFocus()
    from PySide6.QtTest import QTest   # noqa: E402
    QTest.keyClicks(win.ipf_title, "Todo")
    pump(50)
    c.save_now()
    check("typing a title saves it", c.store.get(nid)["title"] == "Todo")
    check("window title uses the note title", win.windowTitle() == "JUN Memo - Todo", win.windowTitle())
    card = None
    lw = c.list_window
    for i in range(lw.list.count()):
        if lw.list.item(i).data(0x0100) == nid:
            card = lw.list.itemWidget(lw.list.item(i))
    check("list card shows the title", card is not None and card.lbl_title.text() == "Todo" and
          not card.lbl_title.isHidden())
    win.close()
    pump(50)
    c2 = ctl.Controller(st.NoteStore(local, shared))
    w2 = c2.open_note(nid)
    check("title is back when the note opens again", w2.ipf_title.text() == "Todo")
    w2.close()

    # ---- 배지 높이 (카드마다 같게)
    s3 = st.NoteStore(os.path.join(TMP, "l3"), os.path.join(TMP, "s3"))
    for scope, pin, title, text in (("local", False, "", "a"), ("shared", True, "Big title", "b\nc\nd"),
                                    ("local", True, "", ""), ("shared", False, "", "x" * 300)):
        n = s3.new_note(scope=scope)
        s3.set_content(n["id"], "<p/>", text)
        s3.set_title(n["id"], title)
        s3.update(n["id"], pinned=pin)
    lw3 = lwm.ListWindow(s3)
    lw3.show()
    pump(50)
    heights = [lw3.list.itemWidget(lw3.list.item(i)).lbl_scope.height() for i in range(lw3.list.count())]
    check("scope badges are the same height on every card", len(set(heights)) == 1, heights)
    lw3.set_text_zoom(1.5)
    pump(50)
    heights = [lw3.list.itemWidget(lw3.list.item(i)).lbl_scope.height() for i in range(lw3.list.count())]
    check("...also at a bigger text size", len(set(heights)) == 1, heights)
    lw3.close()
finally:
    shutil.rmtree(TMP, ignore_errors=True)

print("\nRESULT: {0}/{1} passed".format(sum(R), len(R)))
sys.exit(0 if all(R) else 1)
