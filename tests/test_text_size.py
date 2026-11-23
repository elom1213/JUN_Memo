# -*- coding: utf-8 -*-
# JUN_Memo v01.05 글자 크기 시험 (오프스크린 PySide6)   python tests/test_text_size.py
# 노트: A- / 100% / A+ · Ctrl + 휠 · Ctrl+= / Ctrl+- / Ctrl+0 · 범위 · 기억(이 PC state.json, 공유 파일은 그대로) · 다시 열기 ·
#       옛 노트(HTML 에 11pt 가 박힌 것)도 크기가 따라옴 · 굵게 등 서식 유지
# 목록: Ctrl + 휠 · 메뉴 Larger / Smaller / Reset · 기억
# Shrunk 버튼은 켜져도 연한 빨강이 아니다 (Pin 은 그대로)
import json
import os
import shutil
import sys
import tempfile

os.environ["QT_QPA_PLATFORM"] = "offscreen"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
TMP = tempfile.mkdtemp(prefix="jun_memo_zoom_")
SHARED = os.path.join(TMP, "shared")
os.environ["JUN_MEMO_SHARED"] = SHARED

from PySide6.QtCore import QEvent, QPoint, QPointF, Qt   # noqa: E402
from PySide6.QtGui import QFont, QTextCursor, QWheelEvent   # noqa: E402
from PySide6.QtWidgets import QApplication   # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)

from app.core import store as st   # noqa: E402
from app.ui import controller as ctl   # noqa: E402
from app.ui import note_window as nw   # noqa: E402

R = []


def check(name, cond, extra=""):
    R.append(bool(cond))
    print(("PASS " if cond else "FAIL ") + name + ("  | " + str(extra) if extra != "" else ""))


def wheel(widget, up=True, ctrl=True):
    ev = QWheelEvent(QPointF(10, 10), QPointF(widget.mapToGlobal(QPoint(10, 10))), QPoint(0, 0),
                     QPoint(0, 120 if up else -120), Qt.NoButton, Qt.ControlModifier if ctrl else Qt.NoModifier,
                     Qt.NoScrollPhase, False)
    QApplication.sendEvent(widget, ev)
    app.processEvents()


def rendered_pt(editor, pos=2):
    c = QTextCursor(editor.document())
    c.setPosition(pos)
    f = c.charFormat().font()
    return f.pointSizeF() if c.charFormat().fontPointSize() > 0 else editor.document().defaultFont().pointSizeF()


