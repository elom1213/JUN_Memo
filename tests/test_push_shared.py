# -*- coding: utf-8 -*-
# JUN_Memo v01.03 Push Shared 시험 (실제 git, 오프스크린)   python tests/test_push_shared.py
# 임시 "GitHub"(bare 저장소) + PC 두 대(클론 둘)로:
#   공유 노트만 커밋 · 푸시(이 PC 노트 · 고친 다른 파일은 안 올라감) · 바뀐 것 없음 · 다른 PC 가 먼저 올렸으면 받아서 다시 푸시 ·
#   안 올라간 다른 커밋이 있으면 멈춤 · 공유 폴더가 git 밖이면 에러 · 목록 창 버튼 흐름 · 선택 영역 색(v01.03)
import os
import shutil
import subprocess
import sys
import tempfile
import time

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["GIT_TERMINAL_PROMPT"] = "0"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
TMP = tempfile.mkdtemp(prefix="jun_memo_push_")
os.environ["JUN_MEMO_SHARED"] = os.path.join(TMP, "unused_shared")

from PySide6.QtGui import QPalette   # noqa: E402
from PySide6.QtWidgets import QApplication   # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)

from app.core import git_sync   # noqa: E402
from app.core import store as st   # noqa: E402
from app.ui import controller as ctl   # noqa: E402

R = []


def check(name, cond, extra=""):
    R.append(bool(cond))
    print(("PASS " if cond else "FAIL ") + name + ("  | " + str(extra) if extra != "" else ""))


