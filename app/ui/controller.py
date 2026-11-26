# -*- coding: utf-8 -*-
# Python Script by Ji Hun Park
# last Update date : 2026-11-26
# JUN_Memo - 목록 창 · 노트 창 · 저장소를 잇는다
"""
- 글을 칠 때마다 쓰지 않고 SAVE_MS 뒤에 한 번 저장(마지막 입력 기준). 앱을 끌 때 · 노트를 닫을 때는 바로 저장.
- 노트 창을 닫으면 목록에는 남는다(open=False). **빈 노트는 닫을 때 지운다**(윈도우 스티커 메모처럼).
- 다시 켜면 열려 있던 노트들을 그 자리 · 크기 · 색 · 핀 그대로 다시 연다. 저장된 자리가 지금 화면 밖이면(모니터를 뺐을 때) 주 화면으로.
- v01.01: 노트 범위(Shared = 저장소 shared/notes, This PC = %APPDATA%), 목록 창 색 · Pin · 자리, 시작 메뉴 · 작업 표시줄
  (0110_JUN_Video_Tool 과 같은 셸 통합 - core/shell_integration).
- v01.14 동기화 알림 (A000080 JUN_Library 와 같은 방식): 시작 · 목록 창을 다시 볼 때(1분 넘게 지났으면) · 5분마다
  백그라운드 git fetch → remote(behind · incoming · pending) → 목록 창이 Pull Shared ● · Push Shared ● · 알림 막대로 알린다.
  공유 노트를 저장하면 잠시 뒤 fetch 없이 다시 세어 Push 점을 갱신. git 은 한 번에 하나 - Pull / Push 는 확인이 끝나길 기다린다.
"""

import time

from PySide6.QtCore import QObject, QPoint, QRect, Qt, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication, QMessageBox

from app.config.version import APP_NAME
from app.core import git_sync
from app.core import shell_integration

from app.core import store as st
from app.ui.list_window import ListWindow
from app.ui.note_window import DEFAULT_SIZE, NoteWindow
from app.ui.sync_worker import SyncWorker

