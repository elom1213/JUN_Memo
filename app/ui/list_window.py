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

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QAction, QColor, QFont
from PySide6.QtWidgets import (QAbstractItemView, QButtonGroup, QColorDialog, QFrame, QGridLayout, QHBoxLayout, QLabel,
                               QLineEdit, QListWidget, QListWidgetItem, QMenu, QMessageBox, QRadioButton, QToolButton,
                               QVBoxLayout, QWidget, QWidgetAction)

from app.config.version import VERSION
from app.core import store as st

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
    """목록의 노트 하나 - 위쪽 색 띠 + 범위 표시 + 앞부분 3줄 + 오른쪽 위 시각."""

    def __init__(self, note, parent=None):
        super().__init__(parent)
        pal = st.palette(note["color"])
        self.setObjectName("card")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(
            "#card {{ background: {body}; border-top: 5px solid {header}; border-radius: 2px; }}"
            "QLabel {{ color: {text}; background: transparent; }}"
            "#scopeTag {{ border: 1px solid {text}; border-radius: 3px; padding: 0 4px; }}".format(**pal))
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 6, 10, 8)
        lay.setSpacing(2)
        top = QHBoxLayout()
        self.lbl_scope = QLabel(SCOPE_LABEL[note["scope"]])
        self.lbl_scope.setObjectName("scopeTag")
        self.lbl_scope.setToolTip("Shared: kept in the GitHub repository (shared/notes).\n"
                                  "This PC: kept only on this computer.")
        f = self.lbl_scope.font()
        f.setPointSize(7)
        self.lbl_scope.setFont(f)
        top.addWidget(self.lbl_scope)
        top.addStretch(1)
        self.lbl_time = QLabel(when(note["modified"]) + ("   📌" if note["pinned"] else ""))
        f = self.lbl_time.font()
        f.setPointSize(8)
        self.lbl_time.setFont(f)
        top.addWidget(self.lbl_time)
        lay.addLayout(top)
        self.lbl_text = QLabel(st.preview(note["text"]) or "(empty note)")
        self.lbl_text.setWordWrap(True)
        self.lbl_text.setFont(QFont("Segoe UI", 10))
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

    def __init__(self, store):
        super().__init__(None, Qt.Window)
        self.store = store
        self.scope_filter = SCOPE_ALL
        self.setWindowTitle("JUN Memo v{0}".format(VERSION))
        self.setObjectName("listWindow")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.resize(340, 540)
        self.pinned = False

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        row = QHBoxLayout()
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
        self.btn_pin = self._tool("Pin", "Keep the notes list on top of other windows")
        self.btn_pin.setCheckable(True)
        self.btn_pin.toggled.connect(lambda on: self.set_pinned(on))
        row.addWidget(self.btn_pin)
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
        self.list.setToolTip("Click a note to open it. Right-click: open, color, shared / this PC, delete.")
        self.list.itemClicked.connect(self._on_clicked)
        self.list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self._on_menu)
        root.addWidget(self.list, 1)

        self.lbl_count = QLabel("")
        self.lbl_count.setObjectName("count")
        root.addWidget(self.lbl_count)

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
            "padding: 3px 6px; selection-background-color: #00000040; }}"
            "#notes {{ background: transparent; border: none; }}"
            "#notes::item:selected {{ background: #00000018; }}"
            "#listWindow > QToolButton {{ color: {text}; background: transparent; border: none; font-size: 13px; "
            "padding: 0 6px; }}"
            "#listWindow > QToolButton:hover {{ background: #0000001F; }}"
            "#listWindow > QToolButton:checked {{ background: {pin}; color: #202020; }}"
            "#listWindow > QToolButton::menu-indicator {{ image: none; width: 0; }}"
            "#count {{ color: {text}; }}".format(field=field, ring=ring, pin=PIN_ON, **pal))
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
            card = _Card(note)
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
        geometry() 의 안쪽 위치로 저장하고 move() 로 되살리면 켤 때마다 테두리만큼 밀린다(시험이 잡음)."""
        return [self.x(), self.y(), self.width(), self.height()]
