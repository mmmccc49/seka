from __future__ import annotations

from pathlib import Path
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QApplication


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
PNG_PATH = ASSETS / "app_icon.png"
ICO_PATH = ASSETS / "app_icon.ico"


def draw_icon(size: int) -> QPixmap:
    scale = size / 64
    image = QImage(size, size, QImage.Format_ARGB32)
    image.fill(Qt.transparent)

    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor("#1D2027"))
    painter.drawEllipse(
        round(4 * scale),
        round(4 * scale),
        round(56 * scale),
        round(56 * scale),
    )
    pen = QPen(QColor("#FFFFFF"), max(2, round(4 * scale)))
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)
    painter.drawEllipse(
        round(23 * scale),
        round(23 * scale),
        round(18 * scale),
        round(18 * scale),
    )
    painter.end()

    return QPixmap.fromImage(image)


def main() -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    ASSETS.mkdir(parents=True, exist_ok=True)
    draw_icon(256).save(str(PNG_PATH), "PNG")

    icon = QIcon()
    for size in (16, 24, 32, 48, 64, 128, 256):
        icon.addPixmap(draw_icon(size))
    icon.pixmap(256, 256).save(str(ICO_PATH), "ICO")

    if not ICO_PATH.exists():
        raise RuntimeError(f"Failed to create {ICO_PATH}")
    print(f"Generated {ICO_PATH}")
    app.quit()


if __name__ == "__main__":
    main()
