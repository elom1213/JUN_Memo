# -*- coding: utf-8 -*-
# JUN_Memo v01.14 동기화 알림 시험 (실제 git, 오프스크린)   python tests/test_sync_notice.py
# 임시 "GitHub"(bare 저장소) + PC 두 대(클론 둘)로:
#   remote_status - git 밖 · 받을 것 없음 · 다른 PC 의 새 커밋(fetch 로만 알아냄, 작업 트리 불변) · 앱 파일만 바뀐 커밋 ·
#   안 올린 공유 노트(미커밋 + 안 올린 커밋, fetch 뒤 다른 PC 파일이 섞이지 않음) ·
#   목록 창 - Pull Shared ● / Push Shared ● · 알림 막대(Pull now / Push now / Later) · 받을 것이 늘면 다시 ·
#   시작 때 남은 안 올린 노트는 바로, 새로 생긴 것은 10분 뒤 · 줄인 창은 애니메이션 점 · 백그라운드 확인 · 설정 저장
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
TMP = tempfile.mkdtemp(prefix="jun_memo_notice_")
os.environ["JUN_MEMO_SHARED"] = os.path.join(TMP, "unused_shared")

from PySide6.QtWidgets import QApplication   # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)

from app.core import git_sync   # noqa: E402
from app.core import store as st   # noqa: E402
from app.ui import controller as ctl   # noqa: E402
from app.ui import list_window as lwmod   # noqa: E402
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
    """노트 창 편집기가 쓰는 HTML 로 (test_pull_shared 와 같은 이유)."""
    win = NoteWindow(store.get(note_id))
    win.editor.setPlainText(text)
    html, plain = win.content()
    win.close_quietly()
    store.set_content(note_id, html, plain)


