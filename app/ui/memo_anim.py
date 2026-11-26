# -*- coding: utf-8 -*-
# Python Script by Ji Hun Park
# last Update date : 2026-11-23
# JUN_Memo - Shrink 중에 도는 아이콘 애니메이션 (v01.04)
"""
목록 창을 줄여 둔 동안(Shrink) 끝없이 도는 작은 장면. A00220_BackupTool 의 공룡 · A00370 의 로켓과 같은 자리.

한 바퀴 = PERIOD_MS:
    0.00 ~ 0.14  색 스티커가 위에서 떨어져 살짝 튕기며 자리 잡는다
    0.14 ~ 0.70  연필이 글씨 세 줄을 쓴다 (끝이 줄 끝을 따라가며 손글씨처럼 위아래로 떨린다)
    0.70 ~ 0.80  연필이 비켜나고 압정이 톡 박힌다
    0.80 ~ 1.00  스티커 아래 귀가 들리며 오른쪽으로 날아간다 → 다음 바퀴는 다음 색
쉬는 동안에도 스티커가 아주 조금 흔들린다. 색은 스티커 메모 7색을 차례로.

그림은 전부 QPainter (에셋 없음). 시간은 경과 ms 로 계산하므로 타이머가 늦어도 같은 장면이 나온다.
`set_running(False)` 면 타이머가 멈춘다(펴 둔 동안 CPU 를 쓰지 않는다).
"""

import math

from PySide6.QtCore import QElapsedTimer, QPointF, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import QWidget

from app.core import store as st

PERIOD_MS = 4800
TICK_MS = 33
NOTE = 74              # 스티커 한 변 (px)


def _ease_out_back(x):
    c1, c3 = 1.70158, 2.70158
    return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2


def _clamp(x, lo=0.0, hi=1.0):
    return lo if x < lo else hi if x > hi else x


def _seg(t, a, b):
    """t 가 [a, b] 에서 0~1."""
    return _clamp((t - a) / (b - a))


