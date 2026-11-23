# -*- coding: utf-8 -*-
# JUN_Memo v01.08 시험   python tests/test_default_color.py
# 새 노트의 기본 색 = 저장된 노트 색 (마지막으로 고른 색 · state.json 에 기억 · 옛 파일이면 가장 최근 노트 색)
import json
import os
import shutil
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from app.core import store as st   # noqa: E402

R = []


def check(name, cond, extra=""):
    R.append(bool(cond))
    print(("PASS " if cond else "FAIL ") + name + ("  | " + str(extra) if extra != "" else ""))


tmp = tempfile.mkdtemp(prefix="jun_memo_defcol_")
try:
    local, shared = os.path.join(tmp, "local"), os.path.join(tmp, "shared")
    s = st.NoteStore(local, shared)
    check("no notes yet = yellow", s.new_note()["color"] == st.DEFAULT_COLOR)
    s.notes.clear()

    a = s.new_note()
    s.update(a["id"], color="#474747")
    s.set_content(a["id"], "<p>a</p>", "a")
    check("after picking a colour, a new note has it", s.new_note()["color"] == "#474747")
    check("a new shared note too", s.new_note(scope=st.SCOPE_SHARED)["color"] == "#474747")
    check("an explicit colour still wins", s.new_note(color="Blue")["color"] == "Blue")
    for i in [i for i in s.notes if i != a["id"]]:
        s.delete(i)
    s.save()

    s2 = st.NoteStore(local, shared)
    check("remembered after restart (state.json)", s2.note_color == "#474747" and s2.new_note()["color"] == "#474747")

    s2.update(a["id"], color="Green")
    s2.save()
    check("changing the colour again changes the default", st.NoteStore(local, shared).new_note()["color"] == "Green")

    # 옛 state.json (note_color 없음) - 가장 최근에 고친 노트 색
    s3 = st.NoteStore(local, shared)
    b = s3.new_note(color="Pink")
    time.sleep(0.02)
    s3.set_content(b["id"], "<p>b</p>", "b")
    s3.save()
    with open(s3.state_path, encoding="utf-8") as fh:
        data = json.load(fh)
    data.pop("note_color", None)
    with open(s3.state_path, "w", encoding="utf-8") as fh:
        json.dump(data, fh)
    check("old state file = colour of the latest edited note", st.NoteStore(local, shared).new_note()["color"] == "Pink")

    data["note_color"] = "not-a-colour"
    with open(s3.state_path, "w", encoding="utf-8") as fh:
        json.dump(data, fh)
    check("bad saved colour is ignored", st.NoteStore(local, shared).new_note()["color"] == "Pink")
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print("\nRESULT: {0}/{1} passed".format(sum(R), len(R)))
sys.exit(0 if all(R) else 1)
