# -*- coding: utf-8 -*-
# Python Script by Ji Hun Park
# last Update date : 2026-11-23 (v01.01)
# JUN_Memo - 스티커 노트 창 하나
"""
윈도우 스티커 메모처럼 생긴 노트 창. 테두리 없는 창 + 색 띠(위) + 본문 + 서식 줄(아래).

    위쪽 띠 : [+] 새 노트 · 범위 표시(Shared / This PC, v01.01) · (띠를 잡고 끌면 창 이동) · [Pin] 늘 맨 위 ·
              [...] 색 / Shared (GitHub) 켜고 끄기 / Notes list / Delete · [x] 닫기
    본문    : 서식 있는 글 (붙여 넣기는 글자만 - 다른 프로그램의 배경색 · 글꼴이 색 노트를 깨지 않게)
    아래    : B I U S • (Ctrl+B / I / U / T / Shift+L) · 오른쪽 아래 모서리 = 크기 조절

모든 UI 문자열은 영어 (한국어는 주석만).
"""

import re

from PySide6.QtCore import QEvent, QPoint, QSize, Qt, QTimer, Signal
from PySide6.QtGui import (QAction, QColor, QFont, QKeySequence, QPalette, QShortcut, QTextCharFormat, QTextCursor,
                           QTextFormat, QTextListFormat)
from PySide6.QtWidgets import (QColorDialog, QFrame, QHBoxLayout, QLabel, QLineEdit, QMenu, QMessageBox, QSizeGrip,
                               QTextEdit, QToolButton, QVBoxLayout, QWidget, QWidgetAction, QGridLayout)

from app.core import store as st

DEFAULT_SIZE = QSize(320, 320)
BASE_PT = 11.0              # 글자 크기 100% (v01.05 - 배율을 곱한다)
_BODY_SIZE = re.compile(r"(<body\b[^>]*style=\"[^\"]*?)\s*font-size:[^;\"]*;?", re.IGNORECASE)


SIZE_MIN, SIZE_MAX = -1, 3  # v01.06 고른 글자 크기 단계 (small · medium · large · x-large · xx-large) - 그 밖은 HTML 로 안 남는다


def _clamp_size(level):
    return max(SIZE_MIN, min(SIZE_MAX, int(level)))


def note_font(zoom):
    """본문 글꼴. QFont("Segoe UI", 13.2) 는 크기를 정수로 자른다(13) - setPointSizeF 로 소수 크기 (v01.05 시험이 잡음)."""
    f = QFont("Segoe UI")
    f.setPointSizeF(BASE_PT * zoom)
    return f


def strip_base_size(html):
    """HTML <body style> 의 font-size 를 뺀다 - 남아 있으면 setHtml 이 글자마다 그 크기를 박아 배율이 안 먹는다(v01.05 실측)."""
    return _BODY_SIZE.sub(r"\1", html or "")
MIN_SIZE = QSize(200, 140)
PIN_ON = "#FFB3B3"          # 켜진 Pin = 연한 빨강 (JUN 툴들과 같은 표시)


class _Editor(QTextEdit):
    """붙여 넣기는 글자만."""

    def insertFromMimeData(self, source):
        if source.hasText():
            self.insertPlainText(source.text())
        else:
            super().insertFromMimeData(source)


class _Header(QFrame):
    """위쪽 색 띠 - 잡고 끌면 창이 움직인다, 더블클릭은 무시(스티커는 최대화가 없다)."""

    def __init__(self, window):
        super().__init__(window)
        self._window = window
        self._grab = None

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._grab = event.globalPosition().toPoint() - self._window.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._grab is not None and event.buttons() & Qt.LeftButton:
            self._window.move(event.globalPosition().toPoint() - self._grab)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._grab = None


