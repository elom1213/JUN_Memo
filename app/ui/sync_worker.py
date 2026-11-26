# -*- coding: utf-8 -*-
# Python Script by Ji Hun Park
# last Update date : 2026-11-26
# JUN_Memo - v01.14 원격 확인을 백그라운드로 (git fetch 가 창을 멈추지 않게). A000080 JUN_Library 의 SyncWorker 와 같다.

from PySide6.QtCore import QThread, Signal


class SyncWorker(QThread):
    done = Signal(object)

    def __init__(self, fn, *args, parent=None):
        super().__init__(parent)
        self._fn = fn
        self._args = args

    def run(self):
        try:
            result = self._fn(*self._args)
        except Exception as exc:                 # noqa: BLE001 - 어떤 실패도 알림 상태로 바꾼다
            result = {"behind": 0, "incoming": [], "app_files": [], "pending": None,
                      "error": "Check failed: {0}".format(exc)}
        self.done.emit(result)
