# -*- coding: utf-8 -*-
# Python Script by Ji Hun Park
# last Update date : 2026-11-23
# JUN_Memo - 노트 저장소 (Qt 비의존)
"""
노트 하나 = dict:
    id        : 고유 문자열 (uuid4 hex)
    scope     : "local" (이 PC 에서만) / "shared" (GitHub 로 공유 - 저장소 안 shared 폴더)
    title     : 제목 (v01.09 - 노트 위쪽 띠의 범위 배지 옆, 비어 있어도 된다)
    html      : 본문 (QTextEdit HTML)
    text      : 본문 글자만 (목록 미리보기 · 검색)
    color     : 색 이름(COLORS 키) 또는 "#rrggbb" (사용자 색)
    pinned    : 늘 맨 위 (Pin)                     ┐
    open      : 창이 열려 있었나                    ├ "보기 상태" - PC 마다 다르다
    geometry  : [x, y, w, h] 마지막 창 위치 · 크기 ┘
    created / modified : epoch 초

저장 위치 (v01.01 - 공유 / 이 PC 구분)
--------------------------------------
    local_dir (%APPDATA%/JUN_Memo)
        notes.json   : 이 PC 노트의 내용 (id · html · text · color · created · modified)
        state.json   : 보기 상태 - 노트마다 {open, pinned, geometry} (공유 노트 것도 여기), 목록 창 {color, pinned, geometry},
                       note_color (v01.08 새 노트의 기본 색 = 마지막으로 고른 노트 색),
                       order (v01.08 목록에서 끌어 놓아 정한 순서 - 노트 id 목록. PC 마다 다를 수 있다)
    shared_dir (저장소 안 shared/notes)
        <id>.json    : 공유 노트 하나 = 파일 하나 (내용만). v01.11 부터 html · text 는 줄 배열(git 충돌을 읽을 수 있게). 두 PC 가 **다른** 노트를 고치면 git 에서 충돌하지 않는다.
                       창을 옮기거나 Pin 해도 이 파일은 안 바뀐다(보기 상태는 state.json) - 공유 파일이 쓸데없이 바뀌지 않게.

v01.00 의 notes.json(보기 상태까지 한 파일)은 그대로 읽어 state.json 으로 나눈다.
쓰기는 임시 파일 → os.replace 로 한 번에(쓰다 꺼져도 깨지지 않게), notes.json · state.json 은 직전 파일을 .bak 으로 하나 남긴다.
공유 노트 파일은 **바뀐 것만** 다시 쓴다(git 에 안 바뀐 파일이 바뀐 것으로 보이지 않게).
"""

import json
import os
import time
import uuid

FILE_VERSION = 2
SCOPE_LOCAL = "local"
SCOPE_SHARED = "shared"
SCOPES = (SCOPE_LOCAL, SCOPE_SHARED)

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
#: v01.07 범위 배지 색 (꽉 찬 바탕 + 흰 글자 - 노트 7색 · 차콜 어디서나 보인다). Shared = 파랑, This PC = 초록.
SCOPE_COLORS = {"shared": "#1A73E8", "local": "#2E7D32"}
SCOPE_TEXT = {"shared": "Shared", "local": "This PC"}
DEFAULT_LIST_COLOR = "Gray"
CONTENT_KEYS = ("id", "title", "html", "text", "color", "created", "modified")
VIEW_KEYS = ("open", "pinned", "geometry", "zoom")
ZOOM_MIN, ZOOM_MAX, ZOOM_STEP = 0.6, 3.0, 0.1       # v01.05 글자 크기 배율 (노트마다 · 목록 창)


def clamp_zoom(value):
    try:
        v = float(value)
    except (TypeError, ValueError):
        return 1.0
    return round(min(ZOOM_MAX, max(ZOOM_MIN, v)), 2)


def default_local_dir():
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    return os.path.join(base, "JUN_Memo")


def default_shared_dir():
    """저장소 안 shared/notes (이 파일 기준 ../../shared/notes). 환경 변수 JUN_MEMO_SHARED 가 있으면 그것."""
    env = os.environ.get("JUN_MEMO_SHARED")
    if env:
        return env
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(root, "shared", "notes")


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


def is_color(color):
    return color in COLORS or is_hex(color)


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


