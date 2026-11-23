# -*- coding: utf-8 -*-
# Python Script by Ji Hun Park
# last Update date : 2026-11-23
# JUN_Memo - 노트 저장소 (Qt 비의존)
"""
노트 하나 = dict:
    id        : 고유 문자열 (uuid4 hex)
    html      : 본문 (QTextEdit HTML)
    text      : 본문 글자만 (목록 미리보기 · 검색)
    color     : 색 이름(COLORS 키) 또는 "#rrggbb" (사용자 색)
    pinned    : 늘 맨 위 (Pin)
    open      : 창이 열려 있었나 (다시 켜면 그 노트들을 다시 연다 - 윈도우 스티커 메모처럼)
    geometry  : [x, y, w, h] 마지막 창 위치 · 크기 (없으면 None)
    created / modified : epoch 초

저장 파일은 json 하나(`%APPDATA%/JUN_Memo/notes.json`). 쓰기는 임시 파일 → os.replace 로 한 번에(쓰다 꺼져도 깨지지 않게),
직전 파일은 notes.json.bak 으로 하나 남긴다.
"""

import json
import os
import time
import uuid

FILE_VERSION = 1

#: 윈도우 스티커 메모와 같은 색 (본문, 위쪽 띠, 글자). 순서 = 메뉴 순서.
COLORS = {
    "Yellow":   {"body": "#FFF7D1", "header": "#FFF2AB", "text": "#202020"},
    "Green":    {"body": "#E4F9E0", "header": "#CBF1C4", "text": "#202020"},
    "Pink":     {"body": "#FFE4F1", "header": "#FFCCE5", "text": "#202020"},
    "Purple":   {"body": "#F2E6FF", "header": "#E7CFFF", "text": "#202020"},
    "Blue":     {"body": "#E2F1FF", "header": "#CDE9FF", "text": "#202020"},
    "Gray":     {"body": "#F3F2F1", "header": "#E1DFDD", "text": "#202020"},
    "Charcoal": {"body": "#696969", "header": "#616161", "text": "#FFFFFF"},
}
DEFAULT_COLOR = "Yellow"


def default_path():
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    return os.path.join(base, "JUN_Memo", "notes.json")


# ---------------------------------------------------------------------- 색
def _hex_rgb(h):
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _rgb_hex(r, g, b):
    return "#{0:02X}{1:02X}{2:02X}".format(max(0, min(255, int(r))), max(0, min(255, int(g))), max(0, min(255, int(b))))


def is_hex(color):
    if not isinstance(color, str) or not color.startswith("#") or len(color) != 7:
        return False
    try:
        _hex_rgb(color)
        return True
    except ValueError:
        return False


def palette(color):
    """색 이름 또는 "#rrggbb" → {"body", "header", "text"}. 사용자 색은 띠를 조금 어둡게, 글자는 밝기로 검정 / 흰색."""
    if color in COLORS:
        return dict(COLORS[color])
    if not is_hex(color):
        return dict(COLORS[DEFAULT_COLOR])
    r, g, b = _hex_rgb(color)
    header = _rgb_hex(r * 0.93, g * 0.93, b * 0.93)
    luminance = 0.299 * r + 0.587 * g + 0.114 * b
    return {"body": color.upper(), "header": header, "text": "#202020" if luminance > 140 else "#FFFFFF"}


