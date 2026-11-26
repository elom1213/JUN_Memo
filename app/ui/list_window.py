# -*- coding: utf-8 -*-
# Python Script by Ji Hun Park
# last Update date : 2026-11-23
# JUN_Memo - 노트 목록 창
"""
윈도우 스티커 메모의 "노트 목록" 과 같은 창: [+] 새 노트 · Pin · [...] · 검색 · 범위 필터 · 노트 카드.
카드를 클릭하면 그 노트가 스티커 창으로 열린다(이미 열려 있으면 앞으로). 우클릭 = Open · Color · Shared · Delete.

v01.01
- 창 색을 고른다(노트와 같은 7색 + 사용자 색). 창의 **모든** 부분(배경 · 글자 · 검색칸 · 버튼)을 그 팔레트로 직접 칠한다 -
  윈도우 다크 모드에서 Qt 가 흰 글자를 주는데 배경만 밝게 칠해 글자가 안 보이던 것.
- Pin = 늘 맨 위. 범위 필터 All / Shared / This PC, 카드마다 범위 표시.
- [...] 에 Reload shared notes · Add to Start Menu · Pin to Taskbar (0110_JUN_Video_Tool 과 같은 셸 통합).

모든 UI 문자열은 영어 (한국어는 주석만).
"""

import time

from PySide6.QtCore import QEvent, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QColor, QFont, QFontMetrics
from PySide6.QtWidgets import (QAbstractItemView, QButtonGroup, QColorDialog, QFrame, QGridLayout, QHBoxLayout, QLabel,
                               QLineEdit, QListWidget, QListWidgetItem, QMenu, QMessageBox, QRadioButton, QSizePolicy,
                               QToolButton, QVBoxLayout, QWidget, QWidgetAction)

from app.config.version import VERSION
from app.core import store as st
from app.ui.memo_anim import MemoAnim

SHRINK_WIDTH = 272          # A00220 · A00240 · A00370 과 같은 줄인 크기
SHRINK_HEIGHT = 155

PIN_ON = "#FFB3B3"
SCOPE_ALL = "all"
SCOPE_LABEL = {st.SCOPE_SHARED: "Shared", st.SCOPE_LOCAL: "This PC"}


def when(ts, now=None):
    """고친 시각 - 오늘이면 시:분, 올해면 월 일, 그 밖은 연-월-일."""
    now = now or time.time()
    t, n = time.localtime(ts), time.localtime(now)
    if t.tm_year == n.tm_year and t.tm_yday == n.tm_yday:
        return time.strftime("%H:%M", t)
    if t.tm_year == n.tm_year:
        return time.strftime("%b %d", t)
    return time.strftime("%Y-%m-%d", t)


