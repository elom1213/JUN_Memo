# -*- coding: utf-8 -*-
# JUN_Memo v01.10 시험 (오프스크린 PySide6)   python tests/test_header_popup.py
# v01.09 회귀 두 가지:
#  - 제목칸이 띠를 다 차지해 머리를 잡고 노트를 옮길 수 없던 것 → 띠에 빈 곳이 남고, 그곳을 끌면 창이 움직인다
#  - 제목 있는 노트에 글을 치면(저장 → 목록 다시 그림) 카드의 제목 라벨이 잠깐 독립 창으로 떴다 사라지던 것
import os
import shutil
import sys
import tempfile
import time

os.environ["QT_QPA_PLATFORM"] = "offscreen"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
TMP = tempfile.mkdtemp(prefix="jun_memo_header_")
os.environ["JUN_MEMO_SHARED"] = os.path.join(TMP, "shared")
os.environ["APPDATA"] = os.path.join(TMP, "appdata")

from PySide6.QtCore import QEvent, QObject, QPoint, Qt   # noqa: E402
from PySide6.QtTest import QTest   # noqa: E402
from PySide6.QtWidgets import QApplication, QWidget   # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)

from app.core import store as st   # noqa: E402
from app.ui import controller as ctl   # noqa: E402

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


class ShowSpy(QObject):
    """독립 창(top-level)으로 보이게 된 위젯을 모은다."""

    def __init__(self, allowed):
        super().__init__()
        self.allowed = allowed
        self.popups = []

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Show and isinstance(obj, QWidget) and obj.isWindow() and \
                not any(obj is w for w in self.allowed()) and type(obj).__name__ not in ("QMenu", "QTipLabel"):
            self.popups.append(type(obj).__name__ + ":" + obj.objectName())
        return False


try:
    c = ctl.Controller(st.NoteStore(os.path.join(TMP, "local"), os.path.join(TMP, "shared")))
    c.list_window.show()
    nid = c.new_note()
    win = c.windows[nid]
    win.resize(320, 300)
    pump()

    def empty_header_points():
        h = win.header
        return [x for x in range(0, h.width(), 2) if h.childAt(QPoint(x, h.height() // 2)) is None]

    for title in ("", "Weekly plan", "A very long title that goes on and on and on"):
        win.ipf_title.setFocus()
        win.ipf_title.selectAll()
        QTest.keyClicks(win.ipf_title, title) if title else QTest.keyClick(win.ipf_title, Qt.Key_Delete)
        pump()
        free = empty_header_points()
        check("title box fits its text and leaves header space with title {0!r}".format(title[:12]),
              len(free) >= 5 and win.ipf_title.width() <= 160,
              "{0} px free, title box {1} px".format(len(free) * 2, win.ipf_title.width()))
    win.editor.setFocus()
    pump()

    # 제목칸(고치는 중 아님)을 잡고 끌어도 창이 움직인다 - 좁은 노트에서도 머리 어디든
    start = win.pos()
    tp = win.ipf_title.rect().center()
    QTest.mousePress(win.ipf_title, Qt.LeftButton, Qt.NoModifier, tp)
    QTest.mouseMove(win.ipf_title, tp + QPoint(50, 40))
    QTest.mouseRelease(win.ipf_title, Qt.LeftButton, Qt.NoModifier, tp + QPoint(50, 40))
    pump()
    check("dragging on the title box moves the note", win.pos() != start and not win.ipf_title.hasFocus(),
          (start, win.pos()))
    QTest.mouseClick(win.ipf_title, Qt.LeftButton, Qt.NoModifier, tp)
    pump()
    check("clicking the title box (no drag) starts editing it", win.ipf_title.hasFocus())
    start = win.pos()
    QTest.mousePress(win.ipf_title, Qt.LeftButton, Qt.NoModifier, tp)
    QTest.mouseMove(win.ipf_title, tp + QPoint(40, 0))
    QTest.mouseRelease(win.ipf_title, Qt.LeftButton, Qt.NoModifier, tp + QPoint(40, 0))
    pump()
    check("while editing, dragging in the title box selects text (note stays)", win.pos() == start)

    # 빈 곳을 끌면 창이 움직인다
    free = empty_header_points()
    x = free[len(free) // 2]
    start = win.pos()
    p = QPoint(x, win.header.height() // 2)
    QTest.mousePress(win.header, Qt.LeftButton, Qt.NoModifier, p)
    QTest.mouseMove(win.header, p + QPoint(40, 30))
    QTest.mouseRelease(win.header, Qt.LeftButton, Qt.NoModifier, p + QPoint(40, 30))
    pump()
    check("dragging the header moves the note", win.pos() != start, (start, win.pos()))
    # 범위 배지 위를 잡아도 움직인다
    start = win.pos()
    bp = win.lbl_scope.geometry().center()
    QTest.mousePress(win.header, Qt.LeftButton, Qt.NoModifier, bp)
    QTest.mouseMove(win.header, bp + QPoint(-30, 20))
    QTest.mouseRelease(win.header, Qt.LeftButton, Qt.NoModifier, bp + QPoint(-30, 20))
    pump()
    check("dragging on the scope badge moves the note too", win.pos() != start)

    # 글 치기 - 독립 창이 뜨면 안 된다
    c.save_now()
    spy = ShowSpy(lambda: [c.list_window] + list(c.windows.values()))
    app.installEventFilter(spy)
    win.editor.setFocus()
    for ch in "hello world":
        QTest.keyClicks(win.editor, ch)
        c.save_now()                                        # 저장 = 목록 다시 그림 (타이머를 기다리지 않고)
        pump(10)
    app.removeEventFilter(spy)
    check("typing in a titled note pops up no other window", not spy.popups, spy.popups[:5])
    check("the text was typed", "hello world" in win.editor.toPlainText())
    cards = [c.list_window.list.itemWidget(c.list_window.list.item(i)) for i in range(c.list_window.list.count())]
    check("card title label lives inside its card", all(cd.lbl_title.parent() is cd for cd in cards) and
          all(not cd.lbl_title.isWindow() for cd in cards))
finally:
    shutil.rmtree(TMP, ignore_errors=True)

print("\nRESULT: {0}/{1} passed".format(sum(R), len(R)))
sys.exit(0 if all(R) else 1)
