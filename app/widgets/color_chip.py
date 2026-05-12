"""Palette color chip widgets."""

from __future__ import annotations

from typing import List

from PySide6.QtCore import QTimer, Signal, Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QMenu, QSizePolicy


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

        grad = QLinearGradient(rect.topLeft(), rect.topRight())
        for idx, color in enumerate(colors):
            stop = idx / max(1, len(colors) - 1)
            grad.setColorAt(stop, QColor(color))
        painter.setPen(Qt.NoPen)
        painter.setBrush(grad)
        painter.drawRoundedRect(rect, 16, 16)

        spacing = max(8, min(14, rect.width() // 34))
        dot_size = max(28, min(54, rect.height() - 18, (rect.width() - 36) // max(1, len(colors)) - spacing))
        total = (dot_size * len(colors)) + (spacing * (len(colors) - 1))
        start_x = rect.center().x() - total // 2
        y = rect.center().y() - dot_size // 2
        painter.setPen(QPen(QColor(255, 255, 255, 168), max(2, dot_size // 15)))
        for idx, color in enumerate(colors):
            x = start_x + idx * (dot_size + spacing)
            painter.setBrush(QColor(color))
            painter.drawEllipse(x, y, dot_size, dot_size)


class ColorChip(QFrame):
    clicked = Signal(str)
    delete_requested = Signal(str)
    selected = Signal(str)
    rename_requested = Signal(str)
    copy_color_requested = Signal(str)
    copy_palette_requested = Signal(list, str)

    def __init__(self, palette_id: str, name: str, colors: List[str], parent=None) -> None:
        super().__init__(parent)
        clean = [c.upper() for c in colors]
        self.palette_id = palette_id
        self.name = name
        self.colors = clean if clean else ["#000000"]
        self._highlighted = False
        self._selected = False

        self.setObjectName("paletteChip")
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(12, 12, 12, 12)
        self._layout.setSpacing(8)

        self.preview = QuadPreview(self.colors, self)
        self.label_name = QLabel(self.name, self)
        self.label_name.setObjectName("chipName")
        self.label_code = QLabel(" / ".join(self.colors), self)
        self.label_code.setObjectName("chipCode")
        self.label_code.setToolTip(" / ".join(self.colors))

        self._layout.addWidget(self.preview)
        self._layout.addWidget(self.label_name)
        self._layout.addWidget(self.label_code)
        self.set_card_size(228, 148)

    def set_card_size(self, width: int, height: int) -> None:
        width = max(190, int(width))
        height = max(128, int(height))
        margin = max(10, min(16, width // 22))
        preview_height = max(72, min(height - 62, int(height * 0.48)))

        self.setFixedSize(width, height)
        self._layout.setContentsMargins(margin, margin, margin, margin)
        self.preview.setFixedHeight(preview_height)

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
            self.selected.emit(self.palette_id)
            if self.colors:
                self.clicked.emit(self.colors[0])
        super().mousePressEvent(event)

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        copy_actions = []
        copy_palette_rows_action = None
        copy_palette_line_action = None
        copy_palette_json_action = None
        if len(self.colors) == 1:
            copy_actions.append((menu.addAction("复制颜色代码"), self.colors[0]))
        else:
            for idx, color in enumerate(self.colors[:4]):
                copy_actions.append((menu.addAction(f"复制颜色{idx + 1}"), color))
            menu.addSeparator()
            copy_palette_rows_action = menu.addAction(f"复制整张{len(self.colors[:4])}色卡（多行）")
            copy_palette_line_action = menu.addAction(f"复制整张{len(self.colors[:4])}色卡（一行）")
            copy_palette_json_action = menu.addAction(f"复制整张{len(self.colors[:4])}色卡（JSON）")
        menu.addSeparator()
        rename_action = menu.addAction("重命名色卡")
        delete_action = menu.addAction("删除搭配")
        action = menu.exec(event.globalPos())
        for copy_action, color in copy_actions:
            if action == copy_action:
                self.copy_color_requested.emit(color)
                return
        if copy_palette_rows_action is not None and action == copy_palette_rows_action:
            self.copy_palette_requested.emit(self.colors[:4], "rows")
            return
        if copy_palette_line_action is not None and action == copy_palette_line_action:
            self.copy_palette_requested.emit(self.colors[:4], "line")
            return
        if copy_palette_json_action is not None and action == copy_palette_json_action:
            self.copy_palette_requested.emit(self.colors[:4], "json")
            return
        if action == rename_action:
            self.rename_requested.emit(self.palette_id)
            return
        if action == delete_action:
            self.delete_requested.emit(self.palette_id)

    def paintEvent(self, event):
        super().paintEvent(event)

        if not (self._highlighted or self._selected):
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        accent = QColor("#D9FF51" if self._highlighted else "#8B7CFF")
        glow = QColor(accent)
        glow.setAlpha(44)
        painter.setPen(Qt.NoPen)
        painter.setBrush(glow)
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -2, -2), 24, 24)

        halo = QColor(accent)
        halo.setAlpha(84)
        painter.setPen(QPen(halo, 7))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(self.rect().adjusted(5, 5, -6, -6), 20, 20)

        painter.setPen(QPen(accent, 2))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(self.rect().adjusted(4, 4, -5, -5), 21, 21)
