# -*- coding: utf-8 -*-
# JUN_Memo v01.13 Pull Shared 시험 (실제 git, 오프스크린)   python tests/test_pull_shared.py
# 임시 "GitHub"(bare 저장소) + PC 두 대(클론 둘)로:
#   git 밖이면 에러 · 받을 것 없음 · 다른 PC 의 새 노트 · 고친 노트 받기 · 이 PC 의 안 올린 수정은 autostash 로 살아남음 ·
#   앱 파일이 바뀌면 다시 켜라고 알림 · 리베이스 충돌이면 되돌림 · 목록 창 버튼(Push Shared 옆) ·
#   열린 공유 노트는 받은 내용으로 다시 열리고 다음 저장이 옛 내용으로 덮지 않음
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
TMP = tempfile.mkdtemp(prefix="jun_memo_pull_")
os.environ["JUN_MEMO_SHARED"] = os.path.join(TMP, "unused_shared")

from PySide6.QtWidgets import QApplication   # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)

from app.core import git_sync   # noqa: E402
from app.core import store as st   # noqa: E402
from app.ui import controller as ctl   # noqa: E402
from app.ui.note_window import NoteWindow   # noqa: E402

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


def put(store, note_id, text):
    """노트 창 편집기가 쓰는 것과 같은 HTML 로. 손으로 쓴 <p> 나 QTextDocument 의 HTML 은 글꼴이 달라서
    다른 PC 가 노트를 열기만 해도 다시 쓰여 로컬 변경이 생긴다(실제 앱이 쓴 노트는 다시 열어도 그대로 - 실측)."""
    win = NoteWindow(store.get(note_id))
    win.editor.setPlainText(text)
    html, plain = win.content()
    win.close_quietly()
    store.set_content(note_id, html, plain)


def read_shared(shared_dir, note_id):
    s = st.NoteStore(os.path.join(TMP, "probe_local_{0}".format(time.time())), shared_dir)
    n = s.get(note_id)
    return n["text"] if n else None


