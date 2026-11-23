# -*- coding: utf-8 -*-
# Python Script by Ji Hun Park
# last Update date : 2026-11-23
# JUN_Memo - 공유 노트만 git 으로 올리기 (v01.03, Qt 비의존)
"""
Push Shared = 공유 노트 폴더(shared/notes)만 커밋하고 푸시한다.

    1. git add -A -- shared/notes                      (새로 만든 · 고친 · 지운 공유 노트)
    2. git commit -m "notes: ..." -- shared/notes      (경로를 정해 커밋 - 다른 파일은 고친 게 있어도 안 들어간다)
    3. 푸시 전에 확인: 아직 안 올라간 커밋 중 공유 노트 **밖**을 바꾼 것이 있으면 멈춘다
       (브랜치를 푸시하면 그것까지 나가기 때문 - "shared 인 메모만" 이라는 약속을 지킨다).
    4. git push. 다른 PC 가 먼저 올려 거부되면 git pull --rebase --autostash 후 다시 푸시 (받은 공유 노트는 목록이 다시 읽는다).

돌려주는 값 = PushResult(status, message, committed, pulled)
    status : "pushed" / "nothing" / "blocked" / "error"
커밋 메시지에는 PC 이름 같은 것을 넣지 않는다(공개 저장소일 수 있다).
"""

import os
import subprocess
import sys

GIT_TIMEOUT = 120


class PushResult(object):
    __slots__ = ("status", "message", "committed", "pulled")

    def __init__(self, status, message, committed=0, pulled=False):
        self.status = status
        self.message = message
        self.committed = committed      # 이번에 커밋한 공유 노트 파일 수
        self.pulled = pulled            # 다른 PC 의 커밋을 받아 왔나 (목록을 다시 읽어야)

    def __repr__(self):
        return "PushResult({0!r}, committed={1}, pulled={2})".format(self.status, self.committed, self.pulled)


class GitError(Exception):
    pass


def _flags():
    return getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform.startswith("win") else 0


def git(cwd, *args, check=True):
    """git 을 부르고 (코드, 표준 출력, 표준 에러)."""
    try:
        proc = subprocess.run(["git"] + list(args), cwd=cwd, capture_output=True, timeout=GIT_TIMEOUT,
                              creationflags=_flags())
    except FileNotFoundError:
        raise GitError("git was not found. Install Git for Windows and try again.")
    except subprocess.TimeoutExpired:
        raise GitError("git {0} took too long (over {1} s).".format(args[0], GIT_TIMEOUT))
    out = proc.stdout.decode("utf-8", "replace").strip()
    err = proc.stderr.decode("utf-8", "replace").strip()
    if check and proc.returncode != 0:
        raise GitError("git {0} failed: {1}".format(" ".join(args[:2]), (err or out).splitlines()[-1] if (err or out) else proc.returncode))
    return proc.returncode, out, err


def repo_root(path):
    if not os.path.isdir(path):
        raise GitError("The shared notes folder does not exist yet: {0}".format(path))
    _c, out, _e = git(path, "rev-parse", "--show-toplevel")
    return os.path.normpath(out)


def _rel(root, path):
    return os.path.relpath(os.path.normpath(path), root).replace("\\", "/")


def _unpushed_outside(root, rel):
    """올라가지 않은 커밋이 바꾼 파일 중 rel 밖의 것 (업스트림이 없으면 None)."""
    code, _o, _e = git(root, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}", check=False)
    if code != 0:
        return None
    _c, out, _e = git(root, "log", "@{u}..HEAD", "--name-only", "--format=")
    files = sorted({f for f in out.splitlines() if f.strip()})
    prefix = rel.rstrip("/") + "/"
    return [f for f in files if not f.startswith(prefix)]


def _ahead(root):
    code, out, _e = git(root, "rev-list", "--count", "@{u}..HEAD", check=False)
    return int(out) if code == 0 and out.isdigit() else None


def push_shared(shared_dir, remote="origin"):
    """공유 노트만 커밋 · 푸시. 예외 대신 PushResult 로 알린다."""
    try:
        root = repo_root(shared_dir)
        rel = _rel(root, shared_dir)
        git(root, "add", "-A", "--", rel)
        _c, staged, _e = git(root, "diff", "--cached", "--name-only", "--", rel)
        changed = [f for f in staged.splitlines() if f.strip()]
        outside = _unpushed_outside(root, rel)
        if outside:
            # 커밋하기 전에 멈춘다 - 공유 노트만 올린다는 약속을 지킬 수 없다
            git(root, "reset", "-q", "--", rel, check=False)
            return PushResult("blocked", "This branch has commits that are not pushed yet and change other files "
                                         "({0}{1}).\nPushing now would send them too, so nothing was pushed. "
                                         "Push those commits first (or ask for it), then try again.".format(
                                             ", ".join(outside[:3]), " ..." if len(outside) > 3 else ""))
        if changed:
            msg = "notes: update {0} shared note file(s)".format(len(changed))
            git(root, "commit", "-q", "-m", msg, "--", rel)
        ahead = _ahead(root)
        if not changed and ahead == 0:
            return PushResult("nothing", "The shared notes are already up to date on GitHub - nothing to push.")
        code, out, err = git(root, "push", remote, "HEAD", check=False)
        pulled = False
        if code != 0:
            text = (err + out).lower()
            if "rejected" in text or "fetch first" in text or "non-fast-forward" in text:
                git(root, "pull", "--rebase", "--autostash", remote, _branch(root))
                pulled = True
                code, out, err = git(root, "push", remote, "HEAD", check=False)
            if code != 0:
                return PushResult("error", "Push failed: {0}".format((err or out).splitlines()[-1] if (err or out)
                                                                    else code), len(changed), pulled)
        return PushResult("pushed", "Pushed {0} shared note file(s) to GitHub.{1}".format(
            len(changed), " Got new shared notes from another PC first." if pulled else ""), len(changed), pulled)
    except GitError as exc:
        return PushResult("error", str(exc))


def _branch(root):
    _c, out, _e = git(root, "rev-parse", "--abbrev-ref", "HEAD")
    return out