class _Card(QFrame):
    """목록의 노트 하나 - 위쪽 색 띠 + 범위 표시 + 앞부분 3줄 + 오른쪽 위 시각. zoom = 목록 글자 배율(v01.05)."""

    def __init__(self, note, parent=None, zoom=1.0):
        super().__init__(parent)
        pal = st.palette(note["color"])
        self.setObjectName("card")
        self.setAttribute(Qt.WA_StyledBackground, True)
        scope_color = st.SCOPE_COLORS[note["scope"]]
        # v01.07 카드 왼쪽 띠 + 배지 = 범위 색 (Shared 파랑 / This PC 초록) - 목록을 훑어볼 때 바로 구분된다
        self.setStyleSheet(
            "#card {{ background: {body}; border-top: 5px solid {header}; border-left: 5px solid {scope}; "
            "border-radius: 2px; }}"
            "QLabel {{ color: {text}; background: transparent; }}"
            "#scopeTag {{ background: {scope}; color: #FFFFFF; border: none; border-radius: 3px; padding: 0 5px; "
            "font-weight: bold; }}".format(scope=scope_color, **pal))
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 6, 10, 8)
        lay.setSpacing(2)
        top = QHBoxLayout()
        self.lbl_scope = QLabel(st.SCOPE_TEXT[note["scope"]])
        self.lbl_scope.setObjectName("scopeTag")
        self.lbl_scope.setToolTip("Shared: kept in the GitHub repository (shared/notes).\n"
                                  "This PC: kept only on this computer.")
        f = self.lbl_scope.font()
        f.setPointSizeF(7 * zoom)
        self.lbl_scope.setFont(f)
        # v01.09 배지 높이를 글꼴로 고정 - 안 그러면 같은 줄의 시각(📌 이모지 등) 높이만큼 늘어나 카드마다 달랐다
        self.lbl_scope.setFixedHeight(QFontMetrics(f).height() + 4)
        top.addWidget(self.lbl_scope, 0, Qt.AlignVCenter)
        # v01.09 제목 - 범위 배지 옆 (없으면 비운다). 좁으면 잘리고 시각은 늘 보인다
        title = note.get("title", "")
        # v01.10 부모(self)를 꼭 준다 - 부모 없이 setVisible(True) 하면 잠깐 독립 창으로 떴다 사라졌다(글 칠 때마다 목록을 다시 그려 반복)
        self.lbl_title = QLabel(title if len(title) <= 60 else title[:59] + "…", self)
        self.lbl_title.setObjectName("cardTitle")
        self.lbl_title.setToolTip(title)
        self.lbl_title.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        f = QFont("Segoe UI")
        f.setPointSizeF(9 * zoom)
        f.setBold(True)
        self.lbl_title.setFont(f)
        if not title:
            self.lbl_title.hide()
        top.addSpacing(4)
        top.addWidget(self.lbl_title, 1, Qt.AlignVCenter)
        if not title:
            top.addStretch(1)
        self.lbl_time = QLabel(when(note["modified"]) + ("   📌" if note["pinned"] else ""))
        f = self.lbl_time.font()
        f.setPointSizeF(8 * zoom)
        self.lbl_time.setFont(f)
        top.addWidget(self.lbl_time)
        lay.addLayout(top)
        self.lbl_text = QLabel(st.preview(note["text"]) or "(empty note)")
        self.lbl_text.setWordWrap(True)
        tf = QFont("Segoe UI")
        tf.setPointSizeF(10 * zoom)                          # 정수로 잘리지 않게
        self.lbl_text.setFont(tf)
        lay.addWidget(self.lbl_text)


