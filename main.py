from __future__ import annotations

import os
import sys
import ctypes

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from app.main_window import MainWindow


def main() -> int:
    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
    os.environ.setdefault("QT_SCALE_FACTOR_ROUNDING_POLICY", "PassThrough")
    if os.name == "nt":
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("ColorMark.MinimalPicker")
        except OSError:
            pass

    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    window = MainWindow()
    app.setWindowIcon(window.windowIcon())
    window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
