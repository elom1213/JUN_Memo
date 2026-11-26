# -*- coding: utf-8 -*-
# Python Script by Ji Hun Park
# last Update date : 2026-11-26
# JUN_Memo - 공유 노트만 git 으로 올리기 (v01.03) · 받기 (v01.13) · 알림용 원격 확인 (v01.14), Qt 비의존
"""
Push Shared = 공유 노트 폴더(shared/notes)만 커밋하고 푸시한다.

    1. git add -A -- shared/notes                      (새로 만든 · 고친 · 지운 공유 노트)
    2. git commit -m "notes: ..." -- shared/notes      (경로를 정해 커밋 - 다른 파일은 고친 게 있어도 안 들어간다)
    3. 푸시 전에 확인: 아직 안 올라간 커밋 중 공유 노트 **밖**을 바꾼 것이 있으면 멈춘다
       (브랜치를 푸시하면 그것까지 나가기 때문 - "shared 인 메모만" 이라는 약속을 지킨다).
    4. git push. 다른 PC 가 먼저 올려 거부되면 git pull --rebase --autostash 후 다시 푸시 (받은 공유 노트는 목록이 다시 읽는다).

돌려주는 값 = PushResult(status, message, committed, pulled)
    status : "pushed" / "nothing" / "blocked" / "error"

Pull Shared (v01.13) = 다른 PC 가 올린 것을 받기만 한다 (git pull --rebase --autostash). 커밋 · 푸시 없음.
    돌려주는 값 = PullResult(status, message, commits, shared_files, app_files)
    status : "pulled" / "nothing" / "error"

remote_status (v01.14) = 알림용. git fetch 만 해서 원격에 새 커밋(Pull 할 것)이 있는지 · 안 올린 공유 노트가 있는지 센다.
    작업 트리 · 브랜치는 건드리지 않는다(fetch 는 원격 추적 ref 만 바꾼다). A000080 JUN_Library 와 같은 방식.
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


def git(cwd, *args, check=True, timeout=None):
    """git 을 부르고 (코드, 표준 출력, 표준 에러). timeout 을 주면 그 초(v01.14 원격 확인은 짧게)."""
    limit = timeout or GIT_TIMEOUT
    try:
        proc = subprocess.run(["git"] + list(args), cwd=cwd, capture_output=True, timeout=limit,
                              creationflags=_flags())
    except FileNotFoundError:
        raise GitError("git was not found. Install Git for Windows and try again.")
    except subprocess.TimeoutExpired:
        raise GitError("git {0} took too long (over {1} s).".format(args[0], limit))
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


# ---------------------------------------------------------------- v01.13 Pull Shared
class PullResult(object):
    __slots__ = ("status", "message", "commits", "shared_files", "app_files")

    def __init__(self, status, message, commits=0, shared_files=None, app_files=None):
        self.status = status                    # "pulled" / "nothing" / "error"
        self.message = message
        self.commits = commits                  # 받아 온 커밋 수
        self.shared_files = shared_files or []  # 받아 온 변경 중 공유 노트 파일
        self.app_files = app_files or []        # 그 밖의 파일 (앱 코드 등 - 다시 켜야 반영)

    def __repr__(self):
        return "PullResult({0!r}, commits={1}, shared={2}, app={3})".format(
            self.status, self.commits, len(self.shared_files), len(self.app_files))


def _rebase_in_progress(root):
    for name in ("rebase-merge", "rebase-apply"):
        _c, out, _e = git(root, "rev-parse", "--git-path", name, check=False)
        path = out if os.path.isabs(out) else os.path.join(root, out)
        if out and os.path.isdir(path):
            return True
    return False


def pull_shared(shared_dir, remote="origin"):
    """v01.13 Pull Shared - 다른 PC 가 올린 공유 노트를 받는다 (git pull --rebase --autostash).

    부르기 전에 열린 노트를 저장해 두면, 이 PC 에서 고친 공유 노트(아직 안 올린 것)는 autostash 로 잠시 치웠다가
    받은 뒤 다시 얹힌다 - 다른 문단이면 git 이 합친다(v01.11 줄 배열). 아무것도 커밋 · 푸시하지 않는다.
    브랜치 전체를 받으므로 앱 코드가 바뀌었을 수도 있다 → app_files 로 알린다(다시 켜야 반영).
    실패하면 되돌린다: 리베이스 중 충돌이면 rebase --abort (받기 전 그대로).
    """
    try:
        root = repo_root(shared_dir)
        rel = _rel(root, shared_dir)
        code, _o, _e = git(root, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}", check=False)
        if code != 0:
            return PullResult("error", "This branch has no upstream on GitHub, so there is nothing to pull from.")
        git(root, "fetch", "-q", remote)
        _c, behind, _e = git(root, "rev-list", "--count", "HEAD..@{u}")
        commits = int(behind) if behind.isdigit() else 0
        if commits == 0:
            return PullResult("nothing", "Already up to date - no new shared notes on GitHub.")
        _c, out, _e = git(root, "diff", "--name-only", "HEAD...@{u}")
        files = [f for f in out.splitlines() if f.strip()]
        prefix = rel.rstrip("/") + "/"
        shared_files = [f for f in files if f.startswith(prefix)]
        app_files = [f for f in files if not f.startswith(prefix)]

        code, out, err = git(root, "pull", "--rebase", "--autostash", remote, _branch(root), check=False)
        if code != 0:
            aborted = False
            if _rebase_in_progress(root):
                git(root, "rebase", "--abort", check=False)
                aborted = True
            last = (err or out).splitlines()[-1] if (err or out) else code
            return PullResult("error", "Pull failed: {0}{1}".format(
                last, "\nNothing was changed (the pull was undone)." if aborted else ""))
        _c, unmerged, _e = git(root, "diff", "--name-only", "--diff-filter=U")
        conflicts = [f for f in unmerged.splitlines() if f.strip()]
        if conflicts:
            # autostash 를 다시 얹다 충돌 - 받은 것은 들어왔고, 이 PC 에서 고친 것은 git stash 에 남아 있다
            return PullResult("error", "Got the new commits, but your local changes clash with them in:\n{0}{1}\n"
                                       "Your local version is kept in 'git stash'. Fix the files (look for <<<<<<<), "
                                       "then use Reload shared notes.".format(
                                           "\n".join(conflicts[:5]), "\n..." if len(conflicts) > 5 else ""),
                              commits, shared_files, app_files)
        msg = "Pulled {0} commit(s) from GitHub: {1} shared note file(s) changed.".format(commits, len(shared_files))
        if app_files:
            msg += "\nApp files changed too ({0}) - restart JUN Memo to use them.".format(len(app_files))
        return PullResult("pulled", msg, commits, shared_files, app_files)
    except GitError as exc:
        return PullResult("error", str(exc))


# ---------------------------------------------------------------- v01.14 동기화 알림
def _has_upstream(root):
    code, _o, _e = git(root, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}", check=False)
    return code == 0


def _status_paths(root, rel):
    """커밋 안 된 공유 노트 (새 파일 · 고친 것 · 지운 것)."""
    _c, out, _e = git(root, "status", "--porcelain", "-uall", "--", rel, check=False)
    files = []
    for line in out.splitlines():
        if len(line) < 4:
            continue
        path = line[3:]
        if " -> " in path:                      # 이름 바뀜 = 새 이름
            path = path.split(" -> ", 1)[1]
        files.append(path.strip().strip('"'))
    return files


def pending_shared(shared_dir):
    """Push Shared 점 표시용 - 커밋 안 됐거나 아직 안 올라간 공유 노트 파일 (저장소 기준 경로, 정렬).
    @{u}...HEAD (세 점) = 내 쪽에서만 바뀐 것. 두 점이면 fetch 뒤 다른 PC 가 올린 파일까지 섞인다(JUN_Library 에서 고친 것)."""
    try:
        root = repo_root(shared_dir)
    except GitError:
        return []
    rel = _rel(root, shared_dir)
    files = set(_status_paths(root, rel))
    if _has_upstream(root):
        _c, out, _e = git(root, "diff", "--name-only", "@{u}...HEAD", "--", rel, check=False)
        files.update(f for f in out.splitlines() if f.strip())
    return sorted(files)


def remote_status(shared_dir, fetch=True, remote="origin"):
    """알림용 - 원격과 비교한 상태 (예외 없이 dict).

    {"behind": 원격에만 있는 커밋 수, "incoming": 그 커밋들이 바꾼 공유 노트 파일, "app_files": 그 밖의 파일,
     "pending": 커밋 안 됐거나 아직 안 올라간 공유 노트 파일, "error": 실패 이유(영어, 없으면 빈 문자열)}
    """
    st = {"behind": 0, "incoming": [], "app_files": [], "pending": [], "error": ""}
    try:
        root = repo_root(shared_dir)
        rel = _rel(root, shared_dir)
        st["pending"] = pending_shared(shared_dir)
        if not _has_upstream(root):
            st["error"] = "This branch has no upstream on GitHub."
            return st
        if fetch:
            code, out, err = git(root, "fetch", "-q", remote, check=False, timeout=30)
            if code != 0:
                lines = [l for l in (err or out).splitlines() if l.strip()]
                st["error"] = "Could not check GitHub: {0}".format(lines[-1] if lines else code)
        code, out, _e = git(root, "rev-list", "--count", "HEAD..@{u}", check=False)
        st["behind"] = int(out) if code == 0 and out.isdigit() else 0
        if st["behind"]:
            _c, out, _e = git(root, "diff", "--name-only", "HEAD...@{u}", check=False)
            files = [f for f in out.splitlines() if f.strip()]
            prefix = rel.rstrip("/") + "/"
            st["incoming"] = [f for f in files if f.startswith(prefix)]
            st["app_files"] = [f for f in files if not f.startswith(prefix)]
    except GitError as exc:
        st["error"] = str(exc)
    return st
