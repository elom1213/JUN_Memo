# -*- coding: utf-8 -*-
# JUN_Memo 시험 (오프스크린 PySide6)   python tests/test_memo.py
# 1. 저장소: 새 노트 · 내용 · 색 · 핀 · 위치 · 순서 · 검색 · 저장 / 다시 읽기 · 깨진 파일 → 백업 · 사용자 색 팔레트
# 2. 노트 창: 색 = 스타일 · Pin = 맨 위 플래그 · 서식(굵게 · 글머리표) · 붙여 넣기는 글자만 · 빈 노트 내용
# 3. 컨트롤러: 새 노트 → 입력 → 자동 저장 · 닫으면 목록에 남음 · 빈 노트는 닫을 때 지움 · 목록 클릭 = 열기 · 삭제 ·
#    다시 켜면 열려 있던 노트가 그 자리 · 색 · 핀으로 · 화면 밖 자리는 주 화면으로 · 목록 검색
# 4. 한 번만 실행: 두 번째 실행은 첫 앱의 목록 창을 앞으로 부르고 끝난다
import os
import shutil
import sys
import tempfile
import time

os.environ["QT_QPA_PLATFORM"] = "offscreen"
# 공유 노트 폴더는 시험 동안 임시 폴더로 (저장소의 shared/notes 를 건드리지 않게)
SHARED_TMP = tempfile.mkdtemp(prefix="jun_memo_shared_")
os.environ["JUN_MEMO_SHARED"] = SHARED_TMP
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from PySide6.QtCore import QMimeData, QPoint, Qt   # noqa: E402
from PySide6.QtGui import QFont, QGuiApplication   # noqa: E402
from PySide6.QtWidgets import QApplication   # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)

from app.core import store as st   # noqa: E402
from app.ui import controller as ctl   # noqa: E402
from app.ui.note_window import NoteWindow, PIN_ON   # noqa: E402

R = []


def check(name, cond, extra=""):
    R.append(bool(cond))
    print(("PASS " if cond else "FAIL ") + name + ("  | " + str(extra) if extra != "" else ""))


def pump(ms=0):
    end = time.time() + ms / 1000.0
    while True:
        app.processEvents()
        if time.time() >= end:
            break
        time.sleep(0.01)