class ListWindow(QWidget):

    openRequested = Signal(str)
    newRequested = Signal(str)                  # 범위 (shared / local)
    deleteRequested = Signal(str)
    colorRequested = Signal(str, str)
    scopeRequested = Signal(str, str)           # 노트 id, 범위
    viewChanged = Signal()                      # 목록 창 색 · 핀 · 자리 (저장)
    reloadRequested = Signal()
    startMenuRequested = Signal()
    taskbarRequested = Signal()
    pushSharedRequested = Signal()              # v01.03 공유 노트만 GitHub 로
    pullSharedRequested = Signal()              # v01.13 다른 PC 가 올린 공유 노트 받기

    def __init__(self, store):
        super().__init__(None, Qt.Window)
        self.store = store
        self.scope_filter = SCOPE_ALL
        self.setWindowTitle("JUN Memo v{0}".format(VERSION))
        self.setObjectName("listWindow")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.resize(380, 540)              # v01.04 머리 줄에 Shrink · Pin(72 px 둘)이 들어가 조금 넓게
        self.pinned = False
        self.shrunk = False
        self._full_size = None      # 줄이기 전 크기 (되돌릴 때)

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        row = QHBoxLayout()
        self.header_row = row
        # v01.04 Shrink 동안만 보이는 아이콘 애니메이션 (헤더 왼쪽, 클릭하면 펴기)
        self.anim = MemoAnim(self)
        self.anim.clicked.connect(lambda: self.set_shrunk(False))
        self.anim.hide()
        row.addWidget(self.anim)
        self.lbl_title = QLabel("Sticky Notes")
        tf = self.lbl_title.font()
        tf.setPointSize(14)
        tf.setBold(True)
        self.lbl_title.setFont(tf)
        row.addWidget(self.lbl_title)
        row.addStretch(1)
        self.btn_new = self._tool("+", "New note (Ctrl+N) - in the scope picked below (All = This PC)")
        self.btn_new.setShortcut("Ctrl+N")
        self.btn_new.clicked.connect(lambda: self.newRequested.emit(
            st.SCOPE_SHARED if self.scope_filter == st.SCOPE_SHARED else st.SCOPE_LOCAL))
        row.addWidget(self.btn_new)
        # v01.04 Shrink · Pin 은 작은 그리드에 - 평소엔 한 줄 [Shrink][Pin], 줄였을 땐 Pin 을 Shrunk 아래로 (A00220 과 같다)
        self.btn_shrink = self._tool("Shrink", "Shrink the notes list to a small animated icon "
                                               "(click Shrunk or the icon to open it again)")
        self.btn_shrink.setCheckable(True)
        self.btn_shrink.setObjectName("shrinkBtn")       # v01.05 켜져도 빨갛지 않게 (사용자) - 아래 스타일
        self.btn_shrink.setFixedSize(72, 28)
        self.btn_shrink.toggled.connect(lambda on: self.set_shrunk(on))
        self.btn_pin = self._tool("Pin", "Keep the notes list on top of other windows")
        self.btn_pin.setObjectName("pinBtn")
        self.btn_pin.setCheckable(True)
        self.btn_pin.setFixedSize(72, 28)
        self.btn_pin.toggled.connect(lambda on: self.set_pinned(on))
        self.button_grid = QGridLayout()
        self.button_grid.setContentsMargins(0, 0, 0, 0)
        self.button_grid.setSpacing(4)
        self.button_grid.addWidget(self.btn_shrink, 0, 0)
        self.button_grid.addWidget(self.btn_pin, 0, 1)
        row.addLayout(self.button_grid)
        row.setAlignment(self.button_grid, Qt.AlignTop)
        self.btn_menu = self._tool("…", "Color, shared notes, Start menu / taskbar")
        self.btn_menu.setPopupMode(QToolButton.InstantPopup)
        self.btn_menu.setMenu(self._build_menu())
        row.addWidget(self.btn_menu)
        root.addLayout(row)

        self.ipf_search = QLineEdit()
        self.ipf_search.setObjectName("search")
        self.ipf_search.setPlaceholderText("Search...")
        self.ipf_search.setClearButtonEnabled(True)
        self.ipf_search.setToolTip("Show the notes that contain every word typed here.")
        self.ipf_search.textChanged.connect(lambda *_: self.refresh())
        root.addWidget(self.ipf_search)

        scope_row = QHBoxLayout()
        self.scope_buttons = QButtonGroup(self)
        for label, value, tip in (("All", SCOPE_ALL, "Every note."),
                                  ("Shared", st.SCOPE_SHARED, "Notes kept in the GitHub repository (shared/notes) - "
                                                              "the same on every PC after git pull."),
                                  ("This PC", st.SCOPE_LOCAL, "Notes kept only on this computer.")):
            rb = QRadioButton(label)
            rb.setToolTip(tip)
            rb.setProperty("scope", value)
            rb.setChecked(value == SCOPE_ALL)
            self.scope_buttons.addButton(rb)
            scope_row.addWidget(rb)
        scope_row.addStretch(1)
        self.scope_buttons.buttonClicked.connect(self._on_scope_filter)
        root.addLayout(scope_row)

        self.list = QListWidget()
        self.list.setObjectName("notes")
        self.list.setSpacing(4)
        self.list.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.list.setSelectionMode(QAbstractItemView.SingleSelection)
        # v01.08 카드를 끌어 놓아 순서 바꾸기 - 놓은 뒤 순서를 저장소에 넘기고 카드를 다시 그린다
        self.list.setDragDropMode(QAbstractItemView.InternalMove)
        self.list.setDefaultDropAction(Qt.MoveAction)
        self.list.setDropIndicatorShown(True)
        self.list.model().rowsMoved.connect(lambda *_: QTimer.singleShot(0, self._on_reordered))
        self.list.setToolTip("Click a note to open it. Drag a note up or down to change the order.\n"
                             "Right-click: open, color, shared / this PC, delete.\n"
                             "Ctrl + mouse wheel: bigger / smaller text.")
        self.list.viewport().installEventFilter(self)            # v01.05 Ctrl + 휠 = 목록 글자 크기
        self.list.itemClicked.connect(self._on_clicked)
        self.list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self._on_menu)
        root.addWidget(self.list, 1)

        bottom = QHBoxLayout()
        self.lbl_count = QLabel("")
        self.lbl_count.setObjectName("count")
        bottom.addWidget(self.lbl_count, 1)
        # v01.13 Pull Shared - Push Shared 옆. 다른 PC 가 올린 공유 노트를 받아 목록 · 열린 노트에 반영 (커밋 · 푸시 없음)
        self.btn_pull = QToolButton(self)
        self.btn_pull.setObjectName("pullShared")
        self.btn_pull.setText("Pull Shared")
        self.btn_pull.setToolTip("Get the Shared notes another PC pushed to GitHub (git pull).\n"
                                 "Open notes are saved first; your unpushed edits are kept and merged.\n"
                                 "Nothing is committed or pushed.")
        self.btn_pull.setCursor(Qt.PointingHandCursor)
        self.btn_pull.clicked.connect(self.pullSharedRequested.emit)
        bottom.addWidget(self.btn_pull)
        # v01.03 Push Shared - 공유 노트(shared/notes)만 커밋해 GitHub 로 (이 PC 노트 · 다른 파일은 안 올라간다)
        self.btn_push = QToolButton(self)
        self.btn_push.setObjectName("pushShared")
        self.btn_push.setText("Push Shared")
        self.btn_push.setToolTip("Send the Shared notes to GitHub (only shared/notes - This PC notes stay here).\n"
                                 "If another PC pushed first, its shared notes are pulled in, then this pushes.")
        self.btn_push.setCursor(Qt.PointingHandCursor)
        self.btn_push.clicked.connect(self.pushSharedRequested.emit)
        bottom.addWidget(self.btn_push)
        root.addLayout(bottom)

        # Shrink 가 감추는 것들 (애니메이션 · Shrunk · Pin 만 남는다)
        self._shrink_hidden = [self.lbl_title, self.btn_new, self.btn_menu, self.ipf_search, self.list,
                               self.lbl_count, self.btn_pull, self.btn_push] + list(self.scope_buttons.buttons())

        view = store.list_view
        self.set_color(view.get("color") or st.DEFAULT_LIST_COLOR, emit=False)
        self.set_pinned(view.get("pinned", False), emit=False)
        geo = view.get("geometry")
        if geo:                                     # 바깥(테두리 포함) 위치 + 안쪽 크기 - geometry_list 와 같은 기준
            self.resize(max(geo[2], 260), max(geo[3], 300))
            self.move(geo[0], geo[1])
        self.refresh()

    # ---------------------------------------------------------------- 만들기
    def _tool(self, text, tip):
        b = QToolButton(self)
        b.setText(text)
        b.setToolTip(tip)
        b.setAutoRaise(True)
        b.setFixedHeight(30)
        b.setMinimumWidth(34)
        b.setCursor(Qt.PointingHandCursor)
        return b

    def _build_menu(self):
        menu = QMenu(self)
        holder = QWidget(menu)
        grid = QGridLayout(holder)
        grid.setContentsMargins(8, 6, 8, 6)
        grid.setSpacing(4)
        self.swatches = {}
        for i, (name, pal) in enumerate(st.COLORS.items()):
            b = QToolButton(holder)
            b.setFixedSize(30, 30)
            b.setToolTip("List color: " + name)
            b.setStyleSheet("QToolButton {{ background: {0}; border: 1px solid #00000033; }}"
                            "QToolButton:hover {{ border: 2px solid #00000088; }}".format(pal["header"]))
            b.clicked.connect(lambda _=False, n=name: (self.set_color(n), menu.close()))
            grid.addWidget(b, 0, i)
            self.swatches[name] = b
        act = QWidgetAction(menu)
        act.setDefaultWidget(holder)
        menu.addAction(act)
        self.act_custom = QAction("Custom list color...", menu)
        self.act_custom.triggered.connect(self.pick_custom_color)
        menu.addAction(self.act_custom)
        menu.addSeparator()
        # v01.05 목록 글자 크기
        self.act_larger = QAction("Larger text  (Ctrl + wheel)", menu)
        self.act_larger.triggered.connect(lambda: self.step_text_zoom(1))
        menu.addAction(self.act_larger)
        self.act_smaller = QAction("Smaller text", menu)
        self.act_smaller.triggered.connect(lambda: self.step_text_zoom(-1))
        menu.addAction(self.act_smaller)
        self.act_reset_zoom = QAction("Reset text size", menu)
        self.act_reset_zoom.triggered.connect(lambda: self.set_text_zoom(1.0))
        menu.addAction(self.act_reset_zoom)
        menu.addSeparator()
        self.act_reload = QAction("Reload shared notes", menu)
        self.act_reload.setToolTip("Read shared/notes again (after git pull).")
        self.act_reload.triggered.connect(self.reloadRequested.emit)
        menu.addAction(self.act_reload)
        menu.addSeparator()
        self.act_start = QAction("Add to Start Menu", menu)
        self.act_start.triggered.connect(self.startMenuRequested.emit)
        menu.addAction(self.act_start)
        self.act_taskbar = QAction("Pin to Taskbar", menu)
        self.act_taskbar.triggered.connect(self.taskbarRequested.emit)
        menu.addAction(self.act_taskbar)
        return menu

    # ---------------------------------------------------------------- 색 · 핀
    def set_color(self, color, emit=True):
        """창 색. 모든 부분을 같은 팔레트로 칠한다 (다크 모드의 흰 글자가 밝은 배경에 묻히지 않게)."""
        pal = st.palette(color)
        self.color = color
        dark = pal["text"] == "#FFFFFF"
        field = "#4A4A4A" if dark else "#FFFFFF"
        ring = "#C8C8C8" if dark else "#7A7A7A"          # 안 고른 라디오 테두리 (글자보다 조금 옅게)
        sel_bg, sel_fg = st.selection_colors(color)     # v01.03 검색칸 선택도 불투명하게
        self.setStyleSheet(
            "#listWindow {{ background: {body}; }}"
            "#listWindow QLabel, #listWindow QRadioButton {{ color: {text}; background: transparent; }}"
            # v01.02 - 라디오 동그라미를 직접 그린다. 창을 통째로 칠하면 다크 모드 스타일의 동그라미가 안 보였다(사용자).
            #          안 고름 = 빈 원, 고름 = 원 안에 진한 점 + 굵은 글자.
            "#listWindow QRadioButton {{ spacing: 6px; padding: 2px 4px; }}"
            "#listWindow QRadioButton::indicator {{ width: 12px; height: 12px; border-radius: 8px; "
            "border: 2px solid {ring}; background: {field}; }}"
            "#listWindow QRadioButton::indicator:hover {{ border-color: {text}; }}"
            "#listWindow QRadioButton::indicator:checked {{ border-color: {text}; background: qradialgradient("
            "cx:0.5, cy:0.5, radius:0.5, fx:0.5, fy:0.5, stop:0 {text}, stop:0.5 {text}, stop:0.56 {field}, stop:1 {field}); }}"
            "#listWindow QRadioButton:checked {{ font-weight: bold; }}"
            "#search {{ background: {field}; color: {text}; border: 1px solid {header}; border-radius: 3px; "
            "padding: 3px 6px; selection-background-color: {sel_bg}; selection-color: {sel_fg}; }}"
            "#notes {{ background: transparent; border: none; }}"
            "#notes::item:selected {{ background: #00000018; }}"
            "#listWindow > QToolButton {{ color: {text}; background: transparent; border: none; font-size: 13px; "
            "padding: 0 6px; }}"
            "#listWindow > QToolButton:hover {{ background: #0000001F; }}"
            "#listWindow > QToolButton:checked {{ background: {pin}; color: #202020; }}"
            "#listWindow > QToolButton::menu-indicator {{ image: none; width: 0; }}"
            # Shrunk 는 켜져 있어도 연한 빨강이 아니다(사용자) - 평소 버튼과 같은 모양, 마우스를 올리면만 옅게
            # v01.06 Shrink · Pin 은 배경과 구분되는 버튼 모양 (목록 색과 같아 안 보이는 때가 있었다 - 사용자).
            #        입력칸과 같은 바탕 + 테두리. Shrunk 는 켜져도 빨갛지 않고 테두리만 진하게, 켜진 Pin 만 연한 빨강.
            "#listWindow > QToolButton#shrinkBtn, #listWindow > QToolButton#pinBtn {{ background: {field}; color: {text}; "
            "border: 1px solid {ring}; border-radius: 4px; }}"
            "#listWindow > QToolButton#shrinkBtn:hover, #listWindow > QToolButton#pinBtn:hover {{ border-color: {text}; }}"
            "#listWindow > QToolButton#shrinkBtn:checked {{ background: {field}; color: {text}; border: 2px solid {text}; "
            "font-weight: bold; }}"
            "#listWindow > QToolButton#pinBtn:checked {{ background: {pin}; color: #202020; border: 1px solid {ring}; }}"
            # v01.07 '#listWindow > QToolButton'(투명)이 더 구체적이라 Push Shared 테두리가 안 보였다 → 같은 구체성으로
            # v01.13 Pull Shared 도 같은 모양
            "#listWindow > QToolButton#pushShared, #listWindow > QToolButton#pullShared {{ color: {text}; background: {field}; "
            "border: 1px solid {ring}; border-radius: 3px; padding: 3px 10px; }}"
            "#listWindow > QToolButton#pushShared:hover, #listWindow > QToolButton#pullShared:hover {{ border-color: {text}; }}"
            "#listWindow > QToolButton#pushShared:disabled, #listWindow > QToolButton#pullShared:disabled {{ color: {ring}; }}"
            "#count {{ color: {text}; }}".format(field=field, ring=ring, pin=PIN_ON, sel_bg=sel_bg, sel_fg=sel_fg, **pal))
        if emit:
            self.store.list_view["color"] = color
            self.viewChanged.emit()

    def pick_custom_color(self):
        color = QColorDialog.getColor(QColor(st.palette(self.color)["body"]), self, "List color")
        if color.isValid():
            self.set_color(color.name().upper())

    def set_pinned(self, on, emit=True):
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
        if emit:
            self.store.list_view["pinned"] = on
            self.viewChanged.emit()

    # ---------------------------------------------------------------- 목록
    def _on_scope_filter(self, btn):
        self.scope_filter = btn.property("scope")
        self.refresh()

    def refresh(self):
        keep = self.current_id()
        scope = None if self.scope_filter == SCOPE_ALL else self.scope_filter
        notes = self.store.ordered(self.ipf_search.text(), scope=scope)
        self.list.clear()
        for note in notes:
            item = QListWidgetItem()
            item.setData(Qt.UserRole, note["id"])
            card = _Card(note, zoom=self.text_zoom())
            item.setSizeHint(QSize(100, card.sizeHint().height() + 4))
            self.list.addItem(item)
            self.list.setItemWidget(item, card)
            if note["id"] == keep:
                item.setSelected(True)
        total = len(self.store.notes)
        shared = sum(1 for n in self.store.notes.values() if n["scope"] == st.SCOPE_SHARED)
        if not total:
            self.lbl_count.setText("No notes yet - click + to make one.")
        elif self.ipf_search.text().strip() or scope is not None:
            self.lbl_count.setText("{0} of {1} note(s)  ·  {2} shared, {3} this PC".format(
                len(notes), total, shared, total - shared))
        else:
            self.lbl_count.setText("{0} note(s)  ·  {1} shared, {2} this PC".format(total, shared, total - shared))

    def current_id(self):
        item = self.list.currentItem()
        return item.data(Qt.UserRole) if item is not None else None

    def item_ids(self):
        return [self.list.item(i).data(Qt.UserRole) for i in range(self.list.count())]

    def _on_reordered(self):
        """v01.08 끌어 놓은 뒤 - 보이는 순서를 저장하고(viewChanged = 저장) 카드를 다시 만든다(옮긴 칸의 카드가 비지 않게)."""
        if self.store.set_order(self.item_ids()):
            self.viewChanged.emit()
        self.refresh()

    def _on_clicked(self, item):
        self.openRequested.emit(item.data(Qt.UserRole))

    def _on_menu(self, pos):
        item = self.list.itemAt(pos)
        if item is None:
            return
        note_id = item.data(Qt.UserRole)
        note = self.store.get(note_id)
        menu = QMenu(self)
        menu.addAction("Open").triggered.connect(lambda: self.openRequested.emit(note_id))
        colors = menu.addMenu("Color")
        for name in st.COLORS:
            act = QAction(name, colors)
            act.triggered.connect(lambda _=False, n=name: self.colorRequested.emit(note_id, n))
            colors.addAction(act)
        shared = QAction("Shared (GitHub)", menu)
        shared.setCheckable(True)
        shared.setChecked(note is not None and note["scope"] == st.SCOPE_SHARED)
        shared.triggered.connect(lambda on: self.scopeRequested.emit(
            note_id, st.SCOPE_SHARED if on else st.SCOPE_LOCAL))
        menu.addAction(shared)
        menu.addSeparator()
        menu.addAction("Delete").triggered.connect(lambda: self._confirm_delete(note_id))
        menu.exec(self.list.viewport().mapToGlobal(pos))

    def _confirm_delete(self, note_id):
        answer = QMessageBox.question(self, "Delete note", "Delete this note?",
                                      QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if answer == QMessageBox.Yes:
            self.deleteRequested.emit(note_id)

    def bring_to_front(self):
        if self.isMinimized():
            self.showNormal()
        self.show()
        self.raise_()
        self.activateWindow()

    def geometry_list(self):
        """[x, y, w, h] - 위치는 **바깥**(제목 표시줄 포함, move() 와 같은 기준), 크기는 안쪽.
        geometry() 의 안쪽 위치로 저장하고 move() 로 되살리면 켤 때마다 테두리만큼 밀린다(시험이 잡음).
        줄여 둔 동안은 줄이기 전 크기를 돌려준다(다시 켜서 펼 때 작은 창이 되지 않게)."""
        w, h = self._full_size if (self.shrunk and self._full_size) else (self.width(), self.height())
        return [self.x(), self.y(), w, h]

    # ---------------------------------------------------------------- 글자 크기 (v01.05)
    def text_zoom(self):
        return st.clamp_zoom(self.store.list_view.get("zoom", 1.0))

    def set_text_zoom(self, value, emit=True):
        value = st.clamp_zoom(value)
        if value == self.text_zoom() and emit:
            return
        self.store.list_view["zoom"] = value
        self.refresh()
        if emit:
            self.viewChanged.emit()

    def step_text_zoom(self, steps):
        self.set_text_zoom(self.text_zoom() + steps * st.ZOOM_STEP)

    def eventFilter(self, obj, event):
        if obj is self.list.viewport() and event.type() == QEvent.Wheel and event.modifiers() & Qt.ControlModifier:
            dy = event.angleDelta().y()
            if dy:
                self.step_text_zoom(1 if dy > 0 else -1)
            return True
        return super().eventFilter(obj, event)

    # ---------------------------------------------------------------- Shrink (v01.04)
    def set_shrunk(self, on, emit=True):
        """애니메이션 · Shrunk · Pin 만 남기고 SHRINK_WIDTH x SHRINK_HEIGHT 로 (A00220_BackupTool 과 같은 방식).

        감추는 위젯은 지우지 않고 hide / show 만 - 검색어 · 필터 · 스크롤이 그대로 돌아온다. Pin 은 그리드에서 Shrunk 아래 칸으로.
        숨긴 뒤 layout().invalidate() + activate() 를 해야 창이 실제로 줄어든다(옛 최소 크기에 막힌다 - A00220 의 교훈).
        애니메이션 타이머는 줄여 둔 동안에만 돈다.
        """
        on = bool(on)
        if on == self.shrunk and self.btn_shrink.isChecked() == on:
            return
        self.shrunk = on
        if self.btn_shrink.isChecked() != on:
            self.btn_shrink.blockSignals(True)
            self.btn_shrink.setChecked(on)
            self.btn_shrink.blockSignals(False)
        self.button_grid.removeWidget(self.btn_pin)
        if on:
            self._full_size = (self.width(), self.height())
            for w in self._shrink_hidden:
                w.hide()
            self.button_grid.addWidget(self.btn_pin, 1, 0)
            self.anim.show()
            self.anim.set_running(True)
        else:
            self.anim.set_running(False)
            self.anim.hide()
            self.button_grid.addWidget(self.btn_pin, 0, 1)
            for w in self._shrink_hidden:
                w.show()
        self.btn_shrink.setText("Shrunk" if on else "Shrink")
        lay = self.layout()
        lay.invalidate()
        lay.activate()
        if on:
            self.setMinimumSize(0, 0)
            self.resize(SHRINK_WIDTH, SHRINK_HEIGHT)
        elif self._full_size:
            self.resize(*self._full_size)
        if emit:
            self.store.list_view["shrunk"] = on
            self.viewChanged.emit()