SELECTION_BG = "#0078D7"        # Windows 선택 파랑
SELECTION_ALT = "#E67E00"       # 바탕이 그 파랑과 비슷할 때
SELECTION_FG = "#FFFFFF"


def selection_colors(color):
    """(선택 바탕, 선택 글자) - 불투명. v01.03: 반투명 검정은 다크 모드 팔레트와 섞여 끌어 고른 영역이 안 보였다(사용자).
    7색 모두 · 차콜과 대비가 큰 Windows 파랑, 사용자 색이 그 파랑과 비슷하면 주황."""
    body = palette(color)["body"]
    r, g, b = _hex_rgb(body)
    sr, sg, sb = _hex_rgb(SELECTION_BG)
    near = abs(r - sr) + abs(g - sg) + abs(b - sb) < 150
    return (SELECTION_ALT if near else SELECTION_BG), SELECTION_FG


# ---------------------------------------------------------------------- 파일
def _read_json(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _write_json(path, data, backup=False):
    folder = os.path.dirname(path)
    if folder and not os.path.isdir(folder):
        os.makedirs(folder)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1, sort_keys=True)
        fh.write("\n")
    if backup and os.path.isfile(path):
        try:
            os.replace(path, path + ".bak")
        except OSError:
            pass
    os.replace(tmp, path)


#: v01.11 공유 파일에서 줄 배열로 쓰는 키 - 문자열 하나면 본문 전체가 한 줄(수천 자)이라 git 병합 충돌을 사람이 못 읽었다.
#: 줄 배열이면 JSON 들여쓰기로 한 줄 = 한 원소가 되어 충돌이 바뀐 문단에만 난다.
LINE_KEYS = ("html", "text")


def _to_lines(value):
    """문자열 → 줄 배열. 줄바꿈 글자로만 나누므로 다시 이으면 정확히 돌아온다(끝의 빈 줄 · CR 도 그대로)."""
    return str(value or "").split("\n")


def _from_lines(value):
    """줄 배열(v01.11) 또는 문자열(옛 파일) → 문자열."""
    if isinstance(value, list):
        return "\n".join(str(v) for v in value)
    return str(value or "")


def _is_old_shared(raw):
    """v01.10 까지의 공유 파일 (html / text 가 한 줄 문자열) - 다음 저장 때 줄 배열로 다시 쓴다."""
    return isinstance(raw, dict) and any(isinstance(raw.get(k), str) for k in LINE_KEYS)


def _shared_file_data(payload):
    data = dict(payload)
    for k in LINE_KEYS:
        data[k] = _to_lines(data.get(k))
    return data


