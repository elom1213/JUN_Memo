# -*- coding: utf-8 -*-
# Python Script by Ji Hun Park
# last Update date : 2026-11-23
# JUN_Memo - 실행:  pythonw launch.py   (또는 Run_JUN_Memo.bat)
"""
윈도우 스티커 메모 같은 독립 실행 앱 (PySide6).

- 한 번만 실행: 이미 떠 있으면 새로 띄우지 않고 그 앱의 노트 목록 창을 앞으로 부른다(QLocalServer).
- 작업 표시줄 아이콘: 앱 ID(AUMID)를 따로 줘서 python 아이콘이 아니라 이 앱 아이콘으로 묶인다.
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from PySide6.QtCore import QPointF, QRectF, Qt   # noqa: E402
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap, QPolygonF   # noqa: E402
from PySide6.QtNetwork import QLocalServer, QLocalSocket   # noqa: E402
from PySide6.QtWidgets import QApplication   # noqa: E402

from app.config.version import APP_USER_MODEL_ID as APP_ID   # noqa: E402  (시작 메뉴 바로가기와 같은 앱 ID)
SERVER_NAME = "JUN_Memo_single_instance_" + (os.environ.get("USERNAME") or "user")
ICON_DIR = os.path.join(HERE, "icon")


def paint_icon(size=256):
    """노랑 스티커 한 장(접힌 귀 + 줄 세 개)."""
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    s = size / 256.0
    m, fold = 28 * s, 56 * s
    body = QPainterPath()
    body.moveTo(m, m)
    body.lineTo(size - m, m)
    body.lineTo(size - m, size - m - fold)
    body.lineTo(size - m - fold, size - m)
    body.lineTo(m, size - m)
    body.closeSubpath()
    p.setPen(QPen(QColor("#C9A800"), max(1.0, 4 * s)))
    p.setBrush(QColor("#FFE066"))
    p.drawPath(body)
    p.setBrush(QColor("#F2C200"))
    p.drawPolygon(QPolygonF([QPointF(size - m, size - m - fold), QPointF(size - m - fold, size - m - fold),
                             QPointF(size - m - fold, size - m)]))
    p.fillRect(QRectF(m, m, size - 2 * m, 30 * s), QColor("#FFD43B"))
    p.setPen(QPen(QColor("#8A7300"), max(1.0, 10 * s), Qt.SolidLine, Qt.RoundCap))
    for i, w in enumerate((0.62, 0.52, 0.36)):
        y = m + (88 + i * 42) * s
        p.drawLine(QPointF(m + 26 * s, y), QPointF(m + 26 * s + (size - 2 * m - 52 * s) * w / 0.62 * 0.62, y))
    p.end()
    return pm


def app_icon():
    path = os.path.join(ICON_DIR, "JUN_Memo.ico")
    if os.path.isfile(path):
        return QIcon(path)
    icon = QIcon()
    for s in (16, 24, 32, 48, 64, 128, 256):
        icon.addPixmap(paint_icon(s))
    return icon


def _set_app_id():
    if sys.platform != "win32":
        return
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
    except Exception:                                      # noqa: BLE001
        pass


def _already_running():
    """이미 떠 있으면 "show" 를 보내고 True."""
    sock = QLocalSocket()
    sock.connectToServer(SERVER_NAME)
    if sock.waitForConnected(300):
        sock.write(b"show")
        sock.flush()
        sock.waitForBytesWritten(300)
        sock.disconnectFromServer()
        return True
    return False


def _serve(controller):
    """두 번째 실행이 보낸 "show" 를 받으면 목록 창을 앞으로."""
    server = QLocalServer()
    QLocalServer.removeServer(SERVER_NAME)          # 지난번 비정상 종료로 남은 이름
    server.listen(SERVER_NAME)

    def on_connection():
        # 주고받는 말은 "show" 하나뿐이라 연결이 오기만 하면 앞으로 부른다 - 보낸 쪽이 먼저 끊으면 글을 못 읽는 일이 있었다
        conn = server.nextPendingConnection()
        controller.list_window.bring_to_front()
        if conn is not None:
            conn.disconnectFromServer()
            conn.deleteLater()

    server.newConnection.connect(on_connection)
    return server


def run():
    _set_app_id()
    app = QApplication.instance() or QApplication(sys.argv)
    if _already_running():
        return 0
    app.setApplicationName("JUN Memo")
    app.setQuitOnLastWindowClosed(True)
    app.setWindowIcon(app_icon())
    from app.ui.controller import Controller
    controller = Controller()
    server = _serve(controller)
    controller.start()
    code = app.exec()
    server.close()
    return code


if __name__ == "__main__":
    sys.exit(run())