try:
    local = os.path.join(TMP, "local")
    c = ctl.Controller(st.NoteStore(local))
    c.quiet = True
    c.start()
    app.processEvents()
    nid = c.new_note(scope=st.SCOPE_SHARED)
    w = c.windows[nid]
    w.editor.setHtml("<b>Bold</b> plain")
    check("note: starts at 100% (11 pt), buttons A- 100% A+", w.zoom == 1.0 and w.btn_zoom.text() == "100%" and
          abs(rendered_pt(w.editor, 7) - 11.0) < 0.01)
    w.btn_larger.click()
    w.btn_larger.click()
    check("A+ twice = 120%, the text follows (13.2 pt)", w.btn_zoom.text() == "120%" and
          abs(rendered_pt(w.editor, 7) - 13.2) < 0.01, rendered_pt(w.editor, 7))
    check("bold text grows too and stays bold", abs(rendered_pt(w.editor, 2) - 13.2) < 0.01 and
          QTextCursor(w.editor.document()).block().begin().fragment().charFormat().fontWeight() >= QFont.Bold)
    wheel(w.editor.viewport(), up=False)
    check("Ctrl + wheel down = smaller (110%)", w.btn_zoom.text() == "110%")
    w.editor.verticalScrollBar().setValue(0)
    wheel(w.editor.viewport(), up=True, ctrl=False)
    check("wheel without Ctrl does not change the size", w.btn_zoom.text() == "110%")
    for _ in range(40):
        w.step_zoom(1)
    check("biggest = 300%, A+ disabled", w.btn_zoom.text() == "300%" and not w.btn_larger.isEnabled())
    for _ in range(40):
        w.step_zoom(-1)
    check("smallest = 60%, A- disabled", w.btn_zoom.text() == "60%" and not w.btn_smaller.isEnabled())
    w.btn_zoom.click()
    check("click the % = back to 100%", w.zoom == 1.0)
    w.set_zoom(1.5)
    c.save_now()
    state = json.load(open(os.path.join(local, "state.json"), encoding="utf-8"))
    check("the size is saved per note in this PC's state.json", state["notes"][nid]["zoom"] == 1.5)
    c.windows[nid].editor.setPlainText("shared note text")
    c.save_now()
    shared_file = json.load(open(os.path.join(SHARED, nid + ".json"), encoding="utf-8"))
    check("the shared note file has no size and no fixed 11pt in its HTML (each PC keeps its own size)",
          "zoom" not in shared_file and "font-size" not in shared_file["html"], shared_file["html"][:200])
    w.close()
    app.processEvents()
    c.open_note(nid)
    app.processEvents()
    check("reopening the note keeps its size", c.windows[nid].zoom == 1.5 and c.windows[nid].btn_zoom.text() == "150%")
    # 옛 노트: HTML body 에 11pt 가 박혀 있다
    old_html = ('<!DOCTYPE HTML><html><head></head><body style=" font-family:\'Segoe UI\'; font-size:11pt; '
                'font-weight:400; font-style:normal;"><p>old note</p></body></html>')
    check("strip_base_size removes only the body font-size", "font-size" not in nw.strip_base_size(old_html) and
          "font-family" in nw.strip_base_size(old_html))
    old = c.store.new_note()
    c.store.set_content(old["id"], old_html, "old note")
    c.store.update(old["id"], zoom=2.0)
    ow = c.open_note(old["id"])
    check("an old note (11pt fixed in its HTML) still follows the size (22 pt at 200%)",
          abs(rendered_pt(ow.editor, 2) - 22.0) < 0.01, rendered_pt(ow.editor, 2))

    # ---- 목록 글자 크기
    lw = c.list_window
    lw.refresh()
    card = lw.list.itemWidget(lw.list.item(0))
    base = card.lbl_text.font().pointSizeF()
    wheel(lw.list.viewport(), up=True)
    card = lw.list.itemWidget(lw.list.item(0))
    check("list: Ctrl + wheel up = bigger card text", card.lbl_text.font().pointSizeF() > base and
          c.store.list_view["zoom"] == 1.1, (base, card.lbl_text.font().pointSizeF()))
    lw.act_larger.trigger()
    lw.act_smaller.trigger()
    lw.act_smaller.trigger()
    check("list: menu Larger / Smaller", c.store.list_view["zoom"] == 1.0)
    lw.act_larger.trigger()
    c.save_now()
    check("list: size saved", json.load(open(os.path.join(local, "state.json"), encoding="utf-8"))["list"]["zoom"] == 1.1)
    lw.act_reset_zoom.trigger()
    check("list: Reset text size", c.store.list_view["zoom"] == 1.0)

    # ---- Shrunk 는 빨갛지 않다
    ss = lw.styleSheet()
    lw.set_shrunk(True)
    lw.set_pinned(True)
    app.processEvents()
    check("Shrunk button is not light red when on (Pin still is)",
          lw.btn_shrink.objectName() == "shrinkBtn" and "QToolButton#shrinkBtn:checked { background: #FFFFFF;" in ss and
          "QToolButton:checked { background: #FFB3B3" in ss and lw.btn_shrink.isChecked() and lw.btn_pin.isChecked())
    img = lw.btn_shrink.grab().toImage()
    px = img.pixelColor(3, img.height() // 2)
    check("Shrunk button really paints without the red (pixel check)", not (px.red() > 240 and px.green() < 200),
          px.name())
    for win in list(c.windows.values()):
        win.close_quietly()
    lw.close()
    app.processEvents()
finally:
    shutil.rmtree(TMP, ignore_errors=True)

print("\nRESULT: {0}/{1} passed".format(sum(R), len(R)))
sys.exit(0 if all(R) else 1)