def rel(note_id):
    return "shared/notes/{0}.json".format(note_id)


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

    # ---------------------------------------------------------------- core
    outside = os.path.join(TMP, "not_a_repo", "shared", "notes")
    os.makedirs(outside)
    s = git_sync.remote_status(outside)
    check("remote_status outside git -> error, nothing to do", s["error"] and s["behind"] == 0 and s["pending"] == [], s)
    s = git_sync.remote_status(shared1)
    check("remote_status: up to date -> behind 0, nothing pending, no error",
          s["behind"] == 0 and s["pending"] == [] and not s["error"], s)

    s2 = st.NoteStore(os.path.join(TMP, "pc2_local"), shared2)
    a = s2.new_note(scope=st.SCOPE_SHARED)
    put(s2, a["id"], "note A from PC2")
    s2.save()
    check("PC2 pushes note A", git_sync.push_shared(shared2).status == "pushed")
    head1 = run(pc1, "rev-parse", "HEAD")
    s = git_sync.remote_status(shared1, fetch=False)
    check("without fetch PC1 does not know yet", s["behind"] == 0, s)
    s = git_sync.remote_status(shared1)
    check("with fetch: 1 commit behind, note A incoming, no app files",
          s["behind"] == 1 and s["incoming"] == [rel(a["id"])] and s["app_files"] == [], s)
    check("fetch does not touch the branch or work tree",
          run(pc1, "rev-parse", "HEAD") == head1 and not os.path.exists(os.path.join(shared1, a["id"] + ".json")))

    # 안 올린 공유 노트: 미커밋 새 노트 + 다른 PC 파일은 섞이지 않는다
    s1 = st.NoteStore(os.path.join(TMP, "pc1_local"), shared1)
    b = s1.new_note(scope=st.SCOPE_SHARED)
    put(s1, b["id"], "note B on PC1")
    s1.save()
    s = git_sync.remote_status(shared1, fetch=False)
    check("pending: PC1's uncommitted new note only (not PC2's incoming note)",
          s["pending"] == [rel(b["id"])] and s["behind"] == 1, s)
    local = s1.new_note(scope=st.SCOPE_LOCAL)
    put(s1, local["id"], "this pc only")
    s1.save()
    with open(os.path.join(pc1, "scratch.txt"), "w") as fh:
        fh.write("not a note\n")
    check("pending ignores This PC notes and files outside shared/notes",
          git_sync.pending_shared(shared1) == [rel(b["id"])], git_sync.pending_shared(shared1))
    os.remove(os.path.join(pc1, "scratch.txt"))
    # 안 올린 커밋 속 공유 노트도
    run(pc1, "add", "--", "shared/notes")
    run(pc1, "commit", "-q", "-m", "local note commit")
    check("pending: committed but not pushed note still counts", git_sync.pending_shared(shared1) == [rel(b["id"])])

    # 앱 파일만 바뀐 커밋
    with open(os.path.join(pc2, "README.md"), "a") as fh:
        fh.write("v2\n")
    run(pc2, "commit", "-q", "-am", "app update")
    run(pc2, "push", "-q", "origin", "main")
    s = git_sync.remote_status(shared1)
    check("app update: behind 2, app file listed separately",
          s["behind"] == 2 and s["incoming"] == [rel(a["id"])] and s["app_files"] == ["README.md"], s)

    # ---------------------------------------------------------------- 목록 창
    c = ctl.Controller(st.NoteStore(os.path.join(TMP, "pc1_ui"), shared1))
    c.quiet = True
    c.start()
    app.processEvents()
    lw = c.list_window
    check("quiet (tests): no automatic background check", not c.auto_check and c._checker is None)
    check("before any check: plain buttons, no notice",
          lw.btn_pull.text() == "Pull Shared" and lw.btn_push.text() == "Push Shared" and lw.notice.isHidden())

    c.recount_now()                         # fetch 는 이미 함 → behind 2, pending 1 (시작 직후)
    check("Pull Shared ● when GitHub has new commits", lw.btn_pull.text() == "Pull Shared ●" and
          lw.btn_pull.property("hint") is True, lw.btn_pull.text())
    check("Push Shared ● when shared notes are not pushed", lw.btn_push.text() == "Push Shared ●" and
          rel(b["id"]) in lw.btn_push.toolTip(), lw.btn_push.text())
    check("notice: pull wins over push, says how many shared note files",
          lw.notice_kind == "pull" and not lw.notice.isHidden() and lw.btn_notice.text() == "Pull now" and
          "1 shared note file from another PC" in lw.lbl_notice.text(), lw.lbl_notice.text())
    check("hint border styles exist", 'QToolButton#pullShared[hint="true"]' in lw.styleSheet() and
          '#syncNotice[kind="push"]' in lw.styleSheet())

    lw.btn_notice_close.click()             # Later
    check("Later: pull notice hidden; leftover unpushed note shows right away (from startup)",
          lw.notice_kind == "push" and lw.btn_notice.text() == "Push now" and
          "1 shared note file not pushed yet" in lw.lbl_notice.text(), lw.lbl_notice.text())
    lw.btn_notice_close.click()
    check("Later on push: notice hidden, dots stay", lw.notice.isHidden() and lw.notice_kind == "" and
          lw.btn_pull.text() == "Pull Shared ●")

    # 받을 것이 늘면 다시
    s2.reload_shared()
    put(s2, a["id"], "note A edited on PC2")
    s2.save()
    git_sync.push_shared(shared2)
    c._remote_checked(git_sync.remote_status(shared1))
    check("more commits after Later -> pull notice again", lw.notice_kind == "pull" and not lw.notice.isHidden())

    # 줄인 창
    lw.set_shrunk(True, emit=False)
    check("shrunk: notice hidden, animation shows the pull dot",
          lw.notice.isHidden() and lw.anim.hint == "pull" and "Pull" in lw.anim.toolTip())
    img = lw.anim.grab().toImage()
    px = img.pixelColor(img.width() - 10, 10)
    check("shrunk: the dot is drawn blue at the top right", px.blue() > 180 and px.red() < 80, px.name())
    lw.set_shrunk(False, emit=False)
    check("unshrunk: notice back", not lw.notice.isHidden() and lw.notice_kind == "pull")

    # Pull now → 받고 다시 셈
    lw.btn_notice.click()
    app.processEvents()
    check("Pull now pulls", c.last_pull.status == "pulled", c.messages[-1:])
    check("after pull: Pull dot gone, push still pending (note B)",
          lw.btn_pull.text() == "Pull Shared" and lw.btn_push.text() == "Push Shared ●" and c.remote["behind"] == 0,
          (lw.btn_pull.text(), lw.btn_push.text()))
    check("push notice stays dismissed until it is pushed", lw.notice.isHidden())

    # Push now (Later 해제 시험: 다 올린 뒤 새로 생기면 10분 뒤에만)
    lw._dismiss_push = False
    lw._update_notice()
    check("push notice can be acted on", lw.notice_kind == "push")
    lw.btn_notice.click()
    app.processEvents()
    check("Push now pushes", c.last_push.status == "pushed", c.messages[-1:])
    check("after push: no dots, no notice", lw.btn_push.text() == "Push Shared" and lw.notice.isHidden() and
          c.remote["pending"] == [])

    # 새로 생긴 안 올린 노트 = 10분 뒤에만 알림
    lw._born -= 3600                        # 시작한 지 오래
    n = c.store.new_note(scope=st.SCOPE_SHARED)
    put(c.store, n["id"], "fresh edit")
    c.save_now()
    c.recount_now()
    check("fresh unpushed note: dot at once, but no notice yet",
          lw.btn_push.text() == "Push Shared ●" and lw.notice.isHidden())
    lw._pending_since -= lwmod.PUSH_REMIND_SEC + 1
    lw._update_notice()
    check("after 10 minutes: push notice", lw.notice_kind == "push" and not lw.notice.isHidden())

    # 백그라운드 확인 (실제 스레드)
    put(s2, a["id"], "note A third edit")
    s2.reload_shared()
    put(s2, a["id"], "note A third edit")
    s2.save()
    git_sync.push_shared(shared2)
    check("check_remote starts a background check", c.check_remote() is True and c._checker is not None)
    check("a second check while one runs is skipped", c.check_remote() is False)
    c._checker.wait(40000)
    for _ in range(20):
        app.processEvents()
        if c._checker is None:
            break
        time.sleep(0.05)
    check("background check finished and updated the window",
          c._checker is None and c.remote["behind"] == 1 and lw.btn_pull.text() == "Pull Shared ●", c.remote)

    # 설정
    check("menu has the check toggle (on by default)", lw.act_check.isChecked() and c.check_enabled())
    lw.act_check.setChecked(False)
    check("toggle off is saved", c.store.list_view["check_remote"] is False)
    s3 = st.NoteStore(os.path.join(TMP, "pc1_ui"), shared1)
    check("toggle off survives a restart", s3.list_view["check_remote"] is False)
    lw.act_check.setChecked(True)

    for win in list(c.windows.values()):
        win.close_quietly()
    c.shutdown()
    lw.close()
    app.processEvents()
finally:
    shutil.rmtree(TMP, ignore_errors=True)

print("\nRESULT: {0}/{1} passed".format(sum(R), len(R)))
sys.exit(0 if all(R) else 1)