def run(cwd, *args):
    p = subprocess.run(["git"] + list(args), cwd=cwd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError("git {0}: {1}".format(args, p.stderr))
    return p.stdout.strip()


def clone(name):
    path = os.path.join(TMP, name)
    run(TMP, "clone", "-q", REMOTE, path)
    run(path, "config", "user.name", "test")
    run(path, "config", "user.email", "test@example.com")
    return path


def remote_files(ref="main"):
    return run(REMOTE, "ls-tree", "-r", "--name-only", ref).splitlines()


def remote_head():
    return run(REMOTE, "rev-parse", "main")


try:
    # ---- 임시 GitHub + PC1
    REMOTE = os.path.join(TMP, "remote.git")
    run(TMP, "init", "-q", "--bare", "-b", "main", REMOTE)
    pc1 = clone("pc1")
    with open(os.path.join(pc1, "README.md"), "w") as fh:
        fh.write("app\n")
    run(pc1, "add", "README.md")
    run(pc1, "commit", "-q", "-m", "init")
    run(pc1, "push", "-q", "origin", "main")

    # 공유 폴더가 git 밖이면
    outside = os.path.join(TMP, "not_a_repo", "shared", "notes")
    os.makedirs(outside)
    r = git_sync.push_shared(outside)
    check("not in a git repository -> error, nothing done", r.status == "error", r.message)

    shared1 = os.path.join(pc1, "shared", "notes")
    s1 = st.NoteStore(os.path.join(TMP, "pc1_local"), shared1)
    a = s1.new_note(scope=st.SCOPE_SHARED)
    s1.set_content(a["id"], "<p>a</p>", "team note A")
    b = s1.new_note()                                       # 이 PC 노트
    s1.set_content(b["id"], "<p>b</p>", "private B")
    s1.save()
    with open(os.path.join(pc1, "README.md"), "a") as fh:   # 고치는 중인 다른 파일
        fh.write("work in progress\n")
    r = git_sync.push_shared(shared1)
    check("push: shared notes are committed and pushed", r.status == "pushed" and r.committed == 1, r)
    files = remote_files()
    check("push: GitHub has the shared note file", "shared/notes/{0}.json".format(a["id"]) in files, files)
    check("push: the This PC note never goes to git", not any(b["id"] in f for f in files) and
          "private B" not in run(REMOTE, "log", "-p", "main"))
    check("push: the other changed file stays uncommitted (only shared/notes is committed)",
          "M README.md" in run(pc1, "status", "--porcelain") and
          run(pc1, "show", "--name-only", "--format=", "HEAD").splitlines() == ["shared/notes/{0}.json".format(a["id"])])
    check("push: commit message says what it is, no PC name", run(pc1, "log", "-1", "--format=%s") ==
          "notes: update 1 shared note file(s)")
    r = git_sync.push_shared(shared1)
    check("push again with no change -> nothing to push", r.status == "nothing", r)

    # ---- PC2 가 먼저 올린다
    pc2 = clone("pc2")
    shared2 = os.path.join(pc2, "shared", "notes")
    s2 = st.NoteStore(os.path.join(TMP, "pc2_local"), shared2)
    check("PC2 sees PC1's shared note after cloning", s2.get(a["id"]) is not None and
          s2.get(a["id"])["text"] == "team note A")
    c_ = s2.new_note(scope=st.SCOPE_SHARED)
    s2.set_content(c_["id"], "<p>c</p>", "from PC2")
    s2.save()
    r = git_sync.push_shared(shared2)
    check("PC2 pushes its shared note", r.status == "pushed", r)
    time.sleep(0.02)
    s1.set_content(a["id"], "<p>a2</p>", "team note A edited on PC1")
    s1.save()
    r = git_sync.push_shared(shared1)
    check("PC1 push after PC2: rejected -> pull --rebase -> pushed (pulled flag)", r.status == "pushed" and r.pulled, r)
    check("PC1 now has PC2's note file, GitHub has both changes",
          os.path.isfile(os.path.join(shared1, c_["id"] + ".json")) and
          "team note A edited on PC1" in run(REMOTE, "show", "main:shared/notes/{0}.json".format(a["id"])))
    check("the uncommitted README change survived the pull (autostash)",
          "work in progress" in open(os.path.join(pc1, "README.md")).read())
    added, changed, removed = s1.reload_shared()
    check("PC1 store picks up PC2's note", (added, changed, removed) == (1, 0, 0) and s1.get(c_["id"]) is not None)

    # ---- 안 올라간 다른 커밋이 있으면 멈춘다
    with open(os.path.join(pc1, "code.py"), "w") as fh:
        fh.write("x = 1\n")
    run(pc1, "add", "code.py")
    run(pc1, "commit", "-q", "-m", "code change not pushed")
    before = remote_head()
    s1.set_content(a["id"], "<p>a3</p>", "third edit")
    s1.save()
    r = git_sync.push_shared(shared1)
    check("blocked when other unpushed commits exist (they would go too)", r.status == "blocked" and
          "code.py" in r.message and remote_head() == before, r.message)
    check("blocked: the shared change is left uncommitted and unstaged",
          run(pc1, "diff", "--cached", "--name-only") == "" and
          "shared/notes/{0}.json".format(a["id"]) in run(pc1, "status", "--porcelain"))
    run(pc1, "push", "-q", "origin", "main")                # 사용자가 코드를 먼저 올린 뒤

    # ---- 목록 창 버튼
    c = ctl.Controller(st.NoteStore(os.path.join(TMP, "pc1_local"), shared1))
    c.quiet = True
    c.start()
    app.processEvents()
    check("list window has a Push Shared button", c.list_window.btn_push.text() == "Push Shared")
    nid = c.new_note(scope=st.SCOPE_SHARED)
    c.windows[nid].editor.setPlainText("typed just before pushing")
    c.list_window.btn_push.click()
    app.processEvents()
    check("button: saves open notes first, then pushes only the shared notes",
          c.last_push.status == "pushed" and "shared/notes/{0}.json".format(nid) in remote_files() and
          "typed just before pushing" in run(REMOTE, "show", "main:shared/notes/{0}.json".format(nid)), c.messages[-1:])
    check("button: says what happened and is ready again", "Pushed" in c.messages[-1] and
          c.list_window.btn_push.isEnabled())

    # ---- v01.03 선택 영역 색 (끌어 고른 글자가 보이게)
    w = c.windows[nid]
    hl = w.editor.palette().color(QPalette.Inactive, QPalette.Highlight).name().upper()
    check("selection: opaque Windows blue, also when the note is not focused", hl == "#0078D7" and
          "selection-background-color: #0078D7; selection-color: #FFFFFF" in w.styleSheet(), hl)
    check("selection: a custom color close to that blue uses orange instead",
          st.selection_colors("#0A7AD5")[0] == st.SELECTION_ALT and st.selection_colors("Charcoal")[0] == st.SELECTION_BG)
    for win in list(c.windows.values()):
        win.close_quietly()
    c.list_window.close()
    app.processEvents()
finally:
    shutil.rmtree(TMP, ignore_errors=True)

print("\nRESULT: {0}/{1} passed".format(sum(R), len(R)))
sys.exit(0 if all(R) else 1)