SAVE_MS = 500
CHECK_INTERVAL_MS = 5 * 60 * 1000       # v01.14 원격 확인 주기
CHECK_ON_ACTIVATE_SEC = 60.0            # 목록 창을 다시 볼 때 이보다 오래됐으면 확인
PENDING_DELAY_MS = 2000                 # 저장 뒤 안 올린 공유 노트를 다시 세기까지


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
        lw.pushSharedRequested.connect(self.push_shared)
        lw.pullSharedRequested.connect(self.pull_shared)        # v01.13
        lw.activated.connect(self.window_activated)              # v01.14
        lw.checkRemoteToggled.connect(self.set_check_remote)
        lw.checkNowRequested.connect(lambda: self.check_remote())
        self.messages = []                          # 마지막 안내 문구들 (시험이 본다)
        self.quiet = False                          # True 면 메시지 창을 띄우지 않는다 (시험)
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(SAVE_MS)
        self._save_timer.timeout.connect(self.save_now)
        # v01.14 동기화 알림
        self.remote = {"behind": 0, "incoming": [], "app_files": [], "pending": [], "error": "", "checked": False}
        self.auto_check = False                     # start() 가 켠다 (quiet 시험에서는 꺼짐)
        self._checker = None
        self._recount = False                       # 확인 중에 저장됨 → 끝나면 fetch 없이 다시 센다
        self._last_check = 0.0
        self._closing = False
        self._check_timer = QTimer(self)
        self._check_timer.setInterval(CHECK_INTERVAL_MS)
        self._check_timer.timeout.connect(self.check_remote)
        self._pending_timer = QTimer(self)
        self._pending_timer.setSingleShot(True)
        self._pending_timer.setInterval(PENDING_DELAY_MS)
        self._pending_timer.timeout.connect(lambda: self.check_remote(fetch=False))
        app = QApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self.shutdown)

    # ---------------------------------------------------------------- 시작 · 끝
    def start(self):
        """목록 창을 보이고, 지난번 열려 있던 노트들을 다시 연다."""
        self.list_window.show()
        if self.store.list_view.get("shrunk"):                  # v01.04 줄여 둔 채 껐으면 줄인 채로
            self.list_window.set_shrunk(True, emit=False)
        for note in sorted(self.store.notes.values(), key=lambda n: n["created"]):
            if note["open"]:
                self.open_note(note["id"])
        if self.store.error:
            print("[JUN_Memo] " + self.store.error)
        if QGuiApplication.platformName() == "windows":
            # 작업 표시줄 버튼을 우클릭 → 고정했을 때 python 이 아니라 이 앱이 실행되게 (Video Tool 과 같은 방식)
            QTimer.singleShot(0, lambda: shell_integration.set_window_relaunch(int(self.list_window.winId())))
        # v01.14 원격 확인 - 시험(quiet)에서는 저절로 돌지 않는다
        self.auto_check = not self.quiet
        if self.auto_check:
            QTimer.singleShot(0, lambda: self.check_remote(fetch=False))      # 지난번 남긴 안 올린 노트 먼저
            if self.check_enabled():
                QTimer.singleShot(1500, self.check_remote)
                self._check_timer.start()

    def shutdown(self):
        self._closing = True
        self._check_timer.stop()
        self._pending_timer.stop()
        self._wait_checker()
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
        if self.auto_check and not self._closing:
            self._pending_timer.start()             # v01.14 Push Shared ● 갱신 (모아서 한 번)

    def _pull_content(self, note_id):
        win = self.windows.get(note_id)
        if win is None:
            return False
        html, text = win.content()
        titled = self.store.set_title(note_id, win.note_title())     # v01.09 닫거나 끌 때 제목도 놓치지 않게
        return self.store.set_content(note_id, html, text) or titled

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
        win.titleChanged.connect(self._on_title)                    # v01.09
        win.geometryChanged.connect(self._on_geometry)
        win.closedByUser.connect(self._on_closed)
        win.newNoteRequested.connect(self._on_new_from)
        win.listRequested.connect(self.list_window.bring_to_front)
        win.deleteRequested.connect(self.delete_note)
        win.colorChanged.connect(self.set_color)
        win.pinChanged.connect(self.set_pinned)
        win.scopeChanged.connect(self.set_scope)
        win.zoomChanged.connect(self._on_zoom)
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

    def _on_zoom(self, note_id, value):
        """v01.05 노트 글자 크기 - 이 PC 의 보기 상태(state.json)."""
        if self.store.update(note_id, zoom=value):
            self.schedule_save()

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

    def push_shared(self):
        """v01.03 Push Shared - 열린 노트까지 저장하고 공유 노트(shared/notes)만 커밋 · 푸시 (core/git_sync)."""
        for note_id in list(self.windows):
            self._pull_content(note_id)
        self.save_now()
        self._wait_checker()                        # v01.14 git 은 한 번에 하나
        lw = self.list_window
        lw.btn_push.setEnabled(False)
        lw.btn_push.setText("Pushing...")
        QApplication.setOverrideCursor(Qt.WaitCursor)
        QApplication.processEvents()
        try:
            result = git_sync.push_shared(self.store.shared_dir)
        finally:
            QApplication.restoreOverrideCursor()
            lw.btn_push.setText("Push Shared")
            lw.btn_push.setEnabled(True)
        self.last_push = result
        text = result.message
        if result.pulled:
            added, changed, removed = self.store.reload_shared()
            self.list_window.refresh()
            text += "\nFrom the other PC: {0} new, {1} changed, {2} removed.".format(added, changed, removed)
        self.recount_now()
        self._inform("Push Shared", text, warn=result.status in ("error", "blocked"))

    def pull_shared(self):
        """v01.13 Pull Shared - 열린 노트까지 저장하고 git pull --rebase --autostash (core/git_sync), 받은 공유 노트를
        목록에 읽고, 내용이 바뀐 열린 공유 노트는 창을 같은 자리에 다시 연다(옛 내용으로 덮어쓰지 않게)."""
        for note_id in list(self.windows):
            self._pull_content(note_id)
            self._pull_geometry(note_id)
        self.save_now()
        self._wait_checker()                        # v01.14 git 은 한 번에 하나
        lw = self.list_window
        lw.btn_pull.setEnabled(False)
        lw.btn_pull.setText("Pulling...")
        QApplication.setOverrideCursor(Qt.WaitCursor)
        QApplication.processEvents()
        try:
            result = git_sync.pull_shared(self.store.shared_dir)
        finally:
            QApplication.restoreOverrideCursor()
            lw.btn_pull.setText("Pull Shared")
            lw.btn_pull.setEnabled(True)
        self.last_pull = result
        text = result.message
        if result.status == "pulled":
            added, changed, removed = self.store.reload_shared(include_open=True)
            for note_id in self.store.reloaded_open:
                win = self.windows.pop(note_id, None)
                if win is not None:
                    win.close_quietly()
                    self.open_note(note_id)
            self.list_window.refresh()
            self.save_now()
            text += "\nIn the list: {0} new, {1} changed, {2} removed.".format(added, changed, removed)
            if self.store.reloaded_open:
                text += "\n{0} open note(s) were refreshed with the new text.".format(len(self.store.reloaded_open))
        self.recount_now()
        self._inform("Pull Shared", text, warn=result.status == "error")

    # ---------------------------------------------------------------- v01.14 동기화 알림
    def check_enabled(self):
        return bool(self.store.list_view.get("check_remote", True))

    def set_check_remote(self, on):
        self.store.list_view["check_remote"] = bool(on)
        self.save_now()
        if on and self.auto_check:
            self._check_timer.start()
            self.check_remote()
        else:
            self._check_timer.stop()

    def check_remote(self, fetch=True):
        """백그라운드로 (git fetch +) 원격과 비교. 이미 확인 중이면 건너뛴다(저장 뒤 다시 세기는 끝난 뒤로 미룬다)."""
        if self._closing:
            return False
        if self._checker is not None:
            if not fetch:
                self._recount = True
            return False
        if fetch:
            self._last_check = time.monotonic()
        self._checker = SyncWorker(git_sync.remote_status, self.store.shared_dir, fetch)
        self._checker.done.connect(self._remote_checked)
        self._checker.finished.connect(self._checker_finished)
        self._checker.start()
        return True

    def _wait_checker(self):
        """확인이 돌고 있으면 끝나길 기다린다 (Pull / Push 의 git 과 겹치지 않게, fetch 는 30초 상한)."""
        if self._checker is not None:
            self._checker.wait(40000)
            QApplication.processEvents()            # done · finished 신호 처리

    def recount_now(self):
        """Pull / Push 직후 - fetch 없이 바로 다시 센다 (방금 원격을 봤다)."""
        self._remote_checked(git_sync.remote_status(self.store.shared_dir, fetch=False))

    def window_activated(self):
        """목록 창을 다시 볼 때 - 마지막 확인이 1분 넘었으면 다시 확인."""
        if self.auto_check and self.check_enabled() and time.monotonic() - self._last_check > CHECK_ON_ACTIVATE_SEC:
            self.check_remote()

    def _remote_checked(self, state):
        if not isinstance(state, dict):
            return
        state = dict(state)
        if state.get("pending") is None:            # 워커가 실패하면 안 올린 목록은 그대로 둔다
            state["pending"] = self.remote.get("pending", [])
        self.remote = dict(state, checked=True)
        self.list_window.set_sync(self.remote, self.remote_text(), self.push_text())

    def _checker_finished(self):
        self._checker = None
        if self._recount and not self._closing:
            self._recount = False
            self.check_remote(fetch=False)

    def remote_text(self):
        """알림 막대 · 툴팁 문구 (영어)."""
        n = self.remote.get("behind", 0)
        shared = len(self.remote.get("incoming", []))
        if shared:
            return "New on GitHub: {0} shared note file{1} from another PC - Pull to get {2}.".format(
                shared, "" if shared == 1 else "s", "it" if shared == 1 else "them")
        return "New on GitHub: {0} commit{1} (app files only) - Pull to get the latest.".format(
            n, "" if n == 1 else "s")

    def push_text(self):
        n = len(self.remote.get("pending", []))
        return "{0} shared note file{1} not pushed yet - Push to back {2} up to GitHub.".format(
            n, "" if n == 1 else "s", "it" if n == 1 else "them")

    def set_pinned(self, note_id, on):
        if self.store.update(note_id, pinned=bool(on)):
            self.save_now()

    # ---------------------------------------------------------------- 창 알림
    def _on_content(self, note_id):
        if self._pull_content(note_id):
            self.schedule_save()

    def _on_title(self, note_id, title):
        """v01.09 제목 - 치는 동안 모아서 저장(저장하며 목록도 다시 그린다)."""
        if self.store.set_title(note_id, title):
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
