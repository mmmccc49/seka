"""Palette color chip widgets."""

from __future__ import annotations

from typing import List

from PySide6.QtCore import QTimer, Signal, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QMenu


class QuadPreview(QFrame):
    def __init__(self, colors: List[str], parent=None) -> None:
        super().__init__(parent)
        self._colors = [c.upper() for c in colors] if colors else ["#000000"]
        self.setMinimumHeight(62)
        self.setObjectName("quadPreview")

    def set_colors(self, colors: List[str]) -> None:
        self._colors = [c.upper() for c in colors] if colors else ["#000000"]
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        rect = self.rect().adjusted(1, 1, -1, -1)
        colors = self._colors

        if len(colors) == 1:
            painter.fillRect(rect, QColor(colors[0]))
        else:
            block_w = rect.width() // 2
            block_h = rect.height() // 2
            for idx, color in enumerate(colors[:4]):
                row = idx // 2
                col = idx % 2
                x = rect.x() + col * block_w
                y = rect.y() + row * block_h
                w = block_w if col == 0 else rect.width() - block_w
                h = block_h if row == 0 else rect.height() - block_h
                painter.fillRect(x, y, w, h, QColor(color))

            painter.setPen(QColor(255, 255, 255, 80))
            painter.drawLine(rect.x() + block_w, rect.y() + 2, rect.x() + block_w, rect.bottom() - 2)
            painter.drawLine(rect.x() + 2, rect.y() + block_h, rect.right() - 2, rect.y() + block_h)


class ColorChip(QFrame):
    clicked = Signal(str)
    delete_requested = Signal(str)
    selected = Signal(str)
    rename_requested = Signal(str)

    def __init__(self, name: str, colors: List[str], parent=None) -> None:
        super().__init__(parent)
        clean = [c.upper() for c in colors]
        self.name = name
        self.colors = clean if clean else ["#000000"]
        self._highlighted = False
        self._selected = False

        self.setFixedSize(192, 124)
        self.setObjectName("paletteChip")
        self.setCursor(Qt.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        self.preview = QuadPreview(self.colors, self)
        self.label_name = QLabel(self.name, self)
        self.label_name.setObjectName("chipName")
        self.label_code = QLabel(" / ".join(self.colors), self)
        self.label_code.setObjectName("chipCode")

        layout.addWidget(self.preview)
        layout.addWidget(self.label_name)
        layout.addWidget(self.label_code)

    def set_selected(self, selected: bool) -> None:
        self._selected = selected
        self.update()

    def set_highlight(self) -> None:
        self._highlighted = True
        self.update()
        QTimer.singleShot(700, self._clear_highlight)

    def _clear_highlight(self) -> None:
        self._highlighted = False
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.selected.emit(self.name)
            if self.colors:
                self.clicked.emit(self.colors[0])
        super().mousePressEvent(event)

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        rename_action = menu.addAction("重命名色卡")
        delete_action = menu.addAction("删除搭配")
        action = menu.exec(event.globalPos())
        if action == rename_action:
            self.rename_requested.emit(self.name)
            return
        if action == delete_action:
            self.delete_requested.emit(self.name)

    def paintEvent(self, event):
        super().paintEvent(event)

        if not (self._highlighted or self._selected):
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        border_color = "#F5C47A" if self._highlighted else "#3B82F6"
        pen = QPen(QColor(border_color))
        pen.setWidth(3)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -2, -2), 14, 14)
