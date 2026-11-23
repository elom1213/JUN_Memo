# -*- coding: utf-8 -*-
# JUN_Memo v01.01 시험 (오프스크린 PySide6)   python tests/test_scope_list.py
# 1. 공유(GitHub) / 이 PC 저장: 위치 · 공유 파일은 내용만 · 창을 옮겨도 공유 파일 불변 · 범위 옮기기 · 지우기 · v01.00 파일 이어 읽기 ·
#    다시 읽기(다른 PC 가 올린 것) · 범위 필터
# 2. 목록 창: 색(모든 부분 - 다크 모드 흰 글자 문제) · Pin · 범위 필터 · 카드 범위 표시 · 다시 켜면 색 · 핀 · 자리 그대로
# 3. 노트 창: 범위 표시 · Shared 켜고 끄기 = 파일 옮김 · 노트의 + 는 같은 범위
# 4. 시작 메뉴: 바로가기 대상 · 아이콘 · 임시 경로에 실제로 만들어 앱 ID 확인(사용자 시작 메뉴는 건드리지 않음) · 화면 흐름(가짜 셸)
import json
import os
import shutil
import sys
import tempfile
import time

os.environ["QT_QPA_PLATFORM"] = "offscreen"
SHARED = tempfile.mkdtemp(prefix="jun_memo_shared_")
os.environ["JUN_MEMO_SHARED"] = SHARED
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from PySide6.QtCore import QPoint, Qt   # noqa: E402
from PySide6.QtWidgets import QApplication   # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)

from app.config.version import APP_USER_MODEL_ID   # noqa: E402
from app.core import shell_integration as shell   # noqa: E402
from app.core import store as st   # noqa: E402
from app.ui import controller as ctl   # noqa: E402

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


def shared_files():
    return sorted(f for f in os.listdir(SHARED) if f.endswith(".json")) if os.path.isdir(SHARED) else []


