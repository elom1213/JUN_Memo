# -*- coding: utf-8 -*-
# JUN_Memo v01.04 Shrink 시험 (오프스크린 PySide6)   python tests/test_shrink.py
# 목록 창 Shrink: 272 x 155 · 애니메이션 · Shrunk / Pin 만 남음 · Pin 이 Shrunk 아래로 · 감춘 것 그대로 돌아옴(검색어 · 필터) ·
# 애니메이션 클릭 = 펴기 · 줄여 둔 동안만 타이머 · 다시 켜면 줄인 채로 + 펼 때 원래 크기 · 장면 타임라인(색 차례 · 글씨 · 연필 · 압정)
import os
import shutil
import sys
import tempfile

os.environ["QT_QPA_PLATFORM"] = "offscreen"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
TMP = tempfile.mkdtemp(prefix="jun_memo_shrink_")
os.environ["JUN_MEMO_SHARED"] = os.path.join(TMP, "shared")

from PySide6.QtCore import QPointF, Qt   # noqa: E402
from PySide6.QtGui import QMouseEvent   # noqa: E402
from PySide6.QtCore import QEvent   # noqa: E402
from PySide6.QtWidgets import QApplication   # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)

from app.core import store as st   # noqa: E402
from app.ui import controller as ctl   # noqa: E402
from app.ui import list_window as lwm   # noqa: E402
from app.ui import memo_anim as ma   # noqa: E402

R = []


def check(name, cond, extra=""):
    R.append(bool(cond))
    print(("PASS " if cond else "FAIL ") + name + ("  | " + str(extra) if extra != "" else ""))


def grid_pos(lw, widget):
    i = lw.button_grid.indexOf(widget)
    r, c, _rs, _cs = lw.button_grid.getItemPosition(i)
    return r, c


try:
    local = os.path.join(TMP, "local")
    c = ctl.Controller(st.NoteStore(local))
    c.quiet = True
    c.start()
    app.processEvents()
    lw = c.list_window
    lw.resize(360, 520)
    app.processEvents()
    FULL = (lw.width(), lw.height())        # 실제 크기 (오프스크린 글꼴이 넓으면 최소 폭에 걸린다)
    check("normal: [Shrink][Pin] side by side, no animation", grid_pos(lw, lw.btn_shrink) == (0, 0) and
          grid_pos(lw, lw.btn_pin) == (0, 1) and not lw.anim.isVisible() and not lw.anim.is_running())
    lw.ipf_search.setText("milk")
    [b for b in lw.scope_buttons.buttons() if b.property("scope") == "shared"][0].click()
    lw.btn_shrink.click()
    app.processEvents()
    check("Shrink: window becomes 272 x 155 (same as A00220 / A00240 / A00370)",
          (lw.width(), lw.height()) == (lwm.SHRINK_WIDTH, lwm.SHRINK_HEIGHT), (lw.width(), lw.height()))
    check("Shrink: only the animation, Shrunk and Pin are left",
          lw.anim.isVisible() and lw.btn_shrink.isVisible() and lw.btn_pin.isVisible() and
          not any(w.isVisible() for w in lw._shrink_hidden))
    check("Shrink: Pin moves under Shrunk, the button reads Shrunk (checked)",
          grid_pos(lw, lw.btn_pin) == (1, 0) and lw.btn_shrink.text() == "Shrunk" and lw.btn_shrink.isChecked())
    check("Shrink: the animation loops (timer running)", lw.anim.is_running())
    check("Shrink: state saved", c.store.list_view["shrunk"])
    check("while shrunk the saved size is the full one (so it opens big again)",
          lw.geometry_list()[2:] == list(FULL), (lw.geometry_list(), FULL))
    lw.btn_pin.click()
    app.processEvents()
    check("Pin works while shrunk (stays on top, still shrunk)", lw.pinned and lw.shrunk and
          bool(lw.windowFlags() & Qt.WindowStaysOnTopHint) and (lw.width(), lw.height()) == (272, 155))
    lw.btn_pin.click()
    ev = QMouseEvent(QEvent.MouseButtonPress, QPointF(20, 20), QPointF(20, 20), Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
    QApplication.sendEvent(lw.anim, ev)
    app.processEvents()
    check("clicking the animation opens it again", not lw.shrunk and not lw.btn_shrink.isChecked())
    check("open again: same size as before, everything back, animation stopped",
          (lw.width(), lw.height()) == FULL and all(w.isVisible() for w in lw._shrink_hidden) and
          not lw.anim.isVisible() and not lw.anim.is_running() and grid_pos(lw, lw.btn_pin) == (0, 1))
    check("open again: search text and filter are kept", lw.ipf_search.text() == "milk" and lw.scope_filter == "shared")
    for _ in range(3):                                       # 여러 번 왕복해도 크기가 흐르지 않는다
        lw.set_shrunk(True)
        lw.set_shrunk(False)
    app.processEvents()
    check("repeat shrink / open keeps the size", (lw.width(), lw.height()) == FULL)

    # 줄인 채 끄면 줄인 채로 켜진다 - 펼 때 원래 크기
    lw.set_shrunk(True)
    c.shutdown()
    lw.close()
    app.processEvents()
    c2 = ctl.Controller(st.NoteStore(local))
    c2.quiet = True
    c2.start()
    app.processEvents()
    lw2 = c2.list_window
    check("restart: comes back shrunk with the animation running", lw2.shrunk and lw2.anim.is_running() and
          (lw2.width(), lw2.height()) == (272, 155))
    lw2.set_shrunk(False)
    app.processEvents()
    check("restart: opening gives the full size", (lw2.width(), lw2.height()) == FULL, ((lw2.width(), lw2.height()), FULL))
    lw2.close()

    # ---- 장면 타임라인
    a = ma.MemoAnim()
    cycle0, t0 = a.frame(ma.PERIOD_MS * 0.5)
    cycle1, _t = a.frame(ma.PERIOD_MS * 1.5)
    check("scene: each loop uses the next Sticky Notes color", a.note_color(cycle0) == "Yellow" and
          a.note_color(cycle1) == "Green" and a.note_color(7) == "Yellow" and abs(t0 - 0.5) < 1e-9)
    check("scene: the three lines are written one after another",
          a.line_progress(0.2, 0) > 0 and a.line_progress(0.2, 1) == 0 and a.line_progress(0.45, 0) == 1 and
          a.line_progress(0.45, 1) > 0 and a.line_progress(0.70, 2) == 1)
    check("scene: no pencil while the note drops or flies away, pencil while writing",
          a.pencil_state(0.05)[0] is False and a.pencil_state(0.9)[0] is False and a.pencil_state(0.3)[0] is True)
    vis, tip = a.pencil_state(0.25)
    check("scene: the pencil tip follows the end of the line being written",
          vis and abs(tip[0] - (a._lines()[0][0] + a._lines()[0][1] * a.line_progress(0.25, 0))) < 1e-6)
    a.resize(150, 118)
    for ms in range(0, ma.PERIOD_MS * 2, 97):                # 모든 장면이 에러 없이 그려진다
        a.elapsed_override = ms
        a.grab()
    check("scene: every moment paints without error", True)
finally:
    shutil.rmtree(TMP, ignore_errors=True)

print("\nRESULT: {0}/{1} passed".format(sum(R), len(R)))
sys.exit(0 if all(R) else 1)