# ---------------------------------------------------------------------- 저장소
class NoteStore(object):

    def __init__(self, local_dir=None, shared_dir=None):
        """local_dir 에 notes.json · state.json, shared_dir 에 공유 노트 <id>.json.
        (v01.00 호환: local_dir 자리에 notes.json 파일 경로를 주면 그 폴더로 본다.)"""
        local_dir = local_dir or default_local_dir()
        if local_dir.lower().endswith(".json"):
            local_dir = os.path.dirname(local_dir)
        self.local_dir = local_dir
        self.shared_dir = shared_dir or default_shared_dir()
        self.notes = {}             # id -> note
        self.list_view = {"color": DEFAULT_LIST_COLOR, "pinned": False, "geometry": None, "shrunk": False, "zoom": 1.0,
                          "check_remote": True}       # v01.14 GitHub 확인(알림) 켜짐
        self.order = []                     # v01.08 끌어 놓아 정한 목록 순서 (id). 비어 있으면 최근에 고친 것이 위
        self.note_color = DEFAULT_COLOR     # v01.08 새 노트의 기본 색 - 마지막으로 고른(저장된) 노트 색을 따른다
        self.error = ""             # 마지막 읽기 / 쓰기 문제 (UI 가 로그로 보여 준다)
        self._shared_written = {}   # id -> 마지막으로 쓰거나 읽은 공유 파일 내용 (바뀐 것만 쓰기)
        self.load()

    @property
    def notes_path(self):
        return os.path.join(self.local_dir, "notes.json")

    @property
    def state_path(self):
        return os.path.join(self.local_dir, "state.json")

    def shared_path(self, note_id):
        return os.path.join(self.shared_dir, note_id + ".json")

    # ---------------------------------------------------------------- 읽기
    def _read_with_backup(self, path):
        if not os.path.isfile(path):
            return None
        try:
            return _read_json(path)
        except (OSError, ValueError) as exc:
            msg = "Could not read {0}: {1}".format(path, exc)
            if os.path.isfile(path + ".bak"):
                try:
                    data = _read_json(path + ".bak")
                    self.error = msg + " - loaded the backup instead."
                    return data
                except (OSError, ValueError):
                    pass
            self.error = msg
            return None

    def load(self):
        self.notes = {}
        self._shared_written = {}
        self.error = ""
        data = self._read_with_backup(self.notes_path) or {}
        view_from_old = {}
        for raw in data.get("notes", []):
            note = self._normalize(raw, SCOPE_LOCAL)
            if note is not None:
                self.notes[note["id"]] = note
                if any(k in raw for k in VIEW_KEYS):        # v01.00 파일 - 보기 상태도 같이 있었다
                    view_from_old[note["id"]] = {k: note[k] for k in VIEW_KEYS}
        if os.path.isdir(self.shared_dir):
            for name in sorted(os.listdir(self.shared_dir)):
                if not name.endswith(".json"):
                    continue
                path = os.path.join(self.shared_dir, name)
                try:
                    raw = _read_json(path)
                except (OSError, ValueError) as exc:
                    self.error = "Could not read the shared note {0}: {1}".format(name, exc)
                    continue
                note = self._normalize(raw, SCOPE_SHARED)
                if note is None:
                    continue
                if note["id"] in self.notes:                # 같은 id 가 둘 - 공유 쪽을 쓴다
                    self.notes.pop(note["id"])
                self.notes[note["id"]] = note
                # v01.11 옛 형식(한 줄 문자열)이면 None = 다음 저장 때 줄 배열로 다시 쓴다
                self._shared_written[note["id"]] = None if _is_old_shared(raw) else self._shared_payload(note)
        state = self._read_with_backup(self.state_path) or {}
        views = state.get("notes", {}) if isinstance(state.get("notes"), dict) else {}
        for note_id, note in self.notes.items():
            view = views.get(note_id) or view_from_old.get(note_id) or {}
            note["open"] = bool(view.get("open", False))
            note["pinned"] = bool(view.get("pinned", False))
            geo = view.get("geometry")
            note["geometry"] = [int(v) for v in geo] if isinstance(geo, (list, tuple)) and len(geo) == 4 else None
            note["zoom"] = clamp_zoom(view.get("zoom", 1.0))
        lv = state.get("list") if isinstance(state.get("list"), dict) else {}
        geo = lv.get("geometry")
        self.list_view = {"color": lv.get("color") if is_color(lv.get("color")) else DEFAULT_LIST_COLOR,
                          "pinned": bool(lv.get("pinned", False)),
                          "shrunk": bool(lv.get("shrunk", False)),
                          "zoom": clamp_zoom(lv.get("zoom", 1.0)),
                          "check_remote": bool(lv.get("check_remote", True)),       # v01.14
                          "geometry": [int(v) for v in geo] if isinstance(geo, (list, tuple)) and len(geo) == 4 else None}
        order = state.get("order")
        self.order = [str(i) for i in order if str(i) in self.notes] if isinstance(order, list) else []
        # v01.08 새 노트 기본 색: state.json 의 note_color → 없으면(옛 파일) 가장 최근에 고친 노트 색 → 노랑
        saved = state.get("note_color")
        if is_color(saved):
            self.note_color = saved
        elif self.notes:
            self.note_color = max(self.notes.values(), key=lambda n: n["modified"])["color"]
        else:
            self.note_color = DEFAULT_COLOR

    @staticmethod
    def _normalize(raw, scope):
        if not isinstance(raw, dict) or not raw.get("id"):
            return None
        now = time.time()
        geo = raw.get("geometry")
        color = raw.get("color") or DEFAULT_COLOR
        return {
            "id": str(raw["id"]),
            "scope": scope,
            "title": str(raw.get("title") or ""),
            "html": _from_lines(raw.get("html")),            # v01.11 줄 배열 또는 옛 문자열
            "text": _from_lines(raw.get("text")),
            "color": color if is_color(color) else DEFAULT_COLOR,
            "pinned": bool(raw.get("pinned", False)),
            "open": bool(raw.get("open", False)),
            "geometry": [int(v) for v in geo] if isinstance(geo, (list, tuple)) and len(geo) == 4 else None,
            "zoom": clamp_zoom(raw.get("zoom", 1.0)),
            "created": float(raw.get("created") or now),
            "modified": float(raw.get("modified") or raw.get("created") or now),
        }

    @staticmethod
    def _shared_payload(note):
        return {k: note[k] for k in CONTENT_KEYS}

    # ---------------------------------------------------------------- 쓰기
    def save(self):
        """이 PC 노트 · 보기 상태 · 바뀐 공유 노트를 쓴다. 성공하면 True (실패는 self.error)."""
        ok = True
        try:
            local = [self._shared_payload(n) for n in sorted(self.notes.values(), key=lambda n: n["created"])
                     if n["scope"] == SCOPE_LOCAL]
            _write_json(self.notes_path, {"version": FILE_VERSION, "notes": local}, backup=True)
            views = {i: {k: n[k] for k in VIEW_KEYS} for i, n in self.notes.items()}
            _write_json(self.state_path, {"version": FILE_VERSION, "notes": views, "list": dict(self.list_view),
                                          "note_color": self.note_color,
                                          "order": [i for i in self.order if i in self.notes]},
                        backup=True)
        except OSError as exc:
            self.error = "Could not save in {0}: {1}".format(self.local_dir, exc)
            ok = False
        for note_id, note in self.notes.items():
            if note["scope"] != SCOPE_SHARED:
                continue
            payload = self._shared_payload(note)
            if self._shared_written.get(note_id) == payload:
                continue                                    # 안 바뀐 공유 파일은 건드리지 않는다
            try:
                _write_json(self.shared_path(note_id), _shared_file_data(payload))      # v01.11 본문은 줄 배열
                self._shared_written[note_id] = payload
            except OSError as exc:
                self.error = "Could not save the shared note {0}: {1}".format(note_id, exc)
                ok = False
        for note_id in [i for i in self._shared_written if i not in self.notes or
                        self.notes[i]["scope"] != SCOPE_SHARED]:
            try:                                            # 지웠거나 이 PC 로 옮긴 공유 노트 = 파일 지우기
                if os.path.isfile(self.shared_path(note_id)):
                    os.remove(self.shared_path(note_id))
                self._shared_written.pop(note_id, None)
            except OSError as exc:
                self.error = "Could not remove the shared note {0}: {1}".format(note_id, exc)
                ok = False
        if ok:
            self.error = ""
        return ok

    # ---------------------------------------------------------------- 노트
    def new_note(self, color=None, geometry=None, scope=SCOPE_LOCAL):
        now = time.time()
        note = {"id": uuid.uuid4().hex, "scope": scope if scope in SCOPES else SCOPE_LOCAL, "title": "", "html": "", "text": "",
                "color": color if is_color(color) else self.note_color, "pinned": False, "open": True,
                "geometry": list(geometry) if geometry else None, "zoom": 1.0, "created": now, "modified": now}
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

    def set_title(self, note_id, title):
        """v01.09 제목 - 내용이므로 바뀌면 modified 를 올린다(공유 노트면 공유 파일에 들어간다). 바뀌었으면 True."""
        note = self.notes.get(note_id)
        title = " ".join(str(title or "").split())          # 한 줄로 (줄바꿈 · 겹친 공백 없이)
        if note is None or note["title"] == title:
            return False
        note["title"] = title
        note["modified"] = time.time()
        return True

    def update(self, note_id, **fields):
        """색 · 핀 · 열림 · 위치 · 범위 (modified 는 안 올린다 - 목록 순서는 내용을 고친 시각)."""
        note = self.notes.get(note_id)
        if note is None:
            return False
        changed = False
        for key, value in fields.items():
            if key not in ("color", "pinned", "open", "geometry", "scope", "zoom"):
                raise KeyError(key)
            if key == "geometry" and value is not None:
                value = [int(v) for v in value]
            if key == "zoom":
                value = clamp_zoom(value)
            if key == "scope" and value not in SCOPES:
                raise ValueError(value)
            if key == "color" and is_color(value):
                self.note_color = value                     # v01.08 고른 색 = 다음 새 노트의 기본 색
            if note.get(key) != value:
                note[key] = value
                changed = True
        return changed

    def delete(self, note_id):
        return self.notes.pop(note_id, None) is not None

    def is_empty(self, note_id):
        note = self.notes.get(note_id)
        return note is not None and not note["text"].strip() and not note["title"].strip()

    def ordered(self, query="", scope=None):
        """목록 순서. query = 공백으로 나눈 낱말이 모두(대소문자 무시). scope = None(전부) / local / shared.

        v01.08: 끌어 놓아 정한 순서(self.order)가 있으면 그 순서. 그 순서에 없는 노트(새 노트 · 다른 PC 에서 온 공유 노트)는
        맨 위에, 그것들끼리는 최근에 고친 것이 위. 순서를 한 번도 안 정했으면 예전처럼 최근에 고친 것이 위."""
        words = [w.lower() for w in (query or "").split() if w]
        out = [n for n in self.notes.values() if all(w in (n["title"] + "\n" + n["text"]).lower() for w in words) and
               (scope is None or n["scope"] == scope)]
        rank = {note_id: i for i, note_id in enumerate(self.order)}
        return sorted(out, key=lambda n: (1, rank[n["id"]], 0) if n["id"] in rank else (0, 0, -n["modified"]))

    def set_order(self, visible_ids):
        """목록에서 끌어 놓은 뒤 보이는 순서(visible_ids)를 저장한다. 바뀌었으면 True.

        검색 · 범위로 걸러 일부만 보일 때도 된다 - 전체 순서에서 보이던 노트들이 있던 자리에 새 순서대로 다시 넣고,
        안 보이던 노트는 제자리에 둔다."""
        full = [n["id"] for n in self.ordered()]
        visible = [i for i in visible_ids if i in self.notes]
        seen = set(visible)
        if len(seen) != len(visible):
            return False
        it = iter(visible)
        new = [next(it) if note_id in seen else note_id for note_id in full]
        if new == self.order:
            return False
        self.order = new
        return True

    def reload_shared(self, include_open=False):
        """공유 폴더를 다시 읽는다 (git pull 뒤). 열린 창이 없는 공유 노트만 바뀐다 - 고치는 중인 노트는 건드리지 않는다.
        돌려주는 값: (새로 생긴 수, 바뀐 수, 없어진 수).

        v01.13 include_open=True (Pull Shared) - 열린 공유 노트도 디스크 내용으로 바꾼다. Pull 은 받기 전에 열린 노트를
        저장하고 autostash 로 합치므로 디스크 쪽이 '받은 것 + 이 PC 에서 고친 것' 이다. 열린 노트를 그대로 두면
        다음 저장이 옛 내용으로 받은 것을 덮는다. 바뀐 열린 노트 id 는 self.reloaded_open 에 (창을 다시 열어야)."""
        self.reloaded_open = []
        on_disk = {}
        if os.path.isdir(self.shared_dir):
            for name in os.listdir(self.shared_dir):
                if name.endswith(".json"):
                    try:
                        note = self._normalize(_read_json(os.path.join(self.shared_dir, name)), SCOPE_SHARED)
                    except (OSError, ValueError):
                        continue
                    if note is not None:
                        on_disk[note["id"]] = note
        added = changed = removed = 0
        for note_id, fresh in on_disk.items():
            cur = self.notes.get(note_id)
            payload = self._shared_payload(fresh)
            if cur is None:
                self.notes[note_id] = fresh
                added += 1
            elif cur["scope"] == SCOPE_SHARED and (include_open or not cur["open"]) and \
                    self._shared_payload(cur) != payload:
                for k in CONTENT_KEYS:
                    cur[k] = fresh[k]
                changed += 1
                if cur["open"]:
                    self.reloaded_open.append(note_id)
            self._shared_written[note_id] = payload
        for note_id in [i for i, n in self.notes.items() if n["scope"] == SCOPE_SHARED and i not in on_disk
                        and not n["open"]]:
            self.notes.pop(note_id)
            self._shared_written.pop(note_id, None)
            removed += 1
        return added, changed, removed


def preview(text, lines=3, width=120):
    """목록에 보일 앞부분 (빈 줄은 건너뛴다)."""
    rows = [r.strip() for r in (text or "").splitlines() if r.strip()]
    out = rows[:lines]
    joined = "\n".join(r if len(r) <= width else r[:width - 1] + "…" for r in out)
    return joined
