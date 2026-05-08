"""Main window for the desktop color picker app."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QColor, QCloseEvent, QGuiApplication, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSystemTrayIcon,
    QInputDialog,
    QVBoxLayout,
    QWidget,
)

from .color_utils import all_formats, build_harmony_palette, format_color, hex_to_rgb, normalize_hex, rgb_to_hex
from .hotkey import GlobalHotkeyManager
from .picker_overlay import PickerOverlay
from .storage import AppState, StateStore
from .theme import build_stylesheet
from .widgets.color_chip import ColorChip


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("极简取色工具")
        self.resize(1120, 680)
        self.setMinimumSize(1020, 620)

        self.store = StateStore()
        self.state: AppState = self.store.load()

        self._is_picking = False
        self._force_exit = False
        self._chips: List[ColorChip] = []
        self._selected_palette_names: set[str] = set()

        self.overlay = PickerOverlay(self.get_copy_format)
        self.overlay.picked.connect(self._on_color_picked)
        self.overlay.canceled.connect(self._on_pick_canceled)

        self._build_ui()
        self._init_tray()
        self._init_hotkey()

        self.apply_theme(self.state.theme)
        self.refresh_all_views()

    def _build_ui(self) -> None:
        root = QWidget(self)
        self.setCentralWidget(root)

        outer = QHBoxLayout(root)
        outer.setContentsMargins(22, 22, 22, 22)
        outer.setSpacing(16)

        self.palette_card = QFrame(self)
        self.palette_card.setObjectName("card")
        palette_layout = QVBoxLayout(self.palette_card)
        palette_layout.setContentsMargins(18, 18, 18, 18)
        palette_layout.setSpacing(12)

        palette_title = QLabel("高级配色卡", self.palette_card)
        palette_title.setObjectName("title")
        palette_sub = QLabel("点击色卡可选中；右键删除/重命名；支持单色/4色", self.palette_card)
        palette_sub.setObjectName("subtitle")

        self.palette_scroll = QScrollArea(self.palette_card)
        self.palette_scroll.setWidgetResizable(True)
        self.palette_scroll.setFrameShape(QFrame.NoFrame)
        self.palette_wrap = QWidget(self.palette_scroll)
        self.palette_grid = QGridLayout(self.palette_wrap)
        self.palette_grid.setContentsMargins(0, 0, 0, 0)
        self.palette_grid.setHorizontalSpacing(10)
        self.palette_grid.setVerticalSpacing(10)
        self.palette_scroll.setWidget(self.palette_wrap)

        palette_ops_row1 = QHBoxLayout()
        self.add_to_palette_btn = QPushButton("将当前颜色生成4色卡", self.palette_card)
        self.add_single_color_btn = QPushButton("将当前颜色生成为单色卡", self.palette_card)
        self.delete_selected_btn = QPushButton("删除选定配色卡", self.palette_card)
        self.merge_selected_btn = QPushButton("合并4个单色色卡", self.palette_card)

        self.add_to_palette_btn.clicked.connect(self.add_current_to_palette)
        self.add_single_color_btn.clicked.connect(self.add_single_color_palette)
        self.delete_selected_btn.clicked.connect(self.delete_selected_palette)
        self.merge_selected_btn.clicked.connect(self.merge_selected_mono_palettes)

        palette_ops_row1.addWidget(self.add_to_palette_btn)
        palette_ops_row1.addWidget(self.add_single_color_btn)
        palette_ops_row1.addWidget(self.delete_selected_btn)
        palette_ops_row1.addWidget(self.merge_selected_btn)

        palette_ops_row2 = QHBoxLayout()
        self.export_txt_btn = QPushButton("导出 TXT", self.palette_card)
        self.export_json_btn = QPushButton("导出 JSON", self.palette_card)

        self.export_txt_btn.clicked.connect(lambda: self.export_palette("txt"))
        self.export_json_btn.clicked.connect(lambda: self.export_palette("json"))

        palette_ops_row2.addWidget(self.export_txt_btn)
        palette_ops_row2.addWidget(self.export_json_btn)

        palette_layout.addWidget(palette_title)
        palette_layout.addWidget(palette_sub)
        palette_layout.addWidget(self.palette_scroll, 1)
        palette_layout.addLayout(palette_ops_row1)
        palette_layout.addLayout(palette_ops_row2)

        self.control_card = QFrame(self)
        self.control_card.setObjectName("card")
        control_layout = QVBoxLayout(self.control_card)
        control_layout.setContentsMargins(18, 18, 18, 18)
        control_layout.setSpacing(12)

        title = QLabel("屏幕取色", self.control_card)
        title.setObjectName("title")
        subtitle = QLabel("点击按钮进入全屏取色模式（鼠标右键取消）", self.control_card)
        subtitle.setObjectName("subtitle")

        control_layout.addWidget(title)
        control_layout.addWidget(subtitle)

        pick_zone = QFrame(self.control_card)
        pick_zone.setObjectName("card")
        pick_zone_layout = QVBoxLayout(pick_zone)
        pick_zone_layout.setContentsMargins(14, 14, 14, 14)
        pick_zone_layout.setSpacing(0)

        self.pick_btn = QPushButton("开始取色", pick_zone)
        self.pick_btn.setObjectName("pickButton")
        self.pick_btn.clicked.connect(self.start_pick_mode)
        pick_zone_layout.addWidget(self.pick_btn)

        control_layout.addWidget(pick_zone)

        option_panel = QFrame(self.control_card)
        option_panel.setObjectName("card")
        option_layout = QVBoxLayout(option_panel)
        option_layout.setContentsMargins(12, 12, 12, 12)
        option_layout.setSpacing(8)

        options_row = QHBoxLayout()
        self.format_combo = QComboBox(self.control_card)
        self.format_combo.addItems(["HEX", "RGB", "HSL"])
        self.format_combo.setCurrentText(self.state.copy_format)
        self.format_combo.currentTextChanged.connect(self._on_format_changed)

        self.theme_combo = QComboBox(self.control_card)
        self.theme_combo.addItems(["月白", "暗黑"])
        self.theme_combo.setCurrentIndex(0 if self.state.theme == "moonlight" else 1)
        self.theme_combo.currentIndexChanged.connect(self._on_theme_changed)

        options_row.addWidget(QLabel("复制格式", self.control_card))
        options_row.addWidget(self.format_combo)
        options_row.addSpacing(10)
        options_row.addWidget(QLabel("主题", self.control_card))
        options_row.addWidget(self.theme_combo)
        option_layout.addLayout(options_row)

        self.last_hex_edit = self._readonly_line("-")
        self.last_rgb_edit = self._readonly_line("-")
        self.last_hsl_edit = self._readonly_line("-")

        option_layout.addWidget(QLabel("最后取色 HEX", self.control_card))
        option_layout.addWidget(self.last_hex_edit)
        option_layout.addWidget(QLabel("最后取色 RGB", self.control_card))
        option_layout.addWidget(self.last_rgb_edit)
        option_layout.addWidget(QLabel("最后取色 HSL", self.control_card))
        option_layout.addWidget(self.last_hsl_edit)

        control_layout.addWidget(option_panel)

        history_title = QLabel("历史记录（最近 10 次）", self.control_card)
        history_title.setObjectName("subtitle")
        self.history_list = QListWidget(self.control_card)
        self.history_list.itemClicked.connect(self.copy_from_history)
        control_layout.addWidget(history_title)
        control_layout.addWidget(self.history_list, 1)

        self.status_label = QLabel("就绪", self.control_card)
        self.status_label.setObjectName("subtitle")
        self.status_label.setWordWrap(True)
        control_layout.addWidget(self.status_label)

        outer.addWidget(self.palette_card, 58)
        outer.addWidget(self.control_card, 42)

    def _readonly_line(self, text: str) -> QLineEdit:
        edit = QLineEdit(text, self)
        edit.setReadOnly(True)
        edit.setMinimumHeight(30)
        edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        return edit

    def _init_tray(self) -> None:
        self.tray = QSystemTrayIcon(self)
        self.tray.setIcon(self._create_app_icon())
        self.tray.setToolTip("极简取色工具")

        menu = QMenu(self)
        show_action = QAction("显示主窗口", self)
        pick_action = QAction("屏幕取色", self)
        exit_action = QAction("退出程序", self)

        show_action.triggered.connect(self.restore_main_window)
        pick_action.triggered.connect(self.start_pick_mode)
        exit_action.triggered.connect(self.exit_app)

        menu.addAction(show_action)
        menu.addAction(pick_action)
        menu.addSeparator()
        menu.addAction(exit_action)

        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()

    def _init_hotkey(self) -> None:
        self.hotkey = GlobalHotkeyManager(QGuiApplication.instance())
        self.hotkey.activated.connect(self.start_pick_mode)
        if self.hotkey.register():
            self.status_label.setText("全局快捷键已启用：Ctrl+Shift+C")
        else:
            self.status_label.setText("快捷键注册失败，仍可用按钮取色")

    def _create_app_icon(self) -> QIcon:
        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#1A1A1D"))
        painter.drawEllipse(4, 4, 56, 56)
        painter.setBrush(QColor("#F6F3EE"))
        painter.drawEllipse(20, 20, 24, 24)
        painter.end()
        return QIcon(pixmap)

    def apply_theme(self, theme: str) -> None:
        normalized = "dark" if theme == "dark" else "moonlight"
        self.state.theme = normalized
        self.setStyleSheet(build_stylesheet(normalized))

    def _on_theme_changed(self, index: int) -> None:
        self.apply_theme("moonlight" if index == 0 else "dark")
        self.persist_state()

    def _on_format_changed(self, text: str) -> None:
        self.state.copy_format = text.upper()
        self.refresh_history_list()
        self.persist_state()

    def get_copy_format(self) -> str:
        return self.state.copy_format

    def start_pick_mode(self) -> None:
        if self._is_picking:
            return
        self._is_picking = True
        self.hide()
        self.overlay.start()

    def _on_pick_canceled(self) -> None:
        self._is_picking = False
        self.restore_main_window()
        self.status_label.setText("已取消取色")

    def _on_color_picked(self, rgb_tuple) -> None:
        self._is_picking = False
        hex_color = rgb_to_hex(rgb_tuple)

        self.state.last_color = hex_color
        self.state.history.insert(0, hex_color)
        self.state.history = self.state.history[:10]

        copy_text = format_color(rgb_tuple, self.state.copy_format)
        QGuiApplication.clipboard().setText(copy_text)

        self._highlight_if_exists(hex_color)
        self.refresh_all_views()
        self.persist_state()
        self.restore_main_window()

        self.status_label.setText(f"已复制 {copy_text}")

    def _highlight_if_exists(self, hex_color: str) -> None:
        target = hex_color.upper()
        for chip in self._chips:
            if target in [c.upper() for c in chip.colors]:
                chip.set_highlight()

    def restore_main_window(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()

    def refresh_all_views(self) -> None:
        self.refresh_last_color_views()
        self.refresh_history_list()
        self.refresh_palette_grid()

    def refresh_last_color_views(self) -> None:
        if not self.state.last_color:
            self.last_hex_edit.setText("-")
            self.last_rgb_edit.setText("-")
            self.last_hsl_edit.setText("-")
            return

        hex_color = normalize_hex(self.state.last_color)
        rgb = hex_to_rgb(hex_color)
        formats = all_formats(rgb)
        self.last_hex_edit.setText(formats["HEX"])
        self.last_rgb_edit.setText(formats["RGB"])
        self.last_hsl_edit.setText(formats["HSL"])

    def refresh_history_list(self) -> None:
        self.history_list.clear()
        for hex_color in self.state.history[:10]:
            try:
                rgb = hex_to_rgb(hex_color)
            except ValueError:
                continue
            formatted = format_color(rgb, self.state.copy_format)
            item = QListWidgetItem(formatted)
            item.setData(Qt.UserRole, hex_color)
            self.history_list.addItem(item)

    def refresh_palette_grid(self) -> None:
        while self.palette_grid.count():
            item = self.palette_grid.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        self._chips.clear()

        cols = 3
        for i, item in enumerate(self.state.palettes):
            name = str(item.get("name", f"Palette {i + 1}"))
            colors = item.get("colors")
            if not isinstance(colors, list) or len(colors) < 1:
                continue

            valid: List[str] = []
            for c in colors[:4]:
                try:
                    valid.append(normalize_hex(str(c)))
                except ValueError:
                    continue
            if len(valid) < 1:
                continue

            chip = ColorChip(name, valid, self.palette_wrap)
            chip.clicked.connect(self._copy_palette_color)
            chip.delete_requested.connect(self._delete_palette_group)
            chip.selected.connect(self._select_palette_group)
            chip.rename_requested.connect(self.rename_palette_group)
            self._chips.append(chip)

            row = i // cols
            col = i % cols
            self.palette_grid.addWidget(chip, row, col)

        self._apply_selected_chip_state()

    def _select_palette_group(self, group_name: str) -> None:
        if group_name in self._selected_palette_names:
            self._selected_palette_names.remove(group_name)
        else:
            self._selected_palette_names.add(group_name)
        self._apply_selected_chip_state()
        self.status_label.setText(f"已选中 {len(self._selected_palette_names)} 个配色卡")

    def _apply_selected_chip_state(self) -> None:
        for chip in self._chips:
            chip.set_selected(chip.name in self._selected_palette_names)

    def _copy_palette_color(self, hex_color: str) -> None:
        rgb = hex_to_rgb(hex_color)
        text = format_color(rgb, self.state.copy_format)
        QGuiApplication.clipboard().setText(text)
        self.status_label.setText(f"已复制 {text}")

    def _delete_palette_group(self, group_name: str) -> None:
        idx_to_delete: Optional[int] = None
        for idx, item in enumerate(self.state.palettes):
            if str(item.get("name", "")) == group_name:
                idx_to_delete = idx
                break

        if idx_to_delete is None:
            return

        self.state.palettes.pop(idx_to_delete)
        self._selected_palette_names.discard(group_name)
        self.refresh_palette_grid()
        self.persist_state()
        self.status_label.setText(f"已删除配色卡 {group_name}")

    def add_current_to_palette(self) -> None:
        if not self.state.last_color:
            self.status_label.setText("请先取色")
            return

        hex_color = normalize_hex(self.state.last_color)
        group = {
            "name": f"Custom {len(self.state.palettes) + 1}",
            "colors": build_harmony_palette(hex_color),
        }
        self.state.palettes.append(group)
        self.refresh_palette_grid()
        self.persist_state()
        self.status_label.setText(f"已添加 4 色搭配（锚点 {hex_color}）")

    def add_single_color_palette(self) -> None:
        if not self.state.last_color:
            self.status_label.setText("请先取色")
            return

        hex_color = normalize_hex(self.state.last_color)
        group = {
            "name": f"Mono {len(self.state.palettes) + 1}",
            "colors": [hex_color],
        }
        self.state.palettes.append(group)
        self.refresh_palette_grid()
        self.persist_state()
        self.status_label.setText(f"已添加单色色卡（{hex_color}）")

    def delete_selected_palette(self) -> None:
        if not self._selected_palette_names:
            self.status_label.setText("请先点击选中配色卡")
            return

        selected = set(self._selected_palette_names)
        self.state.palettes = [
            item for item in self.state.palettes if str(item.get("name", "")) not in selected
        ]
        self._selected_palette_names.clear()
        self.refresh_palette_grid()
        self.persist_state()
        self.status_label.setText(f"已删除 {len(selected)} 个配色卡")

    def merge_selected_mono_palettes(self) -> None:
        if len(self._selected_palette_names) != 4:
            self.status_label.setText("请先选中 4 个单色色卡")
            return

        selected_items = []
        for item in self.state.palettes:
            name = str(item.get("name", ""))
            if name in self._selected_palette_names:
                selected_items.append(item)

        if len(selected_items) != 4:
            self.status_label.setText("选中的色卡数量不正确")
            return

        merged_colors: List[str] = []
        for item in selected_items:
            colors = item.get("colors", [])
            if not isinstance(colors, list) or len(colors) != 1:
                self.status_label.setText("只能合并单色色卡（每卡 1 色）")
                return
            try:
                merged_colors.append(normalize_hex(str(colors[0])))
            except ValueError:
                self.status_label.setText("存在非法颜色，无法合并")
                return

        self.state.palettes = [
            item for item in self.state.palettes if str(item.get("name", "")) not in self._selected_palette_names
        ]
        self.state.palettes.append(
            {
                "name": f"Merged {len(self.state.palettes) + 1}",
                "colors": merged_colors,
            }
        )
        self._selected_palette_names.clear()
        self.refresh_palette_grid()
        self.persist_state()
        self.status_label.setText("已合并 4 个单色色卡")

    def rename_palette_group(self, group_name: str) -> None:
        new_name, ok = QInputDialog.getText(self, "重命名色卡", "请输入新名称：", text=group_name)
        if not ok:
            return
        new_name = new_name.strip()
        if not new_name:
            self.status_label.setText("名称不能为空")
            return

        for item in self.state.palettes:
            if str(item.get("name", "")) == group_name:
                item["name"] = new_name
                break

        if group_name in self._selected_palette_names:
            self._selected_palette_names.remove(group_name)
            self._selected_palette_names.add(new_name)

        self.refresh_palette_grid()
        self.persist_state()
        self.status_label.setText(f"已重命名为 {new_name}")

    def export_palette(self, kind: str) -> None:
        if not self.state.palettes:
            self.status_label.setText("配色卡为空，无法导出")
            return

        now = datetime.now().strftime("%Y%m%d_%H%M%S")
        if kind == "txt":
            filename, _ = QFileDialog.getSaveFileName(
                self,
                "导出配色卡 TXT",
                f"palette_{now}.txt",
                "Text Files (*.txt)",
            )
            if not filename:
                return

            lines: List[str] = []
            for item in self.state.palettes:
                name = str(item.get("name", "Palette"))
                colors = item.get("colors", [])
                if isinstance(colors, list):
                    lines.append(f"{name}: {' / '.join(str(c) for c in colors[:4])}")

            Path(filename).write_text("\n".join(lines), encoding="utf-8")
        else:
            filename, _ = QFileDialog.getSaveFileName(
                self,
                "导出配色卡 JSON",
                f"palette_{now}.json",
                "JSON Files (*.json)",
            )
            if not filename:
                return
            data = {"palettes": self.state.palettes}
            Path(filename).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

        self.status_label.setText(f"导出成功：{filename}")

    def copy_from_history(self, item: QListWidgetItem) -> None:
        hex_color = item.data(Qt.UserRole)
        if not hex_color:
            return
        rgb = hex_to_rgb(hex_color)
        text = format_color(rgb, self.state.copy_format)
        QGuiApplication.clipboard().setText(text)
        self.status_label.setText(f"已复制历史颜色 {text}")

    def persist_state(self) -> None:
        self.store.save(self.state)

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.restore_main_window()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._force_exit:
            self.hotkey.unregister()
            self.overlay.hide()
            self.persist_state()
            event.accept()
            return

        event.ignore()
        self.hide()
        self.tray.showMessage("极简取色工具", "程序已最小化到系统托盘")

    def exit_app(self) -> None:
        self._force_exit = True
        self.close()
