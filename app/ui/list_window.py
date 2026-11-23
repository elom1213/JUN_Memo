# -*- coding: utf-8 -*-
# Python Script by Ji Hun Park
# last Update date : 2026-11-23
# JUN_Memo - 노트 목록 창
"""
윈도우 스티커 메모의 "노트 목록" 과 같은 창: [+] 새 노트 · 검색 · 노트 카드(색 띠 · 앞부분 · 고친 시각).
카드를 클릭하면 그 노트가 스티커 창으로 열린다(이미 열려 있으면 앞으로). 우클릭 = Open · Color · Delete.

모든 UI 문자열은 영어 (한국어는 주석만).
"""

import time

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QAction, QFont
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMenu,
                               QMessageBox, QPushButton, QVBoxLayout, QWidget, QAbstractItemView)

from app.core import store as st
from app.config.version import VERSION


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
    """목록의 노트 하나 - 위쪽 색 띠 + 앞부분 3줄 + 오른쪽 위 시각."""

    def __init__(self, note, parent=None):
        super().__init__(parent)
        pal = st.palette(note["color"])
        self.setObjectName("card")
        self.setStyleSheet(
            "#card {{ background: {body}; border-top: 5px solid {header}; border-radius: 2px; }}"
            "QLabel {{ color: {text}; background: transparent; }}".format(**pal))
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 6, 10, 8)
        lay.setSpacing(2)
        top = QHBoxLayout()
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
    newRequested = Signal()
    deleteRequested = Signal(str)
    colorRequested = Signal(str, str)

    def __init__(self, store):
        super().__init__(None, Qt.Window)
        self.store = store
        self.setWindowTitle("JUN Memo v{0}".format(VERSION))
        self.resize(340, 520)
        self.setStyleSheet("ListWindow { background: #F3F3F3; }")

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        row = QHBoxLayout()
        title = QLabel("Sticky Notes")
        tf = title.font()
        tf.setPointSize(14)
        tf.setBold(True)
        title.setFont(tf)
        row.addWidget(title)
        row.addStretch(1)
        self.btn_new = QPushButton("+")
        self.btn_new.setToolTip("New note (Ctrl+N)")
        self.btn_new.setFixedSize(34, 30)
        self.btn_new.setShortcut("Ctrl+N")
        self.btn_new.clicked.connect(self.newRequested.emit)
        row.addWidget(self.btn_new)
        root.addLayout(row)

        self.ipf_search = QLineEdit()
        self.ipf_search.setPlaceholderText("Search...")
        self.ipf_search.setClearButtonEnabled(True)
        self.ipf_search.setToolTip("Show the notes that contain every word typed here.")
        self.ipf_search.textChanged.connect(lambda *_: self.refresh())
        root.addWidget(self.ipf_search)

        self.list = QListWidget()
        self.list.setSpacing(4)
        self.list.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.list.setStyleSheet("QListWidget { background: transparent; border: none; }"
                                "QListWidget::item:selected { background: #00000014; }")
        self.list.setToolTip("Click a note to open it. Right-click: open, color, delete.")
        self.list.itemClicked.connect(self._on_clicked)
        self.list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self._on_menu)
        root.addWidget(self.list, 1)

        self.lbl_count = QLabel("")
        self.lbl_count.setStyleSheet("color: #666;")
        root.addWidget(self.lbl_count)
        self.refresh()

    # ---------------------------------------------------------------- 목록
    def refresh(self):
        keep = self.current_id()
        notes = self.store.ordered(self.ipf_search.text())
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
        if self.ipf_search.text().strip():
            self.lbl_count.setText("{0} of {1} note(s)".format(len(notes), total))
        else:
            self.lbl_count.setText("{0} note(s)".format(total) if total else "No notes yet - click + to make one.")

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
        menu = QMenu(self)
        menu.addAction("Open").triggered.connect(lambda: self.openRequested.emit(note_id))
        colors = menu.addMenu("Color")
        for name in st.COLORS:
            act = QAction(name, colors)
            act.triggered.connect(lambda _=False, n=name: self.colorRequested.emit(note_id, n))
            colors.addAction(act)
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