# ---------------------------------------------------------------------- 저장소
class NoteStore(object):

    def __init__(self, path=None):
        self.path = path or default_path()
        self.notes = {}             # id -> note
        self.error = ""             # 마지막 읽기 / 쓰기 문제 (UI 가 로그로 보여 준다)
        self.load()

    # ---------------------------------------------------------------- 파일
    def load(self):
        self.notes = {}
        if not os.path.isfile(self.path):
            return
        try:
            with open(self.path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, ValueError) as exc:
            self.error = "Could not read {0}: {1}".format(self.path, exc)
            backup = self.path + ".bak"
            if os.path.isfile(backup):                      # 깨졌으면 직전 파일로
                try:
                    with open(backup, "r", encoding="utf-8") as fh:
                        data = json.load(fh)
                    self.error += " - loaded the backup instead."
                except (OSError, ValueError):
                    return
            else:
                return
        for raw in data.get("notes", []):
            note = self._normalize(raw)
            if note is not None:
                self.notes[note["id"]] = note

    def save(self):
        folder = os.path.dirname(self.path)
        if folder and not os.path.isdir(folder):
            os.makedirs(folder)
        data = {"version": FILE_VERSION, "notes": sorted(self.notes.values(), key=lambda n: n["created"])}
        tmp = self.path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(data, fh, ensure_ascii=False, indent=1)
            if os.path.isfile(self.path):
                try:
                    os.replace(self.path, self.path + ".bak")
                except OSError:
                    pass
            os.replace(tmp, self.path)
            self.error = ""
            return True
        except OSError as exc:
            self.error = "Could not save {0}: {1}".format(self.path, exc)
            return False

    @staticmethod
    def _normalize(raw):
        if not isinstance(raw, dict) or not raw.get("id"):
            return None
        now = time.time()
        geo = raw.get("geometry")
        if not (isinstance(geo, (list, tuple)) and len(geo) == 4):
            geo = None
        color = raw.get("color") or DEFAULT_COLOR
        if color not in COLORS and not is_hex(color):
            color = DEFAULT_COLOR
        return {
            "id": str(raw["id"]),
            "html": str(raw.get("html") or ""),
            "text": str(raw.get("text") or ""),
            "color": color,
            "pinned": bool(raw.get("pinned", False)),
            "open": bool(raw.get("open", False)),
            "geometry": [int(v) for v in geo] if geo else None,
            "created": float(raw.get("created") or now),
            "modified": float(raw.get("modified") or raw.get("created") or now),
        }

    # ---------------------------------------------------------------- 노트
    def new_note(self, color=None, geometry=None):
        now = time.time()
        note = {"id": uuid.uuid4().hex, "html": "", "text": "", "color": color or DEFAULT_COLOR, "pinned": False,
                "open": True, "geometry": list(geometry) if geometry else None, "created": now, "modified": now}
        self.notes[note["id"]] = note
        return note

    def get(self, note_id):
        return self.notes.get(note_id)

    def set_content(self, note_id, html, text):
        """본문이 바뀌었을 때만 고치고 modified 를 올린다. 바뀌었으면 True."""
        note = self.notes.get(note_id)
        if note is None or (note["html"] == html and note["text"] == text):
            return False
        note["html"], note["text"] = html, text
        note["modified"] = time.time()
        return True

    def update(self, note_id, **fields):
        """색 · 핀 · 열림 · 위치 같은 것 (modified 는 안 올린다 - 목록 순서는 내용을 고친 시각)."""
        note = self.notes.get(note_id)
        if note is None:
            return False
        changed = False
        for key, value in fields.items():
            if key not in ("color", "pinned", "open", "geometry"):
                raise KeyError(key)
            if key == "geometry" and value is not None:
                value = [int(v) for v in value]
            if note.get(key) != value:
                note[key] = value
                changed = True
        return changed

    def delete(self, note_id):
        return self.notes.pop(note_id, None) is not None

    def is_empty(self, note_id):
        note = self.notes.get(note_id)
        return note is not None and not note["text"].strip()

    def ordered(self, query=""):
        """목록 순서: 최근에 고친 것이 위. query 는 공백으로 나눈 낱말이 모두 들어 있어야(대소문자 무시)."""
        words = [w.lower() for w in (query or "").split() if w]
        out = [n for n in self.notes.values() if all(w in n["text"].lower() for w in words)]
        return sorted(out, key=lambda n: n["modified"], reverse=True)


def preview(text, lines=3, width=120):
    """목록에 보일 앞부분 (빈 줄은 건너뛴다)."""
    rows = [r.strip() for r in (text or "").splitlines() if r.strip()]
    out = rows[:lines]
    joined = "\n".join(r if len(r) <= width else r[:width - 1] + "…" for r in out)
    return joined
