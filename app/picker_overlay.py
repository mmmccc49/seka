"""Fullscreen picking overlay with realtime magnifier."""

from __future__ import annotations

from typing import Callable, List, Optional, Tuple

from PySide6.QtCore import QPoint, QRect, QTimer, Qt, Signal
from PySide6.QtGui import QColor, QCursor, QGuiApplication, QImage, QPainter, QPen
from PySide6.QtWidgets import QApplication, QWidget

from .color_utils import all_formats

RGB = Tuple[int, int, int]


class PickerOverlay(QWidget):
    picked = Signal(list)
    canceled = Signal()

    def __init__(self, format_provider: Callable[[], str], parent=None) -> None:
        super().__init__(parent)
        self._format_provider = format_provider

        self._magnifier_size = 96
        self._sample_size = 15
        self._refresh_ms = 16

        self._cursor_pos = QCursor.pos()
        self._sample_image: Optional[QImage] = None
        self._current_rgb: RGB = (0, 0, 0)
        self._current_formats = {"HEX": "#000000", "RGB": "rgb(0, 0, 0)", "HSL": "hsl(0, 0%, 0%)"}
        self._frozen = False

        self._max_picks = 1
        self._captured: List[RGB] = []

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

    def start(self, max_picks: int = 1) -> None:
        self._max_picks = max(1, min(4, int(max_picks)))
        self._captured = []
        self._frozen = False
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
        self.setMask(rect.translated(-rect.topLeft()))

    def _tick(self) -> None:
        if not self._frozen:
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
        self._current_formats = all_formats(self._current_rgb)
        self._sample_image = image

    def mouseMoveEvent(self, event):
        self._cursor_pos = QCursor.pos()
        if self._frozen:
            self.update()
            super().mouseMoveEvent(event)
            return
        self.update()
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event):
        if event.button() in (Qt.LeftButton, Qt.RightButton):
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            if not self._frozen:
                self._sample_at_cursor()
            self._captured.append(self._current_rgb)
            QApplication.beep()
            if len(self._captured) >= self._max_picks:
                self._finish_pick()
            event.accept()
            return

        if event.button() == Qt.RightButton:
            if self._max_picks > 1 and self._captured:
                self._finish_pick()
            else:
                self._cancel()
            event.accept()
            return

        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self._cancel()
            return
        if event.key() == Qt.Key_Space:
            self._frozen = not self._frozen
            self.update()
            return
        if event.key() in (Qt.Key_Backspace, Qt.Key_Delete) and self._captured:
            self._captured.pop()
            self.update()
            return
        if event.key() in (Qt.Key_Return, Qt.Key_Enter) and self._captured:
            self._finish_pick()
            return
        if event.key() in (Qt.Key_Plus, Qt.Key_Equal, Qt.Key_BracketRight):
            self._magnifier_size = min(144, self._magnifier_size + 8)
            self.update()
            return
        if event.key() in (Qt.Key_Minus, Qt.Key_BracketLeft):
            self._magnifier_size = max(72, self._magnifier_size - 8)
            self.update()
            return
        super().keyPressEvent(event)

    def wheelEvent(self, event) -> None:
        delta = event.angleDelta().y()
        if delta:
            self._magnifier_size = max(72, min(144, self._magnifier_size + (8 if delta > 0 else -8)))
            self.update()
            event.accept()
            return
        super().wheelEvent(event)

    def _cancel(self) -> None:
        self._timer.stop()
        self.releaseKeyboard()
        self.releaseMouse()
        QTimer.singleShot(40, self._emit_canceled)

    def _finish_pick(self) -> None:
        self._timer.stop()
        self.releaseKeyboard()
        self.releaseMouse()
        QTimer.singleShot(40, self._emit_picked)

    def _emit_canceled(self) -> None:
        self.hide()
        self.canceled.emit()

    def _emit_picked(self) -> None:
        self.hide()
        self.picked.emit(list(self._captured))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 1))

        if self._sample_image is None:
            return

        local_cursor = self._cursor_pos - self.geometry().topLeft()
        box_x, box_y = self._magnifier_anchor(local_cursor)

        panel_w = max(self._magnifier_size + 18, 194)
        panel_h = self._magnifier_size + 116
        panel_rect = QRect(box_x, box_y, panel_w, panel_h)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(0, 0, 0, 170))
        painter.drawRoundedRect(panel_rect, 10, 10)

        view_rect = QRect(box_x + 9, box_y + 9, self._magnifier_size, self._magnifier_size)
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
        painter.drawLine(view_rect.left() + center, view_rect.top(), view_rect.left() + center, view_rect.bottom())
        painter.drawLine(view_rect.left(), view_rect.top() + center, view_rect.right(), view_rect.top() + center)

        painter.setPen(QColor(255, 255, 255))
        text_x = box_x + 10
        text_y = box_y + self._magnifier_size + 15
        painter.drawText(
            QRect(text_x, text_y, panel_w - 20, 18),
            Qt.AlignLeft | Qt.AlignVCenter,
            f"{self._current_formats['HEX']}  {self._captured_label()}",
        )

        painter.setPen(QColor(230, 230, 230))
        painter.drawText(
            QRect(text_x, text_y + 19, panel_w - 20, 18),
            Qt.AlignLeft | Qt.AlignVCenter,
            self._current_formats["RGB"],
        )
        painter.drawText(
            QRect(text_x, text_y + 38, panel_w - 20, 18),
            Qt.AlignLeft | Qt.AlignVCenter,
            self._current_formats["HSL"],
        )

        painter.setPen(QColor(205, 205, 205))
        hint = "Space 锁定" if not self._frozen else "已锁定"
        painter.drawText(
            QRect(text_x, text_y + 58, panel_w - 20, 18),
            Qt.AlignLeft | Qt.AlignVCenter,
            f"{hint}  右键结束/取消",
        )

        if self._captured:
            swatch_y = text_y + 82
            for idx, rgb in enumerate(self._captured[:4]):
                painter.setPen(QPen(QColor(255, 255, 255, 190), 1))
                painter.setBrush(QColor(*rgb))
                painter.drawRoundedRect(QRect(text_x + idx * 26, swatch_y, 20, 14), 4, 4)

    def _captured_label(self) -> str:
        return f"{len(self._captured)}/{self._max_picks}"

    def _panel_size(self) -> Tuple[int, int]:
        return max(self._magnifier_size + 18, 194), self._magnifier_size + 116

    def _magnifier_anchor(self, local_cursor: QPoint) -> Tuple[int, int]:
        offset = 15
        pad = 8
        rect = self.rect()
        panel_w, panel_h = self._panel_size()

        x = local_cursor.x() + offset
        y = local_cursor.y() + offset

        if x + panel_w + pad > rect.right():
            x = local_cursor.x() - panel_w - offset
        if y + panel_h + pad > rect.bottom():
            y = local_cursor.y() - panel_h - offset

        x = max(rect.left() + pad, min(x, rect.right() - panel_w - pad))
        y = max(rect.top() + pad, min(y, rect.bottom() - panel_h - pad))

        return x, y
