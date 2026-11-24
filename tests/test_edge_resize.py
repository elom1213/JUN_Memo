# -*- coding: utf-8 -*-
# JUN_Memo v01.12 시험 (오프스크린 PySide6)   python tests/test_edge_resize.py
# 노트 크기를 오른쪽 아래 손잡이뿐 아니라 일반 창처럼 네 변 · 네 모서리 어디서든 끌어 조절
import os
import shutil
import sys
import tempfile
import time

os.environ["QT_QPA_PLATFORM"] = "offscreen"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
TMP = tempfile.mkdtemp(prefix="jun_memo_edge_")
os.environ["JUN_MEMO_SHARED"] = os.path.join(TMP, "shared")
os.environ["APPDATA"] = os.path.join(TMP, "appdata")

from PySide6.QtCore import QPoint, QRect, QSize, Qt   # noqa: E402
from PySide6.QtTest import QTest   # noqa: E402
from PySide6.QtWidgets import QApplication   # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)

from app.core import store as st   # noqa: E402
from app.ui import controller as ctl   # noqa: E402
from app.ui import note_window as nw   # noqa: E402

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


def name(edges):
    return "+".join(n for n, f in (("top", Qt.TopEdge), ("bottom", Qt.BottomEdge), ("left", Qt.LeftEdge),
                                   ("right", Qt.RightEdge)) if edges & f)


try:
    # ---- 계산 (잡은 변만 움직이고, 최소 크기에서 멈춘다)
    r = QRect(100, 100, 300, 300)
    mn = QSize(200, 140)
    check("left edge drag moves left side only", nw.resized_rect(r, Qt.LeftEdge, QPoint(-40, 99), mn) == QRect(60, 100, 340, 300))
    check("top edge drag moves top side only", nw.resized_rect(r, Qt.TopEdge, QPoint(99, 30), mn) == QRect(100, 130, 300, 270))
    check("top-left corner moves both", nw.resized_rect(r, Qt.TopEdge | Qt.LeftEdge, QPoint(10, 20), mn) == QRect(110, 120, 290, 280))
    check("left edge stops at minimum width (right side stays)",
          nw.resized_rect(r, Qt.LeftEdge, QPoint(500, 0), mn) == QRect(200, 100, 200, 300))
    check("bottom edge stops at minimum height",
          nw.resized_rect(r, Qt.BottomEdge, QPoint(0, -500), mn) == QRect(100, 100, 300, 140))

    # ---- 실제 노트 창
    c = ctl.Controller(st.NoteStore(os.path.join(TMP, "local"), os.path.join(TMP, "shared")))
    nid = c.new_note()
    win = c.windows[nid]
    win.setGeometry(300, 300, 320, 300)
    pump()
    check("8 edge handles (4 sides + 4 corners)", len(win.edge_handles) == 8)
    win_rect = win.rect()
    for h in win.edge_handles:
        g = h.geometry()
        e = h.edges
        on_edge = ((not e & Qt.LeftEdge or g.left() == 0) and (not e & Qt.TopEdge or g.top() == 0) and
                   (not e & Qt.RightEdge or g.right() == win_rect.right()) and
                   (not e & Qt.BottomEdge or g.bottom() == win_rect.bottom()))
        top = win.childAt(g.center()) is h
        check("{0} handle sits on the window edge, above other widgets".format(name(e)), on_edge and top, g)
    check("header buttons still clickable (not covered)", win.childAt(win.btn_close.geometry().center()
                                                                      + win.header.pos()) is win.btn_close)

    expected = {
        Qt.TopEdge: lambda g: g.top() == 270 and g.bottom() == 599 and g.left() == 300 and g.width() == 320,
        Qt.BottomEdge: lambda g: g.top() == 300 and g.height() == 330 and g.width() == 320,
        Qt.LeftEdge: lambda g: g.left() == 270 and g.right() == 619 and g.height() == 300,
        Qt.RightEdge: lambda g: g.left() == 300 and g.width() == 350 and g.height() == 300,
        Qt.TopEdge | Qt.LeftEdge: lambda g: g.topLeft() == QPoint(270, 270) and g.bottomRight() == QPoint(619, 599),
        Qt.BottomEdge | Qt.RightEdge: lambda g: g.topLeft() == QPoint(300, 300) and g.size() == QSize(350, 330),
        Qt.TopEdge | Qt.RightEdge: lambda g: g.top() == 270 and g.left() == 300 and g.width() == 350,
        Qt.BottomEdge | Qt.LeftEdge: lambda g: g.left() == 270 and g.top() == 300 and g.height() == 330,
    }
    for h in list(win.edge_handles):
        win.setGeometry(300, 300, 320, 300)
        pump()
        e = h.edges
        d = QPoint(-30 if e & Qt.LeftEdge else (30 if e & Qt.RightEdge else 0),
                   -30 if e & Qt.TopEdge else (30 if e & Qt.BottomEdge else 0))
        p = h.rect().center()
        QTest.mousePress(h, Qt.LeftButton, Qt.NoModifier, p)
        QTest.mouseMove(h, p + d)
        QTest.mouseRelease(h, Qt.LeftButton, Qt.NoModifier, p + d)
        pump()
        g = win.geometry()
        check("dragging the {0} handle outward resizes from that side".format(name(e)), expected[e](g), g)

    # 줄이기 - 최소 크기 아래로 안 내려간다
    win.setGeometry(300, 300, 320, 300)
    pump()
    h = [x for x in win.edge_handles if x.edges == Qt.LeftEdge][0]
    p = h.rect().center()
    QTest.mousePress(h, Qt.LeftButton, Qt.NoModifier, p)
    QTest.mouseMove(h, p + QPoint(400, 0))
    QTest.mouseRelease(h, Qt.LeftButton, Qt.NoModifier, p + QPoint(400, 0))
    pump()
    g = win.geometry()
    check("left drag inward stops at minimum width, right side stays", g.width() == nw.MIN_SIZE.width() and g.right() == 619, g)
    check("handles follow the new size", [x for x in win.edge_handles if x.edges == Qt.RightEdge][0].geometry().right()
          == win.width() - 1)

    win.close()
    pump()
finally:
    shutil.rmtree(TMP, ignore_errors=True)

print("\nRESULT: {0}/{1} passed".format(sum(R), len(R)))
sys.exit(0 if all(R) else 1)
