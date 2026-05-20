"""AutoWorkflow application entry point.

Usage:
    python -m app.main
    # or from project root:
    python app/main.py
"""
import logging
import sys
from pathlib import Path

# Make sure project root is on sys.path when run as a script
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication

from app.ui.main_window import MainWindow


def setup_logging():
    log_dir = ROOT / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    from datetime import datetime
    log_file = log_dir / f"{datetime.now().strftime('%Y%m%d')}.log"

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    # File handler (UTF-8)
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s"))
    fh.setLevel(logging.DEBUG)
    root.addHandler(fh)
    # Console
    sh = logging.StreamHandler()
    sh.setFormatter(logging.Formatter("%(levelname)s - %(message)s"))
    sh.setLevel(logging.INFO)
    root.addHandler(sh)


def main():
    setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("启动 AutoWorkflow")

    app = QApplication(sys.argv)
    app.setApplicationName("AutoWorkflow")

    win = MainWindow()
    win.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