class NoteWindow(QWidget):
    """노트 하나. controller 가 만들고 저장 · 목록 갱신을 맡는다."""

    contentChanged = Signal(str)            # 노트 id - 글이 바뀜 (controller 가 모아서 저장)
    geometryChanged = Signal(str)
    closedByUser = Signal(str)
    newNoteRequested = Signal(str)          # 이 노트 옆에 새 노트
    listRequested = Signal()
    deleteRequested = Signal(str)
    colorChanged = Signal(str, str)
    pinChanged = Signal(str, bool)
    scopeChanged = Signal(str, str)         # v01.01 노트 id, "shared" / "local"
    zoomChanged = Signal(str, float)        # v01.05 노트 id, 글자 크기 배율
    titleChanged = Signal(str, str)         # v01.09 노트 id, 제목

    def __init__(self, note):
        super().__init__(None, Qt.Window | Qt.FramelessWindowHint)
        self.note_id = note["id"]
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self.setMinimumSize(MIN_SIZE)
        self._loading = True
        self._closing_quietly = False
        self.color = note["color"]
        self.pinned = False
        self.scope = note.get("scope", st.SCOPE_LOCAL)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ---- 위쪽 띠
        self.header = _Header(self)
        self.header.setObjectName("noteHeader")
        self.header.setFixedHeight(34)
        hl = QHBoxLayout(self.header)
        hl.setContentsMargins(4, 0, 4, 0)
        hl.setSpacing(2)
        self.btn_new = self._tool("+", "New note (Ctrl+N)")
        self.btn_new.clicked.connect(lambda: self.newNoteRequested.emit(self.note_id))
        hl.addWidget(self.btn_new)
        self.lbl_scope = QLabel(self.header)
        self.lbl_scope.setObjectName("scopeTag")
        self.lbl_scope.setToolTip("Shared: kept in the GitHub repository (shared/notes).\n"
                                  "This PC: kept only on this computer.\nChange it in the ... menu.")
        self.lbl_scope.setFixedHeight(18)
        hl.addWidget(self.lbl_scope, 0, Qt.AlignVCenter)
        # v01.09 제목 - 범위 배지 옆. 띠의 빈 곳은 그대로 끌어서 창을 옮길 수 있다
        self.ipf_title = QLineEdit(self.header)
        self.ipf_title.setObjectName("noteTitle")
        self.ipf_title.setPlaceholderText("Title")
        self.ipf_title.setToolTip("Title of this note (shown in the notes list and searched too).")
        self.ipf_title.setFrame(False)
        self.ipf_title.setFixedHeight(22)
        self.ipf_title.setMinimumWidth(40)
        self.ipf_title.setText(note.get("title", ""))
        self.ipf_title.textEdited.connect(self._on_title_edited)
        self.ipf_title.returnPressed.connect(lambda: self.editor.setFocus())
        hl.addSpacing(4)
        hl.addWidget(self.ipf_title, 1, Qt.AlignVCenter)
        self.btn_pin = self._tool("Pin", "Keep this note on top of other windows")
        self.btn_pin.setCheckable(True)
        self.btn_pin.toggled.connect(self._on_pin_clicked)
        hl.addWidget(self.btn_pin)
        self.btn_menu = self._tool("…", "Color, notes list, delete")
        self.btn_menu.setPopupMode(QToolButton.InstantPopup)
        self.btn_menu.setMenu(self._build_menu())
        hl.addWidget(self.btn_menu)
        self.btn_close = self._tool("✕", "Close this note (it stays in the notes list)")
        self.btn_close.clicked.connect(self.close)
        hl.addWidget(self.btn_close)
        root.addWidget(self.header)

        # ---- 본문
        self.editor = _Editor(self)
        self.editor.setObjectName("noteEditor")
        self.editor.setFrameShape(QFrame.NoFrame)
        self.editor.setPlaceholderText("Take a note...")
        self.editor.setAcceptRichText(True)
        self.zoom = st.clamp_zoom(note.get("zoom", 1.0))
        self.editor.document().setDefaultFont(note_font(self.zoom))
        # v01.05 - 저장된 HTML 의 기본 글자 크기를 빼고 읽는다(남겨 두면 글자마다 11pt 로 박혀 크기 조절이 안 먹는다 - 실측)
        self.editor.setHtml(strip_base_size(note["html"])) if note["html"] else self.editor.setPlainText(note["text"])
        self.editor.viewport().installEventFilter(self)          # Ctrl + 휠 = 글자 크기
        self.editor.textChanged.connect(self._on_text_changed)
        root.addWidget(self.editor, 1)

        # ---- 아래 서식 줄 + 크기 손잡이
        self.footer = QFrame(self)
        self.footer.setObjectName("noteFooter")
        fl = QHBoxLayout(self.footer)
        fl.setContentsMargins(4, 0, 0, 0)
        fl.setSpacing(2)
        self.fmt_buttons = {}
        for key, label, tip in (("bold", "B", "Bold (Ctrl+B)"), ("italic", "I", "Italic (Ctrl+I)"),
                                ("underline", "U", "Underline (Ctrl+U)"), ("strike", "S", "Strikethrough (Ctrl+T)"),
                                ("bullet", "•", "Bullets (Ctrl+Shift+L)")):
            b = self._tool(label, tip)
            f = b.font()
            f.setBold(key == "bold")
            f.setItalic(key == "italic")
            f.setUnderline(key == "underline")
            f.setStrikeOut(key == "strike")
            b.setFont(f)
            b.clicked.connect(lambda _=False, k=key: self.apply_format(k))
            self.fmt_buttons[key] = b
            fl.addWidget(b)
        # v01.06 고른 글자만 크기: T- / T+ (작게 · 보통 · 크게 · 더 크게 · 가장 크게 - 노트 전체 배율과 곱해진다)
        for key, label, tip in (("size_down", "T−", "Selected text smaller (Ctrl+Shift+,)\n"
                                                    "Nothing selected: the text you type next."),
                                ("size_up", "T+", "Selected text larger (Ctrl+Shift+.)\n"
                                                  "Nothing selected: the text you type next.")):
            b = self._tool(label, tip)
            b.clicked.connect(lambda _=False, k=key: self.apply_format(k))
            self.fmt_buttons[key] = b
            fl.addWidget(b)
        fl.addStretch(1)
        # v01.05 글자 크기: A- [100%] A+  (Ctrl + 휠 · Ctrl+= / Ctrl+- · Ctrl+0)
        self.btn_smaller = self._tool("A−", "Smaller text (Ctrl+- or Ctrl + mouse wheel down)")
        self.btn_smaller.clicked.connect(lambda: self.step_zoom(-1))
        fl.addWidget(self.btn_smaller)
        self.btn_zoom = self._tool("100%", "Text size - click for 100% (Ctrl+0)")
        self.btn_zoom.setMinimumWidth(40)
        self.btn_zoom.clicked.connect(lambda: self.set_zoom(1.0))
        fl.addWidget(self.btn_zoom)
        self.btn_larger = self._tool("A+", "Larger text (Ctrl+= or Ctrl + mouse wheel up)")
        self.btn_larger.clicked.connect(lambda: self.step_zoom(1))
        fl.addWidget(self.btn_larger)
        self.grip = QSizeGrip(self.footer)
        fl.addWidget(self.grip, 0, Qt.AlignBottom | Qt.AlignRight)
        root.addWidget(self.footer)

        for seq, key in (("Ctrl+B", "bold"), ("Ctrl+I", "italic"), ("Ctrl+U", "underline"), ("Ctrl+T", "strike"),
                         ("Ctrl+Shift+L", "bullet"), ("Ctrl+Shift+,", "size_down"), ("Ctrl+Shift+.", "size_up"),
                         ("Ctrl+<", "size_down"), ("Ctrl+>", "size_up")):
            QShortcut(QKeySequence(seq), self, activated=lambda k=key: self.apply_format(k))
        QShortcut(QKeySequence("Ctrl+N"), self, activated=lambda: self.newNoteRequested.emit(self.note_id))
        for seq, step in (("Ctrl+=", 1), ("Ctrl++", 1), ("Ctrl+-", -1)):
            QShortcut(QKeySequence(seq), self, activated=lambda s=step: self.step_zoom(s))
        QShortcut(QKeySequence("Ctrl+0"), self, activated=lambda: self.set_zoom(1.0))

        self._geo_timer = QTimer(self)
        self._geo_timer.setSingleShot(True)
        self._geo_timer.setInterval(300)
        self._geo_timer.timeout.connect(lambda: self.geometryChanged.emit(self.note_id))

        self.set_color(note["color"], emit=False)
        self.set_pinned(note["pinned"], emit=False)
        self.set_zoom(self.zoom, emit=False)
        self.set_scope(self.scope, emit=False)
        geo = note.get("geometry")
        if geo:
            self.setGeometry(geo[0], geo[1], max(geo[2], MIN_SIZE.width()), max(geo[3], MIN_SIZE.height()))
        else:
            self.resize(DEFAULT_SIZE)
        self.setWindowTitle(self._title())
        self._loading = False

    # ---------------------------------------------------------------- 만들기
    def _tool(self, text, tip):
        b = QToolButton(self)
        b.setText(text)
        b.setToolTip(tip)
        b.setAutoRaise(True)
        b.setFixedHeight(28)
        b.setMinimumWidth(28)
        b.setCursor(Qt.PointingHandCursor)
        return b

    def _build_menu(self):
        menu = QMenu(self)
        # 색 견본 (윈도우 스티커 메모처럼 한 줄)
        holder = QWidget(menu)
        grid = QGridLayout(holder)
        grid.setContentsMargins(8, 6, 8, 6)
        grid.setSpacing(4)
        self.swatches = {}
        for i, (name, pal) in enumerate(st.COLORS.items()):
            b = QToolButton(holder)
            b.setFixedSize(30, 30)
            b.setToolTip(name)
            b.setStyleSheet("QToolButton {{ background: {0}; border: 1px solid #00000033; }}"
                            "QToolButton:hover {{ border: 2px solid #00000088; }}".format(pal["header"]))
            b.clicked.connect(lambda _=False, n=name: (self.set_color(n), menu.close()))
            grid.addWidget(b, 0, i)
            self.swatches[name] = b
        act = QWidgetAction(menu)
        act.setDefaultWidget(holder)
        menu.addAction(act)
        self.act_custom = QAction("Custom color...", menu)
        self.act_custom.triggered.connect(self.pick_custom_color)
        menu.addAction(self.act_custom)
        menu.addSeparator()
        self.act_shared = QAction("Shared (GitHub)", menu)
        self.act_shared.setCheckable(True)
        self.act_shared.setToolTip("On: the note is kept in the GitHub repository (shared/notes).\n"
                                   "Off: kept only on this computer.")
        self.act_shared.triggered.connect(lambda on: self.set_scope(st.SCOPE_SHARED if on else st.SCOPE_LOCAL))
        menu.addAction(self.act_shared)
        menu.addSeparator()
        self.act_list = QAction("Notes list", menu)
        self.act_list.triggered.connect(self.listRequested.emit)
        menu.addAction(self.act_list)
        self.act_delete = QAction("Delete note", menu)
        self.act_delete.triggered.connect(self._on_delete)
        menu.addAction(self.act_delete)
        return menu

    def _title(self):
        first = self.ipf_title.text().strip() or st.preview(self.editor.toPlainText(), lines=1, width=40)
        return "JUN Memo - " + (first or "New note")

    def note_title(self):
        return self.ipf_title.text()

    def set_note_title(self, title):
        """v01.09 밖(다시 읽은 공유 노트 등)에서 제목을 바꿀 때 - 신호 없이."""
        if self.ipf_title.text() != title:
            self.ipf_title.setText(title)
        self.setWindowTitle(self._title())

    def _on_title_edited(self, text):
        self.setWindowTitle(self._title())
        if not self._loading:
            self.titleChanged.emit(self.note_id, text)

    # ---------------------------------------------------------------- 색 · 핀
    def set_color(self, color, emit=True):
        pal = st.palette(color)
        self.color = color
        sel_bg, sel_fg = st.selection_colors(color)
        self.setStyleSheet(
            "NoteWindow {{ background: {body}; border: 1px solid #00000040; }}"
            "#noteHeader {{ background: {header}; }}"
            "#noteFooter {{ background: {body}; }}"
            "#noteEditor {{ background: {body}; color: {text}; border: none; padding: 6px 10px; "
            "selection-background-color: {sel_bg}; selection-color: {sel_fg}; }}"
            "QToolButton {{ color: {text}; background: transparent; border: none; font-size: 13px; padding: 0 6px; }}"
            "QToolButton:hover {{ background: #0000001F; }}"
            "QToolButton:checked {{ background: {pin}; color: #202020; }}"
            "QToolButton::menu-indicator {{ image: none; width: 0; }}"
            # v01.06 아래 줄은 버튼이 많아(서식 5 + 고른 글자 크기 2 + 전체 크기 3) 여백을 줄인다 - 100% 가 ... 로 잘렸다
            "#noteFooter QToolButton {{ padding: 0 3px; min-width: 20px; }}"
            # v01.09 제목칸 - 띠와 같은 바탕, 굵은 글자. 고칠 때만 옅은 테두리
            "#noteTitle {{ background: transparent; color: {text}; border: 1px solid transparent; border-radius: 3px; "
            "padding: 0 4px; font-size: 13px; font-weight: bold; "
            "selection-background-color: {sel_bg}; selection-color: {sel_fg}; }}"
            "#noteTitle:hover, #noteTitle:focus {{ border-color: #00000040; background: {body}; }}"
            .format(pin=PIN_ON, sel_bg=sel_bg, sel_fg=sel_fg, **pal))
        # 범위 배지는 범위 색으로 따로 칠한다 (v01.07 - set_scope)
        # 팔레트에도 같은 선택 색 - 창이 포커스를 잃었을 때(Inactive)도 선택이 보이게 (스타일시트만으로는 비활성 색이 남는다)
        qp = self.editor.palette()
        for group in (QPalette.Active, QPalette.Inactive):
            qp.setColor(group, QPalette.Highlight, QColor(sel_bg))
            qp.setColor(group, QPalette.HighlightedText, QColor(sel_fg))
        self.editor.setPalette(qp)
        if emit and not self._loading:
            self.colorChanged.emit(self.note_id, color)

    def set_scope(self, scope, emit=True):
        """Shared (GitHub) / This PC - 표시와 메뉴 체크."""
        self.scope = scope if scope in st.SCOPES else st.SCOPE_LOCAL
        self.lbl_scope.setText(st.SCOPE_TEXT[self.scope])
        # v01.07 Shared = 파랑, This PC = 초록 배지 (사용자: 노트마다 색으로 구분되게)
        self.lbl_scope.setStyleSheet(
            "QLabel {{ background: {0}; color: #FFFFFF; border: none; border-radius: 3px; padding: 0 6px; "
            "font-size: 9px; font-weight: bold; }}".format(st.SCOPE_COLORS[self.scope]))
        self.act_shared.setChecked(self.scope == st.SCOPE_SHARED)
        if emit and not self._loading:
            self.scopeChanged.emit(self.note_id, self.scope)

    def pick_custom_color(self):
        start = QColor(st.palette(self.color)["body"])
        color = QColorDialog.getColor(start, self, "Note color")
        if color.isValid():
            self.set_color(color.name().upper())

    def _on_pin_clicked(self, on):
        self.set_pinned(on)

    def set_pinned(self, on, emit=True):
        """늘 맨 위. 창 플래그를 바꾸면 Qt 가 창을 숨기므로 보이던 창이면 다시 보인다."""
        on = bool(on)
        self.pinned = on
        if self.btn_pin.isChecked() != on:
            self.btn_pin.blockSignals(True)
            self.btn_pin.setChecked(on)
            self.btn_pin.blockSignals(False)
        self.btn_pin.setText("Pinned" if on else "Pin")
        visible = self.isVisible()
        geo = self.geometry()
        self.setWindowFlag(Qt.WindowStaysOnTopHint, on)
        if visible:
            self.setGeometry(geo)
            self.show()
        if emit and not self._loading:
            self.pinChanged.emit(self.note_id, on)

    # ---------------------------------------------------------------- 서식
    def apply_format(self, key):
        cursor = self.editor.textCursor()
        if key == "bullet":
            if cursor.currentList() is not None:            # 이미 글머리표면 고른 줄 모두 풀기
                doc = self.editor.document()
                first = doc.findBlock(cursor.selectionStart())
                last = doc.findBlock(cursor.selectionEnd())
                block = first
                while block.isValid():
                    lst = block.textList()
                    if lst is not None:
                        lst.remove(block)
                        c = QTextCursor(block)
                        fmt = block.blockFormat()
                        fmt.setIndent(0)
                        fmt.setObjectIndex(-1)              # 목록 연결까지 끊는다 (remove 만으로는 남는다)
                        c.setBlockFormat(fmt)
                    if block == last:
                        break
                    block = block.next()
            else:
                cursor.createList(QTextListFormat.ListDisc)
            self.editor.setFocus()
            return
        if key in ("size_up", "size_down"):
            self.step_selection_size(1 if key == "size_up" else -1)
            return
        fmt = QTextCharFormat()
        now = self.editor.currentCharFormat()
        if key == "bold":
            fmt.setFontWeight(QFont.Normal if now.fontWeight() > QFont.Normal else QFont.Bold)
        elif key == "italic":
            fmt.setFontItalic(not now.fontItalic())
        elif key == "underline":
            fmt.setFontUnderline(not now.fontUnderline())
        elif key == "strike":
            fmt.setFontStrikeOut(not now.fontStrikeOut())
        cursor.mergeCharFormat(fmt)
        self.editor.mergeCurrentCharFormat(fmt)
        self.editor.setFocus()

    def step_selection_size(self, step):
        """고른 글자만 한 단계 크게 / 작게 (v01.06, 사용자 요청 - 끌어 고른 글자만).

        크기는 몇 pt 가 아니라 **상대 단계**(QTextFormat.FontSizeAdjustment)로 준다 - 노트 전체 배율(A- / A+)과 곱해져 함께 커진다.
        단계는 SIZE_MIN ~ SIZE_MAX (작게 · 보통 · 크게 · 더 크게 · 가장 크게) - 그 밖의 값은 HTML 로 저장되지 않는다(실측).
        고른 범위에 크기가 섞여 있으면 글자 조각마다 한 단계씩(Word 의 글꼴 키우기와 같다). 고른 것이 없으면 이어서 칠 글자.
        """
        cursor = self.editor.textCursor()
        if not cursor.hasSelection():
            now = self.editor.currentCharFormat().intProperty(QTextFormat.FontSizeAdjustment)
            fmt = QTextCharFormat()
            fmt.setProperty(QTextFormat.FontSizeAdjustment, _clamp_size(now + step))
            self.editor.mergeCurrentCharFormat(fmt)
            self.editor.setFocus()
            return
        start, end = cursor.selectionStart(), cursor.selectionEnd()
        doc = self.editor.document()
        runs = []                                   # (시작, 끝, 지금 단계) - 먼저 다 모은 뒤 바꾼다(바꾸는 중 조각이 쪼개진다)
        block = doc.findBlock(start)
        while block.isValid() and block.position() <= end:
            it = block.begin()
            while not it.atEnd():
                frag = it.fragment()
                a, b = max(frag.position(), start), min(frag.position() + frag.length(), end)
                if a < b:
                    runs.append((a, b, frag.charFormat().intProperty(QTextFormat.FontSizeAdjustment)))
                it += 1
            block = block.next()
        edit = QTextCursor(doc)
        edit.beginEditBlock()                       # Ctrl+Z 한 번에
        for a, b, now in runs:
            edit.setPosition(a)
            edit.setPosition(b, QTextCursor.KeepAnchor)
            fmt = QTextCharFormat()
            fmt.setProperty(QTextFormat.FontSizeAdjustment, _clamp_size(now + step))
            edit.mergeCharFormat(fmt)
        edit.endEditBlock()
        self.editor.setFocus()

    # ---------------------------------------------------------------- 이벤트
    def _on_text_changed(self):
        if self._loading:
            return
        self.setWindowTitle(self._title())
        self.contentChanged.emit(self.note_id)

    # ---------------------------------------------------------------- 글자 크기 (v01.05)
    def set_zoom(self, value, emit=True):
        """본문 글자 크기 배율 (기본 11pt x 배율). 이 PC 의 보기 설정이라 공유 노트 파일은 안 바뀐다."""
        value = st.clamp_zoom(value)
        self.zoom = value
        self.editor.document().setDefaultFont(note_font(value))
        self.btn_zoom.setText("{0}%".format(int(round(value * 100))))
        self.btn_smaller.setEnabled(value > st.ZOOM_MIN + 1e-9)
        self.btn_larger.setEnabled(value < st.ZOOM_MAX - 1e-9)
        if emit and not self._loading:
            self.zoomChanged.emit(self.note_id, value)

    def step_zoom(self, steps):
        self.set_zoom(self.zoom + steps * st.ZOOM_STEP)

    def eventFilter(self, obj, event):
        if obj is self.editor.viewport() and event.type() == QEvent.Wheel and event.modifiers() & Qt.ControlModifier:
            dy = event.angleDelta().y()
            if dy:
                self.step_zoom(1 if dy > 0 else -1)
            return True                                          # 스크롤 대신 크기만
        return super().eventFilter(obj, event)

    def content(self):
        """(html, 글자만). 빈 노트는 html 도 비운다."""
        text = self.editor.toPlainText()
        return (strip_base_size(self.editor.toHtml()) if text.strip() else ""), text

    def _on_delete(self):
        answer = QMessageBox.question(self, "Delete note", "Delete this note?",
                                      QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if answer == QMessageBox.Yes:
            self.deleteRequested.emit(self.note_id)

    def close_quietly(self):
        """목록에서 지울 때 등 - 닫힘을 '사용자가 닫음' 으로 알리지 않는다."""
        self._closing_quietly = True
        self.close()

    def moveEvent(self, event):
        super().moveEvent(event)
        if not self._loading:
            self._geo_timer.start()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if not self._loading:
            self._geo_timer.start()

    def closeEvent(self, event):
        self._geo_timer.stop()
        if not self._closing_quietly:
            self.geometryChanged.emit(self.note_id)
            self.closedByUser.emit(self.note_id)
        super().closeEvent(event)

    def bring_to_front(self):
        if self.isMinimized():
            self.showNormal()
        self.show()
        self.raise_()
        self.activateWindow()

    def cascade_point(self):
        """새 노트를 놓을 자리 (이 노트 오른쪽 아래로 조금)."""
        return self.frameGeometry().topLeft() + QPoint(30, 30)
