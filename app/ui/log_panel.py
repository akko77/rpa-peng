"""Log panel: rolling text widget with level coloring and level-based filter.

Also installs a logging handler so module-level logger.info/etc. show here.
"""
import logging
from datetime import datetime
from typing import Optional

from PySide6.QtCore import Qt, Signal, QObject
from PySide6.QtGui import QTextCharFormat, QColor, QTextCursor
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPlainTextEdit, QComboBox, QPushButton, QLabel


LEVEL_ORDER = ["debug", "info", "warning", "error"]
LEVEL_COLORS = {
    "debug": QColor(140, 140, 140),
    "info":  QColor(220, 220, 220),
    "warning": QColor(230, 180, 60),
    "error": QColor(230, 80, 80),
}


class _LoggingBridge(QObject):
    """Bridges Python logging records to a Qt signal."""
    log = Signal(str, str)  # level, message


class _QtLogHandler(logging.Handler):
    def __init__(self, bridge: _LoggingBridge):
        super().__init__()
        self.bridge = bridge

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
        except Exception:
            msg = record.getMessage()
        lvl = record.levelname.lower()
        if lvl == "warn":
            lvl = "warning"
        self.bridge.log.emit(lvl, msg)


class LogPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self._min_level = "info"
        self._bridge = _LoggingBridge()
        self._bridge.log.connect(self.append_log)

        # Install handler on root logger
        self._handler = _QtLogHandler(self._bridge)
        self._handler.setFormatter(logging.Formatter("%(message)s"))
        logging.getLogger().addHandler(self._handler)
        logging.getLogger().setLevel(logging.DEBUG)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel("最低级别:"))
        self.level_combo = QComboBox()
        for lvl in LEVEL_ORDER:
            self.level_combo.addItem(lvl)
        self.level_combo.setCurrentText("info")
        self.level_combo.currentTextChanged.connect(self._on_level_changed)
        toolbar.addWidget(self.level_combo)
        toolbar.addStretch(1)
        clear_btn = QPushButton("清空")
        clear_btn.clicked.connect(self.clear)
        toolbar.addWidget(clear_btn)
        layout.addLayout(toolbar)

        self.text = QPlainTextEdit()
        self.text.setReadOnly(True)
        self.text.setMaximumBlockCount(5000)
        # Monospace and dark background read better for logs
        self.text.setStyleSheet(
            "QPlainTextEdit { background:#1e1e1e; color:#dcdcdc; "
            "font-family: Consolas, 'Courier New', monospace; font-size: 12px; }"
        )
        layout.addWidget(self.text, 1)

    def _on_level_changed(self, text: str):
        self._min_level = text

    def _level_passes(self, level: str) -> bool:
        try:
            return LEVEL_ORDER.index(level) >= LEVEL_ORDER.index(self._min_level)
        except ValueError:
            return True

    def append_log(self, level: str, message: str):
        if not self._level_passes(level):
            return
        ts = datetime.now().strftime("%H:%M:%S")
        prefix = f"[{ts}] [{level.upper()}] "
        cursor = self.text.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)

        fmt = QTextCharFormat()
        fmt.setForeground(LEVEL_COLORS.get(level, LEVEL_COLORS["info"]))
        cursor.insertText(prefix + message + "\n", fmt)
        self.text.setTextCursor(cursor)
        self.text.ensureCursorVisible()

    def clear(self):
        self.text.clear()
