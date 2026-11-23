# -*- coding: utf-8 -*-
# Python Script by Ji Hun Park
# last Update date : 2026-11-23
# JUN_Memo - 목록 창 · 노트 창 · 저장소를 잇는다
"""
- 글을 칠 때마다 쓰지 않고 SAVE_MS 뒤에 한 번 저장(마지막 입력 기준). 앱을 끌 때 · 노트를 닫을 때는 바로 저장.
- 노트 창을 닫으면 목록에는 남는다(open=False). **빈 노트는 닫을 때 지운다**(윈도우 스티커 메모처럼).
- 다시 켜면 열려 있던 노트들을 그 자리 · 크기 · 색 · 핀 그대로 다시 연다. 저장된 자리가 지금 화면 밖이면(모니터를 뺐을 때) 주 화면으로.
"""

from PySide6.QtCore import QObject, QPoint, QRect, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication

from app.core import store as st
from app.ui.list_window import ListWindow
from app.ui.note_window import DEFAULT_SIZE, NoteWindow

SAVE_MS = 500


class Controller(QObject):

    def __init__(self, store=None):
        super().__init__()
        self.store = store or st.NoteStore()
        self.windows = {}
        self.list_window = ListWindow(self.store)
        lw = self.list_window
        lw.openRequested.connect(self.open_note)
        lw.newRequested.connect(lambda: self.new_note())
        lw.deleteRequested.connect(self.delete_note)
        lw.colorRequested.connect(self.set_color)
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(SAVE_MS)
        self._save_timer.timeout.connect(self.save_now)
        app = QApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self.shutdown)

    # ---------------------------------------------------------------- 시작 · 끝
    def start(self):
        """목록 창을 보이고, 지난번 열려 있던 노트들을 다시 연다."""
        self.list_window.show()
        for note in sorted(self.store.notes.values(), key=lambda n: n["created"]):
            if note["open"]:
                self.open_note(note["id"])
        if self.store.error:
            print("[JUN_Memo] " + self.store.error)

    def shutdown(self):
        for note_id, win in list(self.windows.items()):
            self._pull_content(note_id)
            self._pull_geometry(note_id)
        self.save_now()

    # ---------------------------------------------------------------- 저장
    def schedule_save(self):
        self._save_timer.start()

    def save_now(self):
        self._save_timer.stop()
        self.store.save()
        self.list_window.refresh()

    def _pull_content(self, note_id):
        win = self.windows.get(note_id)
        if win is None:
            return False
        html, text = win.content()
        return self.store.set_content(note_id, html, text)

    def _pull_geometry(self, note_id):
        win = self.windows.get(note_id)
        if win is None:
            return False
        g = win.geometry()
        return self.store.update(note_id, geometry=[g.x(), g.y(), g.width(), g.height()])

    # ---------------------------------------------------------------- 노트
    def open_note(self, note_id):
        note = self.store.get(note_id)
        if note is None:
            return None
        win = self.windows.get(note_id)
        if win is not None:
            win.bring_to_front()
            return win
        win = NoteWindow(note)
        self._fit_on_screen(win)
        win.contentChanged.connect(self._on_content)
        win.geometryChanged.connect(self._on_geometry)
        win.closedByUser.connect(self._on_closed)
        win.newNoteRequested.connect(self._on_new_from)
        win.listRequested.connect(self.list_window.bring_to_front)
        win.deleteRequested.connect(self.delete_note)
        win.colorChanged.connect(self.set_color)
        win.pinChanged.connect(self.set_pinned)
        self.windows[note_id] = win
        win.show()
        win.bring_to_front()
        if self.store.update(note_id, open=True):
            self.schedule_save()
        return win

    def new_note(self, at=None, color=None):
        geo = None
        if at is not None:
            geo = [at.x(), at.y(), DEFAULT_SIZE.width(), DEFAULT_SIZE.height()]
        note = self.store.new_note(color=color, geometry=geo)
        win = self.open_note(note["id"])
        win.editor.setFocus()
        self.save_now()
        return note["id"]

    def _on_new_from(self, note_id):
        win = self.windows.get(note_id)
        at = win.cascade_point() if win is not None else None
        self.new_note(at=at)

    def delete_note(self, note_id):
        win = self.windows.pop(note_id, None)
        if win is not None:
            win.close_quietly()
        if self.store.delete(note_id):
            self.save_now()

    def set_color(self, note_id, color):
        if self.store.update(note_id, color=color):
            win = self.windows.get(note_id)
            if win is not None and win.color != color:
                win.set_color(color, emit=False)
            self.save_now()

    def set_pinned(self, note_id, on):
        if self.store.update(note_id, pinned=bool(on)):
            self.save_now()

    # ---------------------------------------------------------------- 창 알림
    def _on_content(self, note_id):
        if self._pull_content(note_id):
            self.schedule_save()

    def _on_geometry(self, note_id):
        if self._pull_geometry(note_id):
            self.schedule_save()

    def _on_closed(self, note_id):
        self._pull_content(note_id)
        self._pull_geometry(note_id)
        self.windows.pop(note_id, None)
        if self.store.is_empty(note_id):
            self.store.delete(note_id)              # 빈 노트는 남기지 않는다
        else:
            self.store.update(note_id, open=False)
        self.save_now()

    # ---------------------------------------------------------------- 화면
    @staticmethod
    def _fit_on_screen(win):
        """저장된 자리가 지금 어느 화면에도 없으면(모니터를 뺐을 때) 주 화면 가운데 근처로."""
        center = win.geometry().center()
        if QGuiApplication.screenAt(center) is not None:
            return
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return
        area = screen.availableGeometry()
        rect = QRect(QPoint(0, 0), win.size())
        rect.moveCenter(area.center())
        win.move(rect.topLeft())