tmp = tempfile.mkdtemp(prefix="jun_memo_v0101_")
try:
    # ================================================================== 1. 저장
    local = os.path.join(tmp, "pc1")
    s = st.NoteStore(local)
    a = s.new_note()
    b = s.new_note(scope=st.SCOPE_SHARED, color="Blue")
    s.set_content(a["id"], "<p>a</p>", "local only")
    s.set_content(b["id"], "<p>b</p>", "team note")
    s.update(b["id"], geometry=(10, 10, 300, 300), pinned=True, open=True)
    s.save()
    local_json = json.load(open(os.path.join(local, "notes.json"), encoding="utf-8"))
    check("store: this-PC notes go to notes.json (shared ones do not)",
          [n["id"] for n in local_json["notes"]] == [a["id"]])
    check("store: a shared note = one file in shared/notes", shared_files() == [b["id"] + ".json"])
    sb = json.load(open(os.path.join(SHARED, b["id"] + ".json"), encoding="utf-8"))
    check("store: the shared file has the content only (no window place / pin / open - those differ per PC)",
          sorted(sb) == sorted(st.CONTENT_KEYS) and sb["text"] == "team note" and sb["color"] == "Blue")
    state = json.load(open(os.path.join(local, "state.json"), encoding="utf-8"))
    check("store: window state of both notes is in this PC's state.json",
          state["notes"][b["id"]]["geometry"] == [10, 10, 300, 300] and state["notes"][b["id"]]["pinned"] and
          a["id"] in state["notes"])
    mtime = os.path.getmtime(os.path.join(SHARED, b["id"] + ".json"))
    time.sleep(0.05)
    s.update(b["id"], geometry=(99, 99, 320, 320), pinned=False)
    s.save()
    check("store: moving / pinning a shared note does not touch its shared file (no git noise)",
          os.path.getmtime(os.path.join(SHARED, b["id"] + ".json")) == mtime)
    s2 = st.NoteStore(local)
    check("store: reload = both scopes back with their window state",
          s2.get(a["id"])["scope"] == "local" and s2.get(b["id"])["scope"] == "shared" and
          s2.get(b["id"])["geometry"] == [99, 99, 320, 320] and s2.get(b["id"])["text"] == "team note")
    check("store: scope filter", [n["id"] for n in s2.ordered(scope="shared")] == [b["id"]] and
          [n["id"] for n in s2.ordered(scope="local")] == [a["id"]] and len(s2.ordered()) == 2)
    s2.update(a["id"], scope=st.SCOPE_SHARED)
    s2.update(b["id"], scope=st.SCOPE_LOCAL)
    s2.save()
    check("store: changing the scope moves the note between the two places",
          shared_files() == [a["id"] + ".json"] and
          [n["id"] for n in json.load(open(os.path.join(local, "notes.json"), encoding="utf-8"))["notes"]] == [b["id"]])
    s2.delete(a["id"])
    s2.save()
    check("store: deleting a shared note removes its file", shared_files() == [])
    # 다른 PC 가 git 으로 올린 공유 노트 (파일만 생김)
    other = {"id": "fromPC2", "html": "<p>x</p>", "text": "from the other PC", "color": "Pink",
             "created": time.time(), "modified": time.time()}
    with open(os.path.join(SHARED, "fromPC2.json"), "w", encoding="utf-8") as fh:
        json.dump(other, fh)
    added, changed, removed = s2.reload_shared()
    check("store: reload_shared picks up a note pulled from git", (added, changed, removed) == (1, 0, 0) and
          s2.get("fromPC2")["scope"] == "shared" and s2.get("fromPC2")["text"] == "from the other PC")
    other["text"] = "edited on PC2"
    with open(os.path.join(SHARED, "fromPC2.json"), "w", encoding="utf-8") as fh:
        json.dump(other, fh)
    s2.update("fromPC2", open=True)
    check("store: a shared note open here is not replaced under the user's hands", s2.reload_shared() == (0, 0, 0) and
          s2.get("fromPC2")["text"] == "from the other PC")
    s2.update("fromPC2", open=False)
    check("store: ... once closed it updates", s2.reload_shared() == (0, 1, 0) and s2.get("fromPC2")["text"] == "edited on PC2")
    os.remove(os.path.join(SHARED, "fromPC2.json"))
    check("store: removed on the other PC -> removed here", s2.reload_shared() == (0, 0, 1) and s2.get("fromPC2") is None)
    # v01.00 파일 (보기 상태가 같은 파일에)
    old = os.path.join(tmp, "old")
    os.makedirs(old)
    with open(os.path.join(old, "notes.json"), "w", encoding="utf-8") as fh:
        json.dump({"version": 1, "notes": [{"id": "o1", "html": "", "text": "old note", "color": "Green", "pinned": True,
                                            "open": True, "geometry": [5, 6, 300, 200], "created": 1, "modified": 2}]}, fh)
    so = st.NoteStore(os.path.join(old, "notes.json"))
    n = so.get("o1")
    check("store: a v01.00 notes.json still loads (this PC) with its window state",
          n is not None and n["scope"] == "local" and n["pinned"] and n["geometry"] == [5, 6, 300, 200] and n["open"])
    so.save()
    check("store: ... and is split into notes.json + state.json on save",
          "geometry" not in json.load(open(os.path.join(old, "notes.json"), encoding="utf-8"))["notes"][0] and
          json.load(open(os.path.join(old, "state.json"), encoding="utf-8"))["notes"]["o1"]["pinned"])
    for f in shared_files():
        os.remove(os.path.join(SHARED, f))

    # ================================================================== 2. 목록 창
    cdir = os.path.join(tmp, "app")
    c = ctl.Controller(st.NoteStore(cdir))
    c.quiet = True
    c.start()
    pump()
    lw = c.list_window
    check("list: default color is a light gray with dark text on every part (dark mode white-on-white fixed)",
          lw.color == st.DEFAULT_LIST_COLOR and "#listWindow { background: #F3F2F1" in lw.styleSheet() and
          "#search { background: #FFFFFF; color: #202020" in lw.styleSheet() and
          "#listWindow QLabel, #listWindow QRadioButton { color: #202020" in lw.styleSheet())
    lw.swatches["Charcoal"].click()
    check("list: picking Charcoal paints it dark with white text (the search box too)",
          "#listWindow { background: #696969" in lw.styleSheet() and "color: #FFFFFF" in lw.styleSheet() and
          "#search { background: #4A4A4A; color: #FFFFFF" in lw.styleSheet() and c.store.list_view["color"] == "Charcoal")
    lw.btn_pin.click()
    pump()
    check("list: Pin = on top, light red, saved", bool(lw.windowFlags() & Qt.WindowStaysOnTopHint) and
          lw.btn_pin.text() == "Pinned" and lw.isVisible() and c.store.list_view["pinned"] and
          json.load(open(os.path.join(cdir, "state.json"), encoding="utf-8"))["list"]["pinned"])
    [r for r in lw.scope_buttons.buttons() if r.property("scope") == "shared"][0].click()
    lw.btn_new.click()
    pump()
    sid = [i for i in c.windows][0]
    check("list: + while 'Shared' is picked makes a shared note", c.store.get(sid)["scope"] == "shared" and
          c.windows[sid].lbl_scope.text() == "Shared" and c.windows[sid].act_shared.isChecked())
    c.windows[sid].editor.setPlainText("shared idea")
    c.windows[sid].btn_new.click()
    pump()
    sid2 = [i for i in c.windows if i != sid][0]
    check("note: + on a shared note makes another shared note", c.store.get(sid2)["scope"] == "shared")
    c.windows[sid2].close()
    pump(ctl.SAVE_MS + 300)
    check("note: the shared note is saved into shared/notes", shared_files() == [sid + ".json"])
    card = lw.list.itemWidget(lw.list.item(0))
    check("list: the card shows its scope", card.lbl_scope.text() == "Shared")
    c.windows[sid].act_shared.trigger()                     # 끄기 → 이 PC
    pump()
    check("note: turning Shared off moves it to this PC (file gone, tag 'This PC', list filter hides it)",
          c.store.get(sid)["scope"] == "local" and shared_files() == [] and
          c.windows[sid].lbl_scope.text() == "This PC" and lw.list.count() == 0)
    [r for r in lw.scope_buttons.buttons() if r.property("scope") == "all"][0].click()
    lw.move(150, 160)
    lw.resize(360, 500)
    saved_size = (lw.width(), lw.height())          # 오프스크린 글꼴이 넓으면 최소 폭에 걸린다
    c.shutdown()
    for w in list(c.windows.values()):
        w.close_quietly()
    lw.close()
    pump()
    c2 = ctl.Controller(st.NoteStore(cdir))
    c2.quiet = True
    c2.start()
    pump()
    lw2 = c2.list_window
    check("restart: the list window comes back with its color, pin, place and size",
          lw2.color == "Charcoal" and lw2.pinned and bool(lw2.windowFlags() & Qt.WindowStaysOnTopHint) and
          lw2.pos() == QPoint(150, 160) and (lw2.width(), lw2.height()) == saved_size, (lw2.pos(), lw2.size()))
    c2.set_scope(sid, st.SCOPE_SHARED)
    check("controller: set_scope from the list menu updates the open note", c2.windows[sid].lbl_scope.text() == "Shared"
          and shared_files() == [sid + ".json"])

    # ================================================================== 4. 시작 메뉴
    spec = shell.launch_spec()
    check("shell: shortcut runs pythonw + this launch.py with the app icon",
          spec.target.name.lower() in ("pythonw.exe", "python.exe") and spec.arguments.strip('"').endswith("launch.py") and
          os.path.normcase(str(spec.workdir)) == os.path.normcase(ROOT) and spec.icon.is_file())
    check("shell: Start menu shortcut name", shell.start_menu_shortcut().name == "JUN Memo.lnk" and
          "Start Menu" in str(shell.start_menu_shortcut()))
    if shell.is_supported():
        lnk = os.path.join(tmp, "JUN Memo test.lnk")
        made = shell.create_shortcut(__import__("pathlib").Path(lnk))
        check("shell: a real shortcut (temp path) carries the app ID", os.path.isfile(lnk) and str(made) == lnk)
    calls = []
    real = (shell.add_to_start_menu, shell.pin_shortcut, shell.find_pinned_taskbar_shortcut, shell.set_window_relaunch)
    shell.add_to_start_menu = lambda: calls.append("lnk")
    shell.pin_shortcut = lambda lnk, where: (calls.append(where), "pinned" if where == "start" else "unavailable")[1]
    shell.find_pinned_taskbar_shortcut = lambda: None
    shell.set_window_relaunch = lambda hwnd: calls.append("relaunch") or True
    try:
        c2.messages[:] = []
        lw2.act_start.trigger()
        check("UI: Add to Start Menu = shortcut + pin to Start, then says so",
              calls[:2] == ["lnk", "start"] and "added to the Start menu" in c2.messages[-1] and
              "also pinned to Start" in c2.messages[-1])
        calls[:] = []
        lw2.act_taskbar.trigger()
        check("UI: Pin to Taskbar = shortcut, try the verb, then the one-click steps (Windows blocks self-pinning)",
              calls == ["lnk", "taskbar", "relaunch"] and "Right-click the JUN Memo button" in c2.messages[-1])
    finally:
        shell.add_to_start_menu, shell.pin_shortcut, shell.find_pinned_taskbar_shortcut, shell.set_window_relaunch = real
    for w in list(c2.windows.values()):
        w.close_quietly()
    lw2.close()
    pump()
finally:
    shutil.rmtree(tmp, ignore_errors=True)
    shutil.rmtree(SHARED, ignore_errors=True)

print("\nRESULT: {0}/{1} passed".format(sum(R), len(R)))
sys.exit(0 if all(R) else 1)