try:
    REMOTE = os.path.join(TMP, "remote.git")
    run(TMP, "init", "-q", "--bare", "-b", "main", REMOTE)
    pc1 = clone("pc1")
    with open(os.path.join(pc1, "README.md"), "w") as fh:
        fh.write("app\n")
    os.makedirs(os.path.join(pc1, "shared", "notes"))
    open(os.path.join(pc1, "shared", "notes", ".gitkeep"), "w").close()
    run(pc1, "add", "-A")
    run(pc1, "commit", "-q", "-m", "init")
    run(pc1, "push", "-q", "-u", "origin", "main")
    pc2 = clone("pc2")
    shared1 = os.path.join(pc1, "shared", "notes")
    shared2 = os.path.join(pc2, "shared", "notes")

    # ---- git 밖 · 받을 것 없음
    outside = os.path.join(TMP, "not_a_repo", "shared", "notes")
    os.makedirs(outside)
    r = git_sync.pull_shared(outside)
    check("not in a git repository -> error", r.status == "error", r.message)
    r = git_sync.pull_shared(shared1)
    check("nothing new on GitHub -> nothing", r.status == "nothing", r)

    # ---- PC2 가 새 노트를 올린다 → PC1 이 받는다
    s2 = st.NoteStore(os.path.join(TMP, "pc2_local"), shared2)
    a = s2.new_note(scope=st.SCOPE_SHARED)
    put(s2, a["id"], "note A from PC2")
    s2.save()
    check("PC2 pushes note A", git_sync.push_shared(shared2).status == "pushed")
    s1 = st.NoteStore(os.path.join(TMP, "pc1_local"), shared1)
    r = git_sync.pull_shared(shared1)
    check("pull: gets PC2's commit", r.status == "pulled" and r.commits == 1 and
          r.shared_files == ["shared/notes/{0}.json".format(a["id"])] and not r.app_files, r)
    check("pull: message says what came in, no restart note", "1 shared note file(s)" in r.message and
          "restart" not in r.message, r.message)
    added, changed, removed = s1.reload_shared()
    check("pull: the store sees note A", (added, changed, removed) == (1, 0, 0) and
          s1.get(a["id"])["text"] == "note A from PC2")
    check("pull: nothing is committed or pushed by pull",
          run(pc1, "rev-parse", "HEAD") == run(REMOTE, "rev-parse", "main"))

    # ---- PC1 의 안 올린 수정(다른 노트)은 살아남는다
    b = s1.new_note(scope=st.SCOPE_SHARED)
    put(s1, b["id"], "note B on PC1, not pushed")
    s1.save()
    time.sleep(0.02)
    s2.reload_shared()
    put(s2, a["id"], "note A edited on PC2")
    s2.save()
    git_sync.push_shared(shared2)
    r = git_sync.pull_shared(shared1)
    check("pull with local unpushed edits: pulled", r.status == "pulled", r)
    check("pull: PC2's edit arrived", read_shared(shared1, a["id"]) == "note A edited on PC2")
    check("pull: PC1's unpushed note B survived (autostash), still uncommitted",
          read_shared(shared1, b["id"]) == "note B on PC1, not pushed" and
          "shared/notes/{0}.json".format(b["id"]) in run(pc1, "status", "--porcelain"))
    check("pull: no stash left behind", run(pc1, "stash", "list") == "")

    # ---- 앱 파일이 바뀌면 다시 켜라고
    with open(os.path.join(pc2, "README.md"), "a") as fh:
        fh.write("new app version\n")
    run(pc2, "commit", "-q", "-am", "app update")
    run(pc2, "push", "-q", "origin", "main")
    r = git_sync.pull_shared(shared1)
    check("pull: app files changed -> listed and 'restart' in the message",
          r.status == "pulled" and r.app_files == ["README.md"] and "restart" in r.message, r.message)

    # ---- 리베이스 충돌이면 되돌린다
    with open(os.path.join(pc1, "code.py"), "w") as fh:
        fh.write("x = 1\n")
    run(pc1, "add", "code.py")
    run(pc1, "commit", "-q", "-m", "pc1 code")
    with open(os.path.join(pc2, "code.py"), "w") as fh:
        fh.write("x = 2\n")
    run(pc2, "add", "code.py")
    run(pc2, "commit", "-q", "-m", "pc2 code")
    run(pc2, "push", "-q", "origin", "main")
    head_before = run(pc1, "rev-parse", "HEAD")
    r = git_sync.pull_shared(shared1)
    check("pull: rebase conflict -> error and undone", r.status == "error" and "undone" in r.message, r.message)
    check("pull: after undo, HEAD and work tree are as before (no rebase in progress, note B kept)",
          run(pc1, "rev-parse", "HEAD") == head_before and not git_sync._rebase_in_progress(pc1) and
          open(os.path.join(pc1, "code.py")).read() == "x = 1\n" and
          read_shared(shared1, b["id"]) == "note B on PC1, not pushed", r.message)
    run(pc1, "reset", "-q", "--hard", "HEAD~1")             # 시험용: 충돌 커밋을 버리고 계속
    # reset --hard 는 note B(추적 안 되는 새 파일)는 남긴다
    r = git_sync.pull_shared(shared1)
    check("pull after resolving: pulled", r.status == "pulled", r)

    # ---- 목록 창 버튼 + 열린 공유 노트
    c = ctl.Controller(st.NoteStore(os.path.join(TMP, "pc1_ui"), shared1))
    c.quiet = True
    c.start()
    app.processEvents()
    lw = c.list_window
    bottom = lw.btn_push.parentWidget().layout()
    layout = None
    for i in range(bottom.count()):
        item = bottom.itemAt(i)
        if item.layout() is not None and item.layout().indexOf(lw.btn_push) >= 0:
            layout = item.layout()
    check("list window has a Pull Shared button right before Push Shared",
          lw.btn_pull.text() == "Pull Shared" and layout is not None and
          layout.indexOf(lw.btn_pull) == layout.indexOf(lw.btn_push) - 1)
    check("Pull Shared is hidden by Shrink like Push Shared", lw.btn_pull in lw._shrink_hidden)
    check("Pull Shared button has the bordered style", "QToolButton#pullShared" in lw.styleSheet())

    c.open_note(a["id"])
    app.processEvents()
    old_win = c.windows[a["id"]]
    check("note A is open on PC1 with the old text", old_win.content()[1] == "note A edited on PC2")
    time.sleep(0.02)
    s2.reload_shared()
    put(s2, a["id"], "note A third edit on PC2")
    s2.save()
    git_sync.push_shared(shared2)
    lw.btn_pull.click()
    app.processEvents()
    check("button: pulled and says so", c.last_pull.status == "pulled" and "Pulled" in c.messages[-1], c.messages[-1:])
    new_win = c.windows.get(a["id"])
    check("button: the open note was reopened with PC2's new text",
          new_win is not None and new_win is not old_win and new_win.content()[1] == "note A third edit on PC2" and
          "1 open note(s) were refreshed" in c.messages[-1], c.messages[-1:])
    c.save_now()
    check("button: saving afterwards does not overwrite the pulled text with the old one",
          read_shared(shared1, a["id"]) == "note A third edit on PC2")
    check("button: ready again", lw.btn_pull.isEnabled() and lw.btn_pull.text() == "Pull Shared")
    lw.btn_pull.click()
    app.processEvents()
    check("button: second click -> already up to date", c.last_pull.status == "nothing")
    for win in list(c.windows.values()):
        win.close_quietly()
    lw.close()
    app.processEvents()
finally:
    shutil.rmtree(TMP, ignore_errors=True)

print("\nRESULT: {0}/{1} passed".format(sum(R), len(R)))
sys.exit(0 if all(R) else 1)
