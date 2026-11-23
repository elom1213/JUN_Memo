# -*- coding: utf-8 -*-
# JUN_Memo v01.08 시험 (오프스크린 PySide6)   python tests/test_reorder.py
# 목록 카드 끌어 놓기로 순서 바꾸기: 저장소 순서 · 검색 / 범위로 일부만 보일 때 · 새 노트는 맨 위 · 다시 켜도 유지 ·
# 목록 창에서 칸을 옮기면(끌어 놓기와 같은 모델 이동) 저장되고 카드가 다시 그려진다
import os
import shutil
import sys
import tempfile
import time

os.environ["QT_QPA_PLATFORM"] = "offscreen"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
TMP = tempfile.mkdtemp(prefix="jun_memo_reorder_")
os.environ["JUN_MEMO_SHARED"] = os.path.join(TMP, "shared")

from PySide6.QtCore import QModelIndex   # noqa: E402
from PySide6.QtWidgets import QAbstractItemView, QApplication   # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)

from app.core import store as st   # noqa: E402
from app.ui import list_window as lwm   # noqa: E402

R = []


def check(name, cond, extra=""):
    R.append(bool(cond))
    print(("PASS " if cond else "FAIL ") + name + ("  | " + str(extra) if extra != "" else ""))


def pump(n=5):
    for _ in range(n):
        app.processEvents()
        time.sleep(0.01)


def ids(notes):
    return [n["id"] for n in notes]


try:
    local, shared = os.path.join(TMP, "local"), os.path.join(TMP, "shared")
    s = st.NoteStore(local, shared)
    made = []
    for i, scope in enumerate((st.SCOPE_LOCAL, st.SCOPE_SHARED, st.SCOPE_LOCAL, st.SCOPE_SHARED)):
        n = s.new_note(scope=scope)
        time.sleep(0.01)
        s.set_content(n["id"], "<p>{0}</p>".format(i), "note {0}{1}".format(i, " apple" if i % 2 else ""))
        made.append(n["id"])
    a, b, c, d = made                                       # 최근 = d, c, b, a
    check("no order yet = latest edit first", ids(s.ordered()) == [d, c, b, a])

    check("set_order changes the order", s.set_order([a, b, c, d]) and ids(s.ordered()) == [a, b, c, d])
    check("same order again = no change", not s.set_order([a, b, c, d]))
    time.sleep(0.01)
    s.set_content(c, "<p>x</p>", "note 2 edited")
    check("editing a note keeps the dragged order", ids(s.ordered()) == [a, b, c, d])

    # 걸러 보일 때 (shared 만: b, d) - d 를 위로 → 보이던 자리(2, 4번째)에 d, b
    check("reorder while filtered keeps hidden notes in place",
          s.set_order([d, b]) and ids(s.ordered()) == [a, d, c, b], ids(s.ordered()))
    check("filtered view follows the order", ids(s.ordered(scope=st.SCOPE_SHARED)) == [d, b] and
          ids(s.ordered("apple")) == [d, b])

    e = s.new_note()
    s.set_content(e["id"], "<p>e</p>", "new one")
    check("a new note shows at the top", ids(s.ordered())[0] == e["id"])
    s.delete(a)
    s.save()
    s2 = st.NoteStore(local, shared)
    check("order kept after restart (deleted note dropped)", ids(s2.ordered()) == [e["id"], d, c, b] and a not in s2.order,
          ids(s2.ordered()))

    # ---- 목록 창
    lw = lwm.ListWindow(s2)
    saved = []
    lw.viewChanged.connect(lambda: saved.append(1))
    lw.show()
    pump()
    check("list: drag and drop is on (move inside the list)",
          lw.list.dragDropMode() == QAbstractItemView.InternalMove)
    before = lw.item_ids()
    # 맨 아래 카드(b)를 맨 위로 - 끌어 놓기와 같은 모델 이동
    ok = lw.list.model().moveRows(QModelIndex(), len(before) - 1, 1, QModelIndex(), 0)
    pump()
    after = lw.item_ids()
    check("list: moving a card changes the list", ok and after == [before[-1]] + before[:-1], after)
    check("list: the new order is in the store and saved", ids(s2.ordered()) == after and saved)
    check("list: every card is drawn after the move",
          all(lw.list.itemWidget(lw.list.item(i)) is not None for i in range(lw.list.count())))
    s2.save()
    check("list: order kept after restart", ids(st.NoteStore(local, shared).ordered()) == after)
    lw.close()
finally:
    shutil.rmtree(TMP, ignore_errors=True)

print("\nRESULT: {0}/{1} passed".format(sum(R), len(R)))
sys.exit(0 if all(R) else 1)