class MemoAnim(QWidget):
    """줄여 둔 동안의 아이콘. clicked = 펴기 (창이 연결한다)."""

    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(150, 118)
        self.hint = ""                  # v01.14 동기화 알림 점
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("Click to open the notes list again")
        self._colors = list(st.COLORS)
        self._clock = QElapsedTimer()
        self._clock.start()
        self._timer = QTimer(self)
        self._timer.setInterval(TICK_MS)
        self._timer.timeout.connect(self.update)
        self.elapsed_override = None    # 시험용: 이 ms 로 그린다

    # ---------------------------------------------------------------- 상태
    def set_hint(self, kind, tip=""):
        """v01.14 동기화 알림 점 - 'pull'(파랑) / 'push'(주황) / ''(없음). 오른쪽 위에 그린다."""
        if kind == getattr(self, "hint", ""):
            self.setToolTip(tip or "Click to open the notes list")
            return
        self.hint = kind
        self.setToolTip(tip or "Click to open the notes list")
        self.update()

    def set_running(self, on):
        if on and not self._timer.isActive():
            self._clock.restart()
            self._timer.start()
        elif not on:
            self._timer.stop()
        self.update()

    def is_running(self):
        return self._timer.isActive()

    def sizeHint(self):
        return QSize(150, 118)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()

    # ---------------------------------------------------------------- 시간
    def elapsed(self):
        return self.elapsed_override if self.elapsed_override is not None else self._clock.elapsed()

    def frame(self, ms=None):
        """(바퀴 번호, 0~1 진행) - 시험이 장면을 확인할 때도 쓴다."""
        ms = self.elapsed() if ms is None else ms
        return int(ms // PERIOD_MS), (ms % PERIOD_MS) / float(PERIOD_MS)

    def note_color(self, cycle):
        return self._colors[cycle % len(self._colors)]

    # ---------------------------------------------------------------- 그리기
    def paintEvent(self, event):
        cycle, t = self.frame()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        pal = st.palette(self.note_color(cycle))
        cx, cy = 58.0, 64.0                                  # 스티커 가운데 (연필 자리를 오른쪽에 남긴다)

        # ---- 스티커 위치 · 각도
        drop = _seg(t, 0.0, 0.14)
        y_off = (1 - _ease_out_back(drop)) * -90 if drop < 1 else 0.0
        sway = math.sin(t * math.pi * 6) * 1.2               # 쉬는 동안 살짝 흔들림
        fly = _seg(t, 0.80, 1.0)
        x_off = (fly ** 2) * 140
        angle = sway + fly * 28
        peel = _seg(t, 0.78, 0.86)                           # 아래 귀 들림
        alpha = 1.0 - _seg(t, 0.9, 1.0)

        p.save()
        p.setOpacity(alpha)
        p.translate(cx + x_off, cy + y_off)
        p.rotate(angle)
        self._draw_note(p, pal, t, peel)
        p.restore()

        # ---- 연필
        self._draw_pencil(p, t, cx, cy, y_off)

        # ---- v01.14 동기화 알림 점 (Pull = 파랑, Push = 주황)
        hint = getattr(self, "hint", "")
        if hint:
            p.setOpacity(1.0)
            p.setPen(QPen(QColor("#FFFFFF"), 2))
            p.setBrush(QColor("#1A73E8" if hint == "pull" else "#E8710A"))
            p.drawEllipse(QPointF(self.width() - 10.0, 10.0), 7.0, 7.0)
        p.end()

    def _draw_note(self, p, pal, t, peel):
        h = NOTE / 2.0
        fold = 14 + peel * 10
        body = QPainterPath()
        body.moveTo(-h, -h)
        body.lineTo(h, -h)
        body.lineTo(h, h - fold)
        body.lineTo(h - fold, h)
        body.lineTo(-h, h)
        body.closeSubpath()
        # 그림자
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, 40))
        p.drawPath(body.translated(2.5, 3))
        p.setBrush(QColor(pal["body"]))
        p.setPen(QPen(QColor(0, 0, 0, 60), 1))
        p.drawPath(body)
        p.fillRect(QRectF(-h + 0.5, -h + 0.5, NOTE - 1, 11), QColor(pal["header"]))
        p.setBrush(QColor(pal["header"]).darker(110))
        p.drawPolygon(QPolygonF([QPointF(h, h - fold), QPointF(h - fold, h - fold), QPointF(h - fold, h)]))
        # 글씨 세 줄 (연필이 쓴 만큼)
        p.setPen(QPen(QColor(pal["text"]), 2.2, Qt.SolidLine, Qt.RoundCap))
        for i, (x0, w) in enumerate(self._lines()):
            k = self.line_progress(t, i)
            if k <= 0:
                continue
            y = -h + 22 + i * 13
            path = QPainterPath(QPointF(x0, y))
            steps = max(2, int(14 * k))
            for s in range(1, steps + 1):
                xx = x0 + w * k * s / steps
                path.lineTo(xx, y + math.sin(xx * 0.9 + i) * 1.3)
            p.drawPath(path)
        # 압정
        pin = _seg(t, 0.70, 0.76)
        if pin > 0:
            r = 6 * _ease_out_back(pin)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor("#D9363E"))
            p.drawEllipse(QPointF(0, -h + 5), r, r)
            p.setBrush(QColor(255, 255, 255, 150))
            p.drawEllipse(QPointF(-r * 0.3, -h + 5 - r * 0.3), r * 0.3, r * 0.3)

    @staticmethod
    def _lines():
        h = NOTE / 2.0
        return ((-h + 9, NOTE - 22), (-h + 9, NOTE - 30), (-h + 9, NOTE - 40))

    @staticmethod
    def line_progress(t, i):
        """i 번째 줄이 써진 비율 (0~1)."""
        a = 0.16 + i * 0.18
        return _seg(t, a, a + 0.16)

    def pencil_state(self, t):
        """(보이나, 끝 위치 (x, y) 스티커 기준) - 쓰는 줄의 끝을 따라간다."""
        if t < 0.14 or t > 0.78:
            return False, None
        h = NOTE / 2.0
        for i, (x0, w) in enumerate(self._lines()):
            k = self.line_progress(t, i)
            if 0 < k < 1 or (i == 2 and k >= 1):
                y = -h + 22 + i * 13
                x = x0 + w * k
                return True, (x, y + math.sin(t * 90) * 1.5)
        return True, (self._lines()[0][0], -h + 22)

    def _draw_pencil(self, p, t, cx, cy, y_off):
        visible, tip = self.pencil_state(t)
        if not visible:
            return
        leave = _seg(t, 0.68, 0.78)                          # 비켜나기
        arrive = _seg(t, 0.12, 0.18)
        tx = cx + tip[0] + leave * 40
        ty = cy + y_off + tip[1] - leave * 30 - (1 - arrive) * 30
        p.save()
        p.setOpacity(_clamp(arrive * 1.5) * (1 - leave))
        p.translate(tx, ty)
        p.rotate(-40)
        # 몸통 (끝이 원점, 몸은 +x 로)
        p.setPen(QPen(QColor(0, 0, 0, 90), 1))
        p.setBrush(QColor("#F6C343"))
        p.drawRect(QRectF(9, -3.5, 34, 7))
        p.setBrush(QColor("#F28FA6"))
        p.drawRect(QRectF(43, -3.5, 7, 7))
        p.setBrush(QColor("#B9B9B9"))
        p.drawRect(QRectF(41, -3.5, 3, 7))
        p.setBrush(QColor("#F3D9B1"))
        p.drawPolygon(QPolygonF([QPointF(0, 0), QPointF(9, -3.5), QPointF(9, 3.5)]))
        p.setBrush(QColor("#333333"))
        p.drawPolygon(QPolygonF([QPointF(0, 0), QPointF(3, -1.2), QPointF(3, 1.2)]))
        p.restore()
