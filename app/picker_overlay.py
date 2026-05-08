"""Fullscreen picking overlay with realtime magnifier."""

from __future__ import annotations

from typing import Callable, Optional, Tuple

from PySide6.QtCore import QPoint, QRect, QTimer, Qt, Signal
from PySide6.QtGui import QColor, QCursor, QGuiApplication, QImage, QPainter, QPen
from PySide6.QtWidgets import QApplication, QWidget

from .color_utils import format_color

RGB = Tuple[int, int, int]


class PickerOverlay(QWidget):
    picked = Signal(tuple)
    canceled = Signal()

    def __init__(self, format_provider: Callable[[], str], parent=None) -> None:
        super().__init__(parent)
        self._format_provider = format_provider

        self._magnifier_size = 80
        self._sample_size = 15
        self._refresh_ms = 16

        self._cursor_pos = QCursor.pos()
        self._sample_image: Optional[QImage] = None
        self._current_rgb: RGB = (0, 0, 0)
        self._current_text = "#000000"

        self._timer = QTimer(self)
        self._timer.setInterval(self._refresh_ms)
        self._timer.timeout.connect(self._tick)

        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WA_NoMouseReplay, True)
        self.setMouseTracking(True)
        self.setCursor(Qt.CrossCursor)
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.Tool
            | Qt.WindowStaysOnTopHint
            | Qt.BypassWindowManagerHint
        )

    def start(self) -> None:
        self._set_virtual_geometry()
        self.show()
        self.raise_()
        self.activateWindow()
        self.grabKeyboard()
        self.grabMouse()
        self._sample_at_cursor()
        self._timer.start()

    def _set_virtual_geometry(self) -> None:
        screens = QGuiApplication.screens()
        if not screens:
            self.setGeometry(QRect(0, 0, 1920, 1080))
            return

        rect = screens[0].geometry()
        for screen in screens[1:]:
            rect = rect.united(screen.geometry())
        self.setGeometry(rect)
        # Force a non-transparent fill on the whole overlay so mouse events
        # are captured everywhere and never click-through to underlying apps.
        self.setMask(rect.translated(-rect.topLeft()))

    def _tick(self) -> None:
        self._sample_at_cursor()
        self.update()

    def _sample_at_cursor(self) -> None:
        pos = QCursor.pos()
        self._cursor_pos = pos

        screen = QGuiApplication.screenAt(pos)
        if screen is None:
            screen = QGuiApplication.primaryScreen()
        if screen is None:
            return

        geo = screen.geometry()
        half = self._sample_size // 2

        local_x = pos.x() - geo.left()
        local_y = pos.y() - geo.top()

        x = local_x - half
        y = local_y - half

        max_x = geo.width() - self._sample_size
        max_y = geo.height() - self._sample_size

        x = max(0, min(x, max_x))
        y = max(0, min(y, max_y))

        pix = screen.grabWindow(0, x, y, self._sample_size, self._sample_size)
        image = pix.toImage().convertToFormat(QImage.Format_RGB32)
        if image.isNull():
            return

        rx = max(0, min(self._sample_size - 1, local_x - x))
        ry = max(0, min(self._sample_size - 1, local_y - y))

        color = image.pixelColor(rx, ry)
        self._current_rgb = (color.red(), color.green(), color.blue())
        self._current_text = format_color(self._current_rgb, self._format_provider())
        self._sample_image = image

    def mouseMoveEvent(self, event):
        self._cursor_pos = QCursor.pos()
        self.update()
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            event.accept()
            return
        if event.button() == Qt.RightButton:
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._sample_at_cursor()
            QApplication.beep()
            self._finish_pick()
            event.accept()
            return
        if event.button() == Qt.RightButton:
            self._cancel()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self._cancel()
            return
        super().keyPressEvent(event)

    def _cancel(self) -> None:
        self._timer.stop()
        self.releaseKeyboard()
        self.releaseMouse()
        # Delay hide to avoid OS replaying right-click to underlying app.
        QTimer.singleShot(40, self._emit_canceled)

    def _finish_pick(self) -> None:
        self._timer.stop()
        self.releaseKeyboard()
        self.releaseMouse()
        # Delay hide to avoid click replay to underlying app/window.
        QTimer.singleShot(40, self._emit_picked)

    def _emit_canceled(self) -> None:
        self.hide()
        self.canceled.emit()

    def _emit_picked(self) -> None:
        self.hide()
        self.picked.emit(self._current_rgb)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        # Keep full widget non-transparent for hit test; alpha=1 is visually transparent.
        painter.fillRect(self.rect(), QColor(0, 0, 0, 1))

        if self._sample_image is None:
            return

        local_cursor = self._cursor_pos - self.geometry().topLeft()
        box_x, box_y = self._magnifier_anchor(local_cursor)

        panel_rect = QRect(box_x, box_y, self._magnifier_size, self._magnifier_size + 26)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(0, 0, 0, 170))
        painter.drawRoundedRect(panel_rect, 10, 10)

        view_rect = QRect(box_x, box_y, self._magnifier_size, self._magnifier_size)
        zoomed = self._sample_image.scaled(
            self._magnifier_size,
            self._magnifier_size,
            Qt.IgnoreAspectRatio,
            Qt.FastTransformation,
        )
        painter.drawImage(view_rect, zoomed)

        center = self._magnifier_size // 2
        pen = QPen(QColor(255, 255, 255, 220))
        pen.setWidth(1)
        painter.setPen(pen)
        painter.drawLine(box_x + center, box_y, box_x + center, box_y + self._magnifier_size)
        painter.drawLine(box_x, box_y + center, box_x + self._magnifier_size, box_y + center)

        painter.setPen(QColor(255, 255, 255))
        painter.drawText(
            QRect(box_x + 6, box_y + self._magnifier_size + 3, self._magnifier_size - 12, 20),
            Qt.AlignLeft | Qt.AlignVCenter,
            self._current_text,
        )

    def _magnifier_anchor(self, local_cursor: QPoint) -> Tuple[int, int]:
        offset = 15
        pad = 8
        rect = self.rect()
        panel_w = self._magnifier_size
        panel_h = self._magnifier_size + 26

        x = local_cursor.x() + offset
        y = local_cursor.y() + offset

        if x + panel_w + pad > rect.right():
            x = local_cursor.x() - panel_w - offset
        if y + panel_h + pad > rect.bottom():
            y = local_cursor.y() - panel_h - offset

        x = max(rect.left() + pad, min(x, rect.right() - panel_w - pad))
        y = max(rect.top() + pad, min(y, rect.bottom() - panel_h - pad))

        return x, y
