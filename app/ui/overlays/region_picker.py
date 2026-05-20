"""Region picker overlay: drag a rectangle to select a screen region.

Returns (left, top, width, height) or None if cancelled.
"""
from typing import Optional, Tuple

from PySide6.QtCore import Qt, QPoint, QRect, Signal, QEventLoop
from PySide6.QtGui import QPainter, QPen, QColor, QFont, QGuiApplication, QKeyEvent, QMouseEvent
from PySide6.QtWidgets import QWidget


Region = Tuple[int, int, int, int]


class RegionPicker(QWidget):
    picked = Signal(int, int, int, int)
    cancelled = Signal()

    def __init__(self):
        super().__init__(None)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.CrossCursor)

        screen = QGuiApplication.primaryScreen()
        self.setGeometry(screen.geometry())

        self._dragging = False
        self._start: QPoint = QPoint()
        self._end: QPoint = QPoint()
        self._result: Optional[Region] = None
        self._loop: Optional[QEventLoop] = None

    def pick(self) -> Optional[Region]:
        self._result = None
        self._loop = QEventLoop()
        self.picked.connect(self._on_picked)
        self.cancelled.connect(self._on_cancelled)

        self.show()
        self.activateWindow()
        self.raise_()
        self.setFocus()
        self._loop.exec()
        return self._result

    def _on_picked(self, x: int, y: int, w: int, h: int):
        self._result = (x, y, w, h)
        self._finish()

    def _on_cancelled(self):
        self._result = None
        self._finish()

    def _finish(self):
        self.hide()
        if self._loop and self._loop.isRunning():
            self._loop.quit()

    # ---------- events ----------
    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.cancelled.emit()
            event.accept()
            return
        super().keyPressEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._start = event.position().toPoint()
            self._end = self._start
            self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._dragging:
            self._end = event.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._dragging:
            self._dragging = False
            self._end = event.position().toPoint()
            rect = self._normalized_rect()
            # Convert to absolute screen coords (widget covers primary screen at 0,0
            # but to be safe, translate by widget geometry)
            geo = self.geometry()
            x = rect.x() + geo.x()
            y = rect.y() + geo.y()
            w = rect.width()
            h = rect.height()
            if w <= 2 or h <= 2:
                # Treat tiny drags as miss-clicks
                self.update()
                return
            self.picked.emit(x, y, w, h)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Dim background
        painter.fillRect(self.rect(), QColor(0, 0, 0, 90))

        if self._dragging or not self._start.isNull():
            rect = self._normalized_rect()
            # Cut a hole (transparent) inside the selection so user sees the target clearly
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
            painter.fillRect(rect, Qt.GlobalColor.transparent)
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)

            pen = QPen(QColor(0, 200, 255))
            pen.setWidth(2)
            painter.setPen(pen)
            painter.drawRect(rect)

            # Size HUD
            font = QFont()
            font.setPointSize(10)
            font.setFamily("Consolas")
            painter.setFont(font)
            hud_text = f"{rect.x()}, {rect.y()}  {rect.width()} x {rect.height()}"
            hud_x = rect.x()
            hud_y = max(0, rect.y() - 24)
            painter.fillRect(hud_x, hud_y, 220, 22, QColor(20, 20, 20, 230))
            painter.setPen(QColor(255, 255, 255))
            painter.drawText(hud_x + 6, hud_y + 16, hud_text)

        # Instruction at top
        instr = "拖拽选择区域  |  Esc 取消"
        painter.setPen(QColor(255, 255, 255))
        font = QFont()
        font.setPointSize(11)
        painter.setFont(font)
        painter.drawText(20, 30, instr)
        painter.end()

    def _normalized_rect(self) -> QRect:
        x1, y1 = self._start.x(), self._start.y()
        x2, y2 = self._end.x(), self._end.y()
        return QRect(min(x1, x2), min(y1, y2), abs(x2 - x1), abs(y2 - y1))
