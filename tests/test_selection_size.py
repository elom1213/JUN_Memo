# -*- coding: utf-8 -*-
# JUN_Memo v01.06 시험 (오프스크린 PySide6)   python tests/test_selection_size.py
# 1. 고른 글자만 크기: T+ / T- · 단축키 · 고른 부분만 바뀜 · 섞인 크기는 조각마다 한 단계 · 단계 범위 · 고른 것 없으면 이어서 칠 글자 ·
#    Ctrl+Z 한 번 · 저장 / 다시 열기에 남음 · 노트 전체 배율(A- / A+)과 곱해짐 · 전체 배율 기능은 그대로
# 2. 목록 창 Shrink · Pin 이 배경과 구분되는 버튼 (바탕 · 테두리, 여러 목록 색) · Shrunk 는 빨갛지 않음 · 켜진 Pin 만 연한 빨강
import os
import shutil
import sys
import tempfile

os.environ["QT_QPA_PLATFORM"] = "offscreen"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
TMP = tempfile.mkdtemp(prefix="jun_memo_selsize_")
os.environ["JUN_MEMO_SHARED"] = os.path.join(TMP, "shared")

from PySide6.QtGui import QColor, QShortcut, QTextCursor, QTextFormat   # noqa: E402
from PySide6.QtWidgets import QApplication   # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)

from app.core import store as st   # noqa: E402
from app.ui import controller as ctl   # noqa: E402
from app.ui import note_window as nw   # noqa: E402

R = []


def check(name, cond, extra=""):
    R.append(bool(cond))
    print(("PASS " if cond else "FAIL ") + name + ("  | " + str(extra) if extra != "" else ""))


def level_at(editor, pos):
    c = QTextCursor(editor.document())
    c.setPosition(pos + 1)                      # pos 글자 뒤 = 그 글자의 서식
    return c.charFormat().intProperty(QTextFormat.FontSizeAdjustment)


def select(editor, a, b):
    c = editor.textCursor()
    c.setPosition(a)
    c.setPosition(b, QTextCursor.KeepAnchor)
    editor.setTextCursor(c)


def line_height(editor):
    """첫 블록의 높이 - 줄 배치(lineAt)는 아직 안 만들어졌으면 접근 위반으로 죽는다(시험이 한 번 죽었다) → 문서 레이아웃에 묻는다."""
    editor.window().show()
    app.processEvents()
    doc = editor.document()
    return doc.documentLayout().blockBoundingRect(doc.begin()).height()


