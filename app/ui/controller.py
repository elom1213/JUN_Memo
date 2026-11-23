# -*- coding: utf-8 -*-
# Python Script by Ji Hun Park
# last Update date : 2026-11-23
# JUN_Memo - 목록 창 · 노트 창 · 저장소를 잇는다
"""
- 글을 칠 때마다 쓰지 않고 SAVE_MS 뒤에 한 번 저장(마지막 입력 기준). 앱을 끌 때 · 노트를 닫을 때는 바로 저장.
- 노트 창을 닫으면 목록에는 남는다(open=False). **빈 노트는 닫을 때 지운다**(윈도우 스티커 메모처럼).
- 다시 켜면 열려 있던 노트들을 그 자리 · 크기 · 색 · 핀 그대로 다시 연다. 저장된 자리가 지금 화면 밖이면(모니터를 뺐을 때) 주 화면으로.
- v01.01: 노트 범위(Shared = 저장소 shared/notes, This PC = %APPDATA%), 목록 창 색 · Pin · 자리, 시작 메뉴 · 작업 표시줄
  (0110_JUN_Video_Tool 과 같은 셸 통합 - core/shell_integration).
"""

from PySide6.QtCore import QObject, QPoint, QRect, Qt, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication, QMessageBox

from app.config.version import APP_NAME
from app.core import shell_integration

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
        lw.newRequested.connect(lambda scope: self.new_note(scope=scope))
        lw.deleteRequested.connect(self.delete_note)
        lw.colorRequested.connect(self.set_color)
        lw.scopeRequested.connect(self.set_scope)
        lw.viewChanged.connect(self.save_now)
        lw.reloadRequested.connect(self.reload_shared)
        lw.startMenuRequested.connect(self.add_to_start_menu)
        lw.taskbarRequested.connect(self.pin_to_taskbar)
        self.messages = []                          # 마지막 안내 문구들 (시험이 본다)
        self.quiet = False                          # True 면 메시지 창을 띄우지 않는다 (시험)
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
        if QGuiApplication.platformName() == "windows":
            # 작업 표시줄 버튼을 우클릭 → 고정했을 때 python 이 아니라 이 앱이 실행되게 (Video Tool 과 같은 방식)
            QTimer.singleShot(0, lambda: shell_integration.set_window_relaunch(int(self.list_window.winId())))

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
        if self.list_window.isVisible():
            self.store.list_view["geometry"] = self.list_window.geometry_list()
        self.store.save()
        if self.store.error:
            print("[JUN_Memo] " + self.store.error)
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
        win.scopeChanged.connect(self.set_scope)
        self.windows[note_id] = win
        win.show()
        win.bring_to_front()
        if self.store.update(note_id, open=True):
            self.schedule_save()
        return win

    def new_note(self, at=None, color=None, scope=st.SCOPE_LOCAL):
        geo = None
        if at is not None:
            geo = [at.x(), at.y(), DEFAULT_SIZE.width(), DEFAULT_SIZE.height()]
        note = self.store.new_note(color=color, geometry=geo, scope=scope)
        win = self.open_note(note["id"])
        win.editor.setFocus()
        self.save_now()
        return note["id"]

    def _on_new_from(self, note_id):
        win = self.windows.get(note_id)
        at = win.cascade_point() if win is not None else None
        note = self.store.get(note_id)
        self.new_note(at=at, scope=note["scope"] if note else st.SCOPE_LOCAL)      # 같은 범위로

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

    def set_scope(self, note_id, scope):
        """Shared (저장소 shared/notes) ↔ This PC (%APPDATA%). 저장할 때 파일이 옮겨진다."""
        if self.store.update(note_id, scope=scope):
            win = self.windows.get(note_id)
            if win is not None and win.scope != scope:
                win.set_scope(scope, emit=False)
            self.save_now()

    def reload_shared(self):
        """git pull 뒤 공유 노트를 다시 읽는다 (열려 있는 공유 노트는 건드리지 않는다)."""
        added, changed, removed = self.store.reload_shared()
        self.list_window.refresh()
        self._inform("Shared notes", "Shared notes reloaded: {0} new, {1} changed, {2} removed.{3}".format(
            added, changed, removed, "\n(Open shared notes are kept as they are - close them and reload to update.)"
            if any(n["open"] and n["scope"] == st.SCOPE_SHARED for n in self.store.notes.values()) else ""))

    # ---------------------------------------------------------------- 시작 메뉴 · 작업 표시줄
    def _inform(self, title, text, warn=False):
        self.messages.append(text)
        if self.quiet:
            return
        (QMessageBox.warning if warn else QMessageBox.information)(self.list_window, title, text)

    def _make_start_shortcut(self):
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            shell_integration.add_to_start_menu()
        except shell_integration.ShellIntegrationError as exc:
            QApplication.restoreOverrideCursor()
            self._inform("Start Menu", "Could not create the Start menu shortcut:\n{0}".format(exc), warn=True)
            return False
        QApplication.restoreOverrideCursor()
        return True

    def add_to_start_menu(self):
        if not self._make_start_shortcut():
            return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            pinned = shell_integration.pin_shortcut(shell_integration.start_menu_shortcut(), "start")
        finally:
            QApplication.restoreOverrideCursor()
        text = "'{0}' was added to the Start menu (All apps and Start search).".format(APP_NAME)
        if pinned in ("pinned", "already"):
            # Windows 11 은 고정 결과를 알려 주지 않으므로 '요청했다' 까지만 말한다
            text += ("\n\nIt was also pinned to Start. If you do not see it among the pinned apps, "
                     "open All apps, right-click '{0}' and choose 'Pin to Start'.".format(APP_NAME))
        else:
            text += "\n\nTo pin it to Start, open All apps, right-click '{0}' and choose 'Pin to Start'.".format(APP_NAME)
        text += "\n\nIf you move the JUN_Memo folder, click this menu item again to update the shortcut."
        self._inform("Start Menu", text)

    def pin_to_taskbar(self):
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            existing = shell_integration.find_pinned_taskbar_shortcut()
        finally:
            QApplication.restoreOverrideCursor()
        if existing is not None:
            self._inform("Taskbar", "'{0}' is already pinned to the taskbar.".format(APP_NAME))
            return
        if not self._make_start_shortcut():
            return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            result = shell_integration.pin_shortcut(shell_integration.start_menu_shortcut(), "taskbar")
        finally:
            QApplication.restoreOverrideCursor()
        if result in ("pinned", "already"):
            self._inform("Taskbar", "'{0}' was pinned to the taskbar.".format(APP_NAME))
            return
        shell_integration.set_window_relaunch(int(self.list_window.winId()))
        self._inform(
            "Pin to Taskbar",
            "Windows does not allow programs to pin themselves to the taskbar, so the last click is yours:\n\n"
            "1. Right-click the {0} button on the taskbar (it is there now, while the app is running).\n"
            "2. Choose 'Pin to taskbar'.\n\n"
            "The pinned button starts {0} directly, without a console window.\n\n"
            "Another way: open Start > All apps, right-click '{0}' and choose More > 'Pin to taskbar'.".format(APP_NAME))

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
