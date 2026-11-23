# -*- coding: utf-8 -*-
# JUN_Memo v01.07 시험 (오프스크린 PySide6)   python tests/test_scope_colors.py
# Shared / This PC 가 노트마다 다른 색: 노트 위쪽 배지 · 목록 카드 배지 + 왼쪽 띠 (Shared 파랑, This PC 초록) ·
# 범위를 바꾸면 색도 바뀜 · 노트 7색 · 차콜에서 배지 픽셀이 범위 색 · Push Shared 버튼 테두리가 보임
import os
import shutil
import sys
import tempfile

os.environ["QT_QPA_PLATFORM"] = "offscreen"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
TMP = tempfile.mkdtemp(prefix="jun_memo_scopecol_")
os.environ["JUN_MEMO_SHARED"] = os.path.join(TMP, "shared")

from PySide6.QtGui import QColor   # noqa: E402
from PySide6.QtWidgets import QApplication   # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)

from app.core import store as st   # noqa: E402
from app.ui import controller as ctl   # noqa: E402

R = []


def check(name, cond, extra=""):
    R.append(bool(cond))
    print(("PASS " if cond else "FAIL ") + name + ("  | " + str(extra) if extra != "" else ""))


def close(a, b, tol=30):
    a, b = QColor(a), QColor(b)
    return abs(a.red() - b.red()) + abs(a.green() - b.green()) + abs(a.blue() - b.blue()) <= tol


def badge_pixel(label):
    img = label.grab().toImage()
    return img.pixelColor(2, img.height() // 2).name()


try:
    blue, green = st.SCOPE_COLORS["shared"], st.SCOPE_COLORS["local"]
    check("two different scope colors (Shared blue, This PC green)", blue != green and
          st.SCOPE_TEXT == {"shared": "Shared", "local": "This PC"})
    c = ctl.Controller(st.NoteStore(os.path.join(TMP, "local")))
    c.quiet = True
    c.start()
    app.processEvents()
    ok_all = True
    for color in list(st.COLORS) + ["#204060"]:
        for scope, want in (("shared", blue), ("local", green)):
            nid = c.new_note(color=color, scope=scope)
            w = c.windows[nid]
            app.processEvents()
            px = badge_pixel(w.lbl_scope)
            if not (w.lbl_scope.text() == st.SCOPE_TEXT[scope] and close(px, want)):
                ok_all = False
                print("   ", color, scope, px)
            w.close_quietly()
            c.delete_note(nid)
    check("note header badge is filled with the scope color on every note color (7 + custom)", ok_all)
    nid = c.new_note(scope="local")
    w = c.windows[nid]
    w.editor.setPlainText("switch me")
    w.act_shared.trigger()
    app.processEvents()
    check("turning Shared on recolors the badge (green -> blue)", w.lbl_scope.text() == "Shared" and
          close(badge_pixel(w.lbl_scope), blue))
    w.act_shared.trigger()
    app.processEvents()
    check("... and back (blue -> green)", w.lbl_scope.text() == "This PC" and close(badge_pixel(w.lbl_scope), green))
    c.set_color(nid, "Charcoal")
    app.processEvents()
    check("changing the note color keeps the scope color", close(badge_pixel(w.lbl_scope), green))
    s_id = c.new_note(scope="shared")
    c.windows[s_id].editor.setPlainText("shared one")
    c.save_now()
    lw = c.list_window
    lw.refresh()
    app.processEvents()
    cards = {lw.list.item(i).data(0x0100): lw.list.itemWidget(lw.list.item(i)) for i in range(lw.list.count())}
    check("list cards: badge text and color per scope",
          cards[s_id].lbl_scope.text() == "Shared" and "background: {0}".format(blue) in cards[s_id].styleSheet() and
          cards[nid].lbl_scope.text() == "This PC" and "background: {0}".format(green) in cards[nid].styleSheet())
    check("list cards: a left stripe in the scope color", "border-left: 5px solid {0}".format(blue) in cards[s_id].styleSheet()
          and "border-left: 5px solid {0}".format(green) in cards[nid].styleSheet())
    lw.show()
    lw.resize(380, 500)
    app.processEvents()
    img = cards[s_id].grab().toImage()
    check("list card: the stripe really paints blue (pixel)", close(img.pixelColor(1, img.height() // 2).name(), blue),
          img.pixelColor(1, img.height() // 2).name())
    # Push Shared 버튼이 배경과 구분된다 (테두리)
    bimg = lw.btn_push.grab().toImage()
    edge = bimg.pixelColor(0, bimg.height() // 2)
    bg = QColor(st.palette(lw.color)["body"])
    diff = abs(edge.red() - bg.red()) + abs(edge.green() - bg.green()) + abs(edge.blue() - bg.blue())
    check("Push Shared button shows its border (it was plain text)", diff > 60 and
          "QToolButton#pushShared {" in lw.styleSheet(), (edge.name(), bg.name()))
    for win in list(c.windows.values()):
        win.close_quietly()
    lw.close()
    app.processEvents()
finally:
    shutil.rmtree(TMP, ignore_errors=True)

print("\nRESULT: {0}/{1} passed".format(sum(R), len(R)))
sys.exit(0 if all(R) else 1)