tmp = tempfile.mkdtemp(prefix="jun_memo_")
try:
    # ================================================================== 1. 저장소
    path = os.path.join(tmp, "a", "notes.json")
    s = st.NoteStore(path)
    check("store: a missing file = no notes, no error", s.notes == {} and not s.error)
    n1 = s.new_note()
    check("store: new note is yellow, open, not pinned", n1["color"] == "Yellow" and n1["open"] and not n1["pinned"])
    time.sleep(0.01)
    n2 = s.new_note(color="Blue")
    check("store: picking a colour makes it the new-note default", s.update(n2["id"], color="#474747") and
          s.new_note()["color"] == "#474747")
    s.delete([i for i in s.notes if i not in (n1["id"], n2["id"])][0])
    s.update(n2["id"], color="Blue")
    check("store: set_content changes and bumps modified only when different",
          s.set_content(n1["id"], "<p>hi</p>", "Buy milk\nand eggs") and not s.set_content(n1["id"], "<p>hi</p>", "Buy milk\nand eggs"))
    time.sleep(0.02)                                        # 수정 시각이 같은 밀리초가 되지 않게
    s.set_content(n2["id"], "<p>x</p>", "Meeting at 3")
    check("store: newest edit first", [n["id"] for n in s.ordered()][0] == n2["id"])
    check("store: search = every word, any case", [n["id"] for n in s.ordered("MILK eggs")] == [n1["id"]] and
          s.ordered("milk meeting") == [])
    check("store: update colour / pin / geometry does not change the order time",
          s.update(n1["id"], color="Pink", pinned=True, geometry=(10, 20, 300, 200)) and
          s.ordered()[0]["id"] == n2["id"])
    try:
        s.update(n1["id"], html="x")
        check("store: update refuses content fields", False)
    except KeyError:
        check("store: update refuses content fields", True)
    check("store: save creates the folder and writes", s.save() and os.path.isfile(path))
    s2 = st.NoteStore(path)
    a = s2.get(n1["id"])
    check("store: reload keeps everything", a["color"] == "Pink" and a["pinned"] and a["geometry"] == [10, 20, 300, 200] and
          a["text"] == "Buy milk\nand eggs" and len(s2.notes) == 2)
    s2.save()                                               # 이제 .bak 이 생긴다
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("{ broken")
    s3 = st.NoteStore(path)
    check("store: a broken file falls back to the backup and says so", len(s3.notes) == 2 and "backup" in s3.error, s3.error)
    check("store: delete / is_empty", s3.delete(n2["id"]) and not s3.delete(n2["id"]) and not s3.is_empty(n1["id"]))
    check("store: palette - named colours are the Sticky Notes ones",
          st.palette("Yellow")["body"] == "#FFF7D1" and st.palette("Charcoal")["text"] == "#FFFFFF")
    pal = st.palette("#204060")
    check("store: palette - a dark custom colour gets white text and a darker header",
          pal["text"] == "#FFFFFF" and pal["header"] != pal["body"] and st.palette("#F0F0A0")["text"] == "#202020")
    check("store: unknown colour -> yellow", st.palette("nope")["body"] == "#FFF7D1")
    check("store: preview = first lines, skips blanks", st.preview("\n\nA\n\nB\nC\nD") == "A\nB\nC")

    # ================================================================== 2. 노트 창
    note = {"id": "x1", "html": "", "text": "hello", "color": "Green", "pinned": False, "open": True,
            "geometry": [100, 120, 300, 260], "created": 0, "modified": 0}
    w = NoteWindow(note)
    w.show()
    pump()
    check("note: frameless window at the saved place and size", bool(w.windowFlags() & Qt.FramelessWindowHint) and
          w.geometry().width() == 300 and w.geometry().height() == 260 and w.pos().x() == 100, w.geometry())
    check("note: body colour = Sticky Notes green", "#E4F9E0" in w.styleSheet() and w.editor.toPlainText() == "hello")
    seen = []
    w.colorChanged.connect(lambda i, c: seen.append(c))
    w.swatches["Purple"].click()
    check("note: a colour swatch recolours the note and reports it", "#F2E6FF" in w.styleSheet() and seen == ["Purple"])
    pins = []
    w.pinChanged.connect(lambda i, on: pins.append(on))
    w.btn_pin.click()
    pump()
    check("note: Pin = stays on top, button shows Pinned (light red when checked), still visible",
          bool(w.windowFlags() & Qt.WindowStaysOnTopHint) and w.btn_pin.isChecked() and w.btn_pin.text() == "Pinned" and
          w.isVisible() and PIN_ON in w.styleSheet() and pins == [True])
    w.btn_pin.click()
    pump()
    check("note: Pin off", not (w.windowFlags() & Qt.WindowStaysOnTopHint) and pins == [True, False] and w.isVisible())
    w.editor.selectAll()
    w.apply_format("bold")
    check("note: bold", w.editor.textCursor().charFormat().fontWeight() >= QFont.Bold)
    w.apply_format("bullet")
    check("note: bullets on, then off", w.editor.textCursor().currentList() is not None)
    w.apply_format("bullet")
    check("note: bullets off", w.editor.textCursor().currentList() is None)
    w.editor.clear()
    md = QMimeData()
    md.setHtml("<span style='background:red;font-size:40pt'>pasted</span>")
    md.setText("pasted")
    w.editor.insertFromMimeData(md)
    check("note: paste keeps the text only (no foreign background / size)", w.editor.toPlainText() == "pasted" and
          "background" not in w.editor.toHtml() and "40pt" not in w.editor.toHtml())
    w.editor.clear()
    check("note: empty note -> empty html", w.content() == ("", ""))
    w.close_quietly()
    pump()

    # ================================================================== 3. 컨트롤러
    cpath = os.path.join(tmp, "c", "notes.json")
    c = ctl.Controller(st.NoteStore(cpath))
    c.start()
    pump()
    check("app: the notes list shows (no notes yet)", c.list_window.isVisible() and c.list_window.list.count() == 0 and
          "No notes yet" in c.list_window.lbl_count.text())
    c.list_window.btn_new.click()
    pump()
    nid = list(c.windows)[0]
    nw = c.windows[nid]
    check("app: + makes a yellow sticky note window, saved at once", nw.isVisible() and nw.color == "Yellow" and
          os.path.isfile(cpath))
    nw.editor.setPlainText("Call Mom\nabout Sunday")
    check("app: typing saves a moment later (not on every key)", st.NoteStore(cpath).get(nid)["text"] == "")
    # 저장 타이머(SAVE_MS) 뒤를 기다린다 - 고정 시간만 기다리면 처음 실행(컴파일 등)에 느려 흔들렸다 → 저장될 때까지 최대 3초
    waited = 0
    while waited < 3000 and st.NoteStore(cpath).get(nid)["text"] != "Call Mom\nabout Sunday":
        pump(100)
        waited += 100
    check("app: ... saved (after the save delay, not before it)", st.NoteStore(cpath).get(nid)["text"] ==
          "Call Mom\nabout Sunday" and waited >= ctl.SAVE_MS - 100, waited)
    check("app: the list shows the note's first lines", c.list_window.list.count() == 1 and
          "Call Mom" in c.list_window.list.itemWidget(c.list_window.list.item(0)).lbl_text.text())
    nw.btn_new.click()
    pump()
    other = [i for i in c.windows if i != nid][0]
    check("app: + on a note opens a new one next to it", c.windows[other].pos() == nw.pos() + QPoint(30, 30) or
          abs(c.windows[other].pos().x() - nw.pos().x() - 30) <= 2)
    c.windows[other].close()
    pump()
    check("app: closing an empty note deletes it", c.store.get(other) is None and other not in c.windows)
    nw.move(240, 180)
    nw.resize(360, 300)
    nw.swatches["Blue"].click()
    nw.btn_pin.click()
    pump(400)
    nw.close()
    pump()
    saved = st.NoteStore(cpath).get(nid)
    check("app: closing keeps the note in the list (closed), with colour, pin, place and size",
          saved is not None and not saved["open"] and saved["color"] == "Blue" and saved["pinned"] and
          saved["geometry"] == [240, 180, 360, 300] and nid not in c.windows, saved)
    c.list_window._on_clicked(c.list_window.list.item(0))
    pump()
    again = c.windows.get(nid)
    check("app: clicking the note in the list opens it as it was", again is not None and again.isVisible() and
          again.editor.toPlainText() == "Call Mom\nabout Sunday" and again.color == "Blue" and again.pinned and
          again.geometry().topLeft() == QPoint(240, 180))
    c.list_window._on_clicked(c.list_window.list.item(0))
    pump()
    check("app: clicking it again does not open a second window", len([1 for i in c.windows if i == nid]) == 1 and
          len(QApplication.topLevelWidgets()) >= 2)
    c.list_window.ipf_search.setText("sunday")
    check("app: list search", c.list_window.list.count() == 1 and "1 of 1" in c.list_window.lbl_count.text())
    c.list_window.ipf_search.setText("zzz")
    check("app: list search with no hit", c.list_window.list.count() == 0)
    c.list_window.ipf_search.clear()
    c.set_color(nid, "Charcoal")
    check("app: colour from the list menu recolours the open note too", again.color == "Charcoal" and "#696969" in again.styleSheet())
    c.shutdown()                                            # 앱을 끈다 (열린 노트 그대로 - open=True)
    for win in list(c.windows.values()):
        win.close_quietly()
    c.list_window.close()
    pump()

    c2 = ctl.Controller(st.NoteStore(cpath))
    c2.start()
    pump()
    back = c2.windows.get(nid)
    check("restart: the note that was open opens again at its place, colour and pin",
          back is not None and back.isVisible() and back.color == "Charcoal" and back.pinned and
          back.geometry().topLeft() == QPoint(240, 180) and bool(back.windowFlags() & Qt.WindowStaysOnTopHint))
    # 화면 밖에 저장된 노트 (모니터를 뺀 경우)
    off = c2.store.new_note(geometry=(50000, 50000, 300, 300))
    c2.store.set_content(off["id"], "<p>far</p>", "far away")
    c2.store.update(off["id"], open=False)
    win_off = c2.open_note(off["id"])
    pump()
    check("off-screen place -> moved onto the main screen",
          QGuiApplication.screenAt(win_off.geometry().center()) is not None, win_off.geometry())
    c2.delete_note(off["id"])
    pump()
    check("delete removes the window and the note", c2.store.get(off["id"]) is None and off["id"] not in c2.windows and
          st.NoteStore(cpath).get(off["id"]) is None)
    for win in list(c2.windows.values()):
        win.close_quietly()
    c2.list_window.close()
    pump()

    # ================================================================== 4. 한 번만 실행
    import launch
    launch.SERVER_NAME = "JUN_Memo_test_" + str(os.getpid())
    c3 = ctl.Controller(st.NoteStore(os.path.join(tmp, "d", "notes.json")))
    server = launch._serve(c3)
    c3.list_window.hide()
    check("single instance: a second launch sees the first one", launch._already_running())
    pump(300)
    check("single instance: ... and brings its notes list to the front", c3.list_window.isVisible())
    server.close()
    check("single instance: nobody running -> start normally", not launch._already_running())
    c3.list_window.close()
    pump()
finally:
    shutil.rmtree(tmp, ignore_errors=True)
    shutil.rmtree(SHARED_TMP, ignore_errors=True)

print("\nRESULT: {0}/{1} passed".format(sum(R), len(R)))
sys.exit(0 if all(R) else 1)
