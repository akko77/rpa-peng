"""Position picker overlay.

Covers all screens with a translucent layer that shows live cursor coordinates
and crosshair guides. F8 captures the current cursor position; Esc cancels.

Usage:
    picker = PositionPicker()
    pos = picker.pick()  # blocks (modal) until user presses F8 or Esc
    # pos is (x, y) or None if cancelled
"""
from typing import Optional, Tuple

from PySide6.QtCore import Qt, QTimer, QPoint, QRect, Signal
from PySide6.QtGui import QPainter, QPen, QColor, QFont, QGuiApplication, QKeyEvent, QCursor
from PySide6.QtWidgets import QWidget


class PositionPicker(QWidget):
    """Modal-style overlay that returns a screen coordinate.

    On Windows with no DPI scaling (per project assumption), QCursor.pos() and
    pyautogui share the same coordinate space.
    """

    picked = Signal(int, int)
    cancelled = Signal()

    def __init__(self):
        super().__init__(None)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        self.setMouseTracking(True)

        # Cover the entire virtual desktop (all screens). For single-screen scope
        # in Phase 1 this is effectively the primary screen.
        screen = QGuiApplication.primaryScreen()
        geo = screen.geometry()
        self.setGeometry(geo)

        self._cursor_pos = QPoint(0, 0)
        self._result: Optional[Tuple[int, int]] = None

        # Timer to update cursor pos even when mouse doesn't move over our widget.
        # (pyautogui-style monitoring: global cursor pos via QCursor.)
        self._timer = QTimer(self)
        self._timer.setInterval(16)  # ~60fps
        self._timer.timeout.connect(self._tick)

    # ---------- public API ----------
    def pick(self) -> Optional[Tuple[int, int]]:
        """Show the overlay and block until the user picks or cancels."""
        from PySide6.QtCore import QEventLoop

        self._result = None
        self._loop = QEventLoop()
        self.picked.connect(self._on_picked)
        self.cancelled.connect(self._on_cancelled)

        self.show()
        self.activateWindow()
        self.raise_()
        self.setFocus()
        self._timer.start()
        self._loop.exec()
        return self._result

    # ---------- internals ----------
    def _on_picked(self, x: int, y: int):
        self._result = (x, y)
        self._cleanup_and_close()

    def _on_cancelled(self):
        self._result = None
        self._cleanup_and_close()

    def _cleanup_and_close(self):
        self._timer.stop()
        self.hide()
        if self._loop and self._loop.isRunning():
            self._loop.quit()

    def _tick(self):
        pos = QCursor.pos()
        if pos != self._cursor_pos:
            self._cursor_pos = pos
            self.update()

    # ---------- Qt events ----------
    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_F8:
            pos = QCursor.pos()
            self.picked.emit(pos.x(), pos.y())
            event.accept()
            return
        if event.key() == Qt.Key.Key_Escape:
            self.cancelled.emit()
            event.accept()
            return
        super().keyPressEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Dim background (very lightly so the user can still see the target)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 40))

        # Crosshair guides (full width/height through cursor)
        # Convert global cursor pos to widget-local coords
        local = self.mapFromGlobal(self._cursor_pos)
        pen = QPen(QColor(0, 200, 255, 200))
        pen.setWidth(1)
        painter.setPen(pen)
        painter.drawLine(0, local.y(), self.width(), local.y())
        painter.drawLine(local.x(), 0, local.x(), self.height())

        # Coordinate HUD: floating box near cursor
        hud_w, hud_h = 180, 60
        hud_x = local.x() + 16
        hud_y = local.y() + 16
        # Keep HUD on-screen
        if hud_x + hud_w > self.width():
            hud_x = local.x() - hud_w - 16
        if hud_y + hud_h > self.height():
            hud_y = local.y() - hud_h - 16

        hud_rect = QRect(hud_x, hud_y, hud_w, hud_h)
        painter.fillRect(hud_rect, QColor(20, 20, 20, 220))
        painter.setPen(QColor(255, 255, 255))
        font = QFont()
        font.setPointSize(11)
        font.setFamily("Consolas")
        painter.setFont(font)
        painter.drawText(
            hud_rect.adjusted(8, 4, -8, -4),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
            f"x: {self._cursor_pos.x()}\ny: {self._cursor_pos.y()}\nF8 抓取  Esc 取消",
        )
        painter.end()
