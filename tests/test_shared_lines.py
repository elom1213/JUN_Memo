# -*- coding: utf-8 -*-
# JUN_Memo v01.11 시험   python tests/test_shared_lines.py
# 공유 노트 파일의 본문(html · text)을 줄 배열로 저장 - git 병합 충돌을 사람이 읽을 수 있게.
# 정확히 되돌아옴 · 옛 형식(한 줄 문자열) 읽기 + 다음 저장 때 바꿔 쓰기 · 실제 git 으로 두 PC 가 다른 문단을 고치면 충돌 없이 병합,
# 같은 문단을 고치면 충돌이 그 줄에만 난다.
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from app.core import store as st   # noqa: E402

R = []


def check(name, cond, extra=""):
    R.append(bool(cond))
    print(("PASS " if cond else "FAIL ") + name + ("  | " + str(extra) if extra != "" else ""))


def git(cwd, *args):
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "core.autocrlf=false"] + list(args),
                          cwd=cwd, capture_output=True, text=True, encoding="utf-8")


def para_html(paras):
    return "<html><body>\n" + "\n".join("<p>{0}</p>".format(p) for p in paras) + "\n</body></html>"


TMP = tempfile.mkdtemp(prefix="jun_memo_lines_")
try:
    local, shared = os.path.join(TMP, "local"), os.path.join(TMP, "shared")
    s = st.NoteStore(local, shared)
    n = s.new_note(scope=st.SCOPE_SHARED)
    text = "first\n\nthird with \"quotes\"\r\nend\n"
    s.set_content(n["id"], para_html(["one", "two"]), text)
    s.save()
    path = os.path.join(shared, n["id"] + ".json")
    raw = json.load(open(path, encoding="utf-8"))
    check("html and text are saved as arrays of lines", isinstance(raw["html"], list) and isinstance(raw["text"], list),
          raw["text"])
    with open(path, encoding="utf-8") as fh:
        longest = max(len(line) for line in fh)
    check("no very long line in the file", longest < 80, longest)
    back = st.NoteStore(local, shared).get(n["id"])
    check("reads back exactly (blank lines, CR, trailing newline)", back["text"] == text and back["html"] == s.get(n["id"])["html"])

    # 옛 형식 (한 줄 문자열)
    old = dict(raw, html=para_html(["old"]), text="old line 1\nold line 2")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(old, fh)
    s2 = st.NoteStore(local, shared)
    check("old one-line file still reads", s2.get(n["id"])["text"] == "old line 1\nold line 2")
    s2.save()
    raw2 = json.load(open(path, encoding="utf-8"))
    check("old file is rewritten as lines on the next save", raw2["text"] == ["old line 1", "old line 2"] and
          s2.get(n["id"])["text"] == "old line 1\nold line 2")
    mtime = os.path.getmtime(path)
    s2.save()
    check("...and not rewritten again when nothing changed", os.path.getmtime(path) == mtime)

    # ---- 실제 git: 두 PC 가 같은 노트의 다른 문단을 고친다
    def merge_case(edit_a, edit_b):
        repo = tempfile.mkdtemp(prefix="repo_", dir=TMP)
        git(repo, "init", "-q", "-b", "main")
        sd = os.path.join(repo, "shared", "notes")
        paras = ["para {0}".format(i) for i in range(10)]
        base = st.NoteStore(os.path.join(repo, "_l"), sd)
        note = base.new_note(scope=st.SCOPE_SHARED)
        base.set_content(note["id"], para_html(paras), "\n".join(paras))
        base.save()
        git(repo, "add", "shared")
        git(repo, "commit", "-q", "-m", "base")
        git(repo, "branch", "pc2")
        for branch, (idx, word) in (("main", edit_a), ("pc2", edit_b)):
            git(repo, "checkout", "-q", branch)
            pc = st.NoteStore(os.path.join(repo, "_l_" + branch), sd)
            p2 = list(paras)
            p2[idx] = word
            pc.set_content(note["id"], para_html(p2), "\n".join(p2))
            pc.save()
            git(repo, "commit", "-q", "-am", branch)
        git(repo, "checkout", "-q", "main")
        res = git(repo, "merge", "pc2", "-m", "merge")
        with open(os.path.join(sd, note["id"] + ".json"), encoding="utf-8") as fh:
            return res.returncode, fh.read()

    code, body = merge_case((1, "edited on PC1"), (8, "edited on PC2"))
    # 두 PC 모두 고친 시각(modified)을 바꾸므로 그 한 줄은 충돌한다 - 본문의 두 문단은 git 이 알아서 합친다
    lines = body.splitlines()
    marks = [i for i, line in enumerate(lines) if line.startswith(("<<<<<<<", "=======", ">>>>>>>"))]
    inside = [lines[i] for i in range(marks[0] + 1, marks[-1]) if i not in marks] if marks else []
    check("two PCs edit different paragraphs -> both edits merged, only the 'modified' line conflicts",
          len(marks) == 3 and all(x.strip().startswith('"modified"') for x in inside) and
          body.count("edited on PC1") == 2 and body.count("edited on PC2") == 2, inside)
    code, body = merge_case((4, "PC1 wording"), (4, "PC2 wording"))
    conflict = [line for line in body.splitlines() if line.startswith(("<<<<<<<", "=======", ">>>>>>>"))]
    inside = body.split("<<<<<<<", 1)[-1].split(">>>>>>>", 1)[0] if conflict else ""
    check("same paragraph edited -> conflict only around that line, readable",
          code != 0 and len(conflict) >= 3 and "PC1 wording" in inside and "PC2 wording" in inside and
          "para 0" not in inside and "para 9" not in inside and max(len(x) for x in inside.splitlines()) < 80,
          len(inside))
finally:
    shutil.rmtree(TMP, ignore_errors=True)

print("\nRESULT: {0}/{1} passed".format(sum(R), len(R)))
sys.exit(0 if all(R) else 1)