try:
    c = ctl.Controller(st.NoteStore(os.path.join(TMP, "local")))
    c.quiet = True
    c.start()
    app.processEvents()
    nid = c.new_note()
    w = c.windows[nid]
    ed = w.editor
    text = "Meeting at 3pm in room B"
    ed.setPlainText(text)
    i = text.index("3pm")
    check("buttons T- / T+ are in the format row", w.fmt_buttons["size_up"].text() == "T+" and
          w.fmt_buttons["size_down"].text() == "T−")
    select(ed, i, i + 3)
    w.fmt_buttons["size_up"].click()
    check("T+ on '3pm' = one step larger, only those letters",
          [level_at(ed, i + k) for k in range(3)] == [1, 1, 1] and level_at(ed, i - 2) == 0 and level_at(ed, i + 4) == 0)
    w.apply_format("size_up")
    w.apply_format("size_up")
    w.apply_format("size_up")
    check("steps stop at the largest level (xx-large)", level_at(ed, i) == nw.SIZE_MAX)
    for _ in range(10):
        w.apply_format("size_down")
    check("steps stop at the smallest level (small)", level_at(ed, i) == nw.SIZE_MIN)
    w.apply_format("size_up")                    # 3pm = 0 (보통)
    w.apply_format("size_up")                    # 3pm = 1
    m = text.index("Meeting")
    select(ed, m, i + 3)                         # "Meeting at " (0) + "3pm" (1) 섞임
    w.apply_format("size_up")
    check("mixed sizes: each piece goes up one step (Word-like)", level_at(ed, m) == 1 and level_at(ed, i) == 2,
          (level_at(ed, m), level_at(ed, i)))
    ed.document().undo()
    check("one Ctrl+Z undoes the whole step", level_at(ed, m) == 0 and level_at(ed, i) == 1,
          (level_at(ed, m), level_at(ed, i)))
    # 고른 것 없음 = 이어서 칠 글자
    c_ = ed.textCursor()
    c_.movePosition(QTextCursor.End)
    ed.setTextCursor(c_)
    w.apply_format("size_up")
    ed.insertPlainText(" BIG")
    check("nothing selected: the next typed text gets the size", level_at(ed, len(text) + 2) == 1 and
          level_at(ed, text.index("room")) == 0)
    # 단축키
    keys = sorted(s.key().toString() for s in w.findChildren(QShortcut))
    check("shortcuts Ctrl+Shift+, / Ctrl+Shift+. exist", "Ctrl+Shift+," in keys and "Ctrl+Shift+." in keys, keys)
    # 저장 → 다시 열기
    c._pull_content(nid)
    c.save_now()
    html = c.store.get(nid)["html"]
    check("saved html keeps the relative sizes (x-large etc.), no fixed base size",
          "font-size:x-large" in html or "font-size:large" in html, html[-300:])
    w.close()
    app.processEvents()
    w2 = c.open_note(nid)
    j = w2.editor.toPlainText().index("3pm")
    check("reopened: sizes are back", level_at(w2.editor, j) == 1 and level_at(w2.editor, 0) == 0)
    # 노트 전체 배율과 곱해진다 + 전체 배율 기능은 그대로
    probe = nw.NoteWindow({"id": "p", "html": "", "text": "x", "color": "Yellow", "pinned": False, "open": True,
                           "geometry": None, "zoom": 1.0, "scope": "local", "created": 0, "modified": 0})
    probe.editor.setPlainText("Big")
    select(probe.editor, 0, 3)
    probe.apply_format("size_up")
    probe.apply_format("size_up")
    h100 = line_height(probe.editor)
    probe.set_zoom(2.0)
    h200 = line_height(probe.editor)
    check("selected size multiplies with the note zoom (x-large at 200% is about twice as tall)",
          1.7 < h200 / h100 < 2.3, (h100, h200))
    check("note zoom buttons still there (A- 100% A+)", probe.btn_zoom.text() == "200%" and probe.btn_larger.isEnabled())
    probe.close_quietly()

    # ---- 2. Shrink · Pin 버튼이 배경과 구분된다
    lw = c.list_window
    for color in ("Gray", "Yellow", "Charcoal", "#F3F2F1"):
        lw.set_color(color)
        app.processEvents()
        pal = st.palette(color)
        img = lw.btn_shrink.grab().toImage()
        edge = img.pixelColor(0, img.height() // 2)
        mid = img.pixelColor(img.width() // 2, 3)
        bg = QColor(pal["body"])

        def diff(a, b):
            return abs(a.red() - b.red()) + abs(a.green() - b.green()) + abs(a.blue() - b.blue())
        check("Shrink button stands out from a {0} list (border / fill differ from the background)".format(color),
              diff(edge, bg) > 60 or diff(mid, bg) > 25, (edge.name(), mid.name(), bg.name()))
    lw.set_color("Gray")
    lw.set_shrunk(True)
    lw.set_pinned(True)
    app.processEvents()
    img = lw.btn_shrink.grab().toImage()
    px = img.pixelColor(img.width() // 2, 4)
    pimg = lw.btn_pin.grab().toImage()
    pp = pimg.pixelColor(pimg.width() // 2, 4)
    check("Shrunk (on) is not light red; Pinned (on) is", not (px.red() > 240 and px.green() < 200) and
          pp.red() > 240 and pp.green() < 200, (px.name(), pp.name()))
    for win in list(c.windows.values()):
        win.close_quietly()
    lw.close()
    app.processEvents()
finally:
    shutil.rmtree(TMP, ignore_errors=True)

print("\nRESULT: {0}/{1} passed".format(sum(R), len(R)))
sys.exit(0 if all(R) else 1)
