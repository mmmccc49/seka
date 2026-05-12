"""Main window for the desktop color picker app."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QColor, QCloseEvent, QGuiApplication, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
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
    QVBoxLayout,
    QWidget,
    QInputDialog,
)

from .color_utils import all_formats, build_harmony_palette, format_color, hex_to_rgb, normalize_hex, rgb_to_hex
from .exporters import export_ase, export_css_variables, export_figma_tokens, export_tailwind
from .hotkey import GlobalHotkeyManager
from .image_analyzer import ImagePaletteDialog
from .picker_overlay import PickerOverlay
from .storage import AppState, StateStore, new_palette_id
from .theme import build_stylesheet
from .widgets.color_chip import ColorChip
from .widgets.motion import MotionButton, pulse


class SettingsDialog(QDialog):
    def __init__(self, parent, theme: str, hotkey_enabled: bool, hotkey_shortcut: str) -> None:
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setModal(True)
        self.resize(420, 220)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        theme_row = QHBoxLayout()
        theme_row.addWidget(QLabel("主题", self))
        self.theme_combo = QComboBox(self)
        self.theme_combo.addItems(["月白", "暗黑"])
        self.theme_combo.setCurrentIndex(0 if theme == "moonlight" else 1)
        theme_row.addWidget(self.theme_combo)

        self.hotkey_check = QCheckBox("启用全局快捷键", self)
        self.hotkey_check.setChecked(hotkey_enabled)

        hotkey_row = QHBoxLayout()
        hotkey_row.addWidget(QLabel("快捷键", self))
        self.hotkey_edit = QLineEdit(self)
        self.hotkey_edit.setPlaceholderText("例如 Ctrl+Shift+C / Ctrl+Alt+Q / Alt+F2")
        self.hotkey_edit.setText(hotkey_shortcut)
        hotkey_row.addWidget(self.hotkey_edit)

        hint = QLabel("支持：Ctrl / Shift / Alt + 字母数字或 F1~F24", self)
        hint.setObjectName("subtitle")

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        ok_btn = QPushButton("保存", self)
        cancel_btn = QPushButton("取消", self)
        ok_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(ok_btn)
        btn_row.addWidget(cancel_btn)

        layout.addLayout(theme_row)
        layout.addWidget(self.hotkey_check)
        layout.addLayout(hotkey_row)
        layout.addWidget(hint)
        layout.addStretch(1)
        layout.addLayout(btn_row)

    @property
    def selected_theme(self) -> str:
        return "moonlight" if self.theme_combo.currentIndex() == 0 else "dark"

    @property
    def hotkey_enabled(self) -> bool:
        return self.hotkey_check.isChecked()

    @property
    def hotkey_shortcut(self) -> str:
        return self.hotkey_edit.text().strip()


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("极简取色工具")
        self.setWindowIcon(self._create_app_icon())
        self.resize(1160, 700)
        self.setMinimumSize(1060, 640)

        self.store = StateStore()
        self.state: AppState = self.store.load()

        self._is_picking = False
        self._force_exit = False
        self._chips: List[ColorChip] = []
        self._selected_palette_ids: set[str] = set()
        self._last_pick_batch: List[str] = []
        self._pick_mode = "single"
        self._palette_layout_key: tuple[int, int, int] = (0, 0, 0)
        self._palette_resize_timer = QTimer(self)
        self._palette_resize_timer.setSingleShot(True)
        self._palette_resize_timer.timeout.connect(self._refresh_palette_grid_for_resize)

        self.overlay = PickerOverlay(self.get_copy_format)
        self.overlay.picked.connect(self._on_colors_picked)
        self.overlay.canceled.connect(self._on_pick_canceled)

        self._build_ui()
        self._init_tray()
        self._init_hotkey()

        self.apply_theme(self.state.theme)
        self.refresh_all_views()

    def _build_ui(self) -> None:
        root = QWidget(self)
        root.setObjectName("appRoot")
        self.setCentralWidget(root)

        outer = QHBoxLayout(root)
        outer.setContentsMargins(18, 18, 18, 18)
        outer.setSpacing(14)

        self.sidebar = QFrame(self)
        self.sidebar.setObjectName("sidebar")
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(12, 14, 12, 14)
        sidebar_layout.setSpacing(12)

        logo = QLabel(self.sidebar)
        logo.setObjectName("logoBadge")
        logo.setPixmap(self._create_app_icon().pixmap(42, 42))
        logo.setAlignment(Qt.AlignCenter)
        sidebar_layout.addWidget(logo, 0, Qt.AlignCenter)
        sidebar_layout.addSpacing(10)

        nav_items = [
            ("●", "首页"),
            ("◆", "色卡"),
            ("▲", "分析"),
            ("⚙", "设置"),
        ]
        self.nav_buttons: List[QPushButton] = []
        for idx, (icon, label) in enumerate(nav_items):
            btn = MotionButton(f"{icon}\n{label}", self.sidebar)
            btn.setObjectName("navButtonActive" if idx == 0 else "navButton")
            btn.setCursor(Qt.PointingHandCursor)
            if label == "设置":
                btn.clicked.connect(self.open_settings)
            elif label == "分析":
                btn.clicked.connect(self.open_image_palette_analyzer)
            else:
                btn.clicked.connect(lambda checked=False, b=btn: self._pulse_widget(b))
            self.nav_buttons.append(btn)
            sidebar_layout.addWidget(btn)

        sidebar_layout.addStretch(1)
        self.theme_pill = MotionButton("Light", self.sidebar)
        self.theme_pill.setObjectName("themePill")
        self.theme_pill.clicked.connect(self._toggle_theme)
        sidebar_layout.addWidget(self.theme_pill)

        self.palette_card = QFrame(self)
        self.palette_card.setObjectName("card")
        palette_layout = QVBoxLayout(self.palette_card)
        palette_layout.setContentsMargins(22, 22, 22, 22)
        palette_layout.setSpacing(14)

        top_title_row = QHBoxLayout()
        palette_title = QLabel("高级配色卡", self.palette_card)
        palette_title.setObjectName("title")
        self.settings_btn = MotionButton("设置", self.palette_card)
        self.settings_btn.clicked.connect(self.open_settings)
        top_title_row.addWidget(palette_title)
        top_title_row.addStretch(1)
        top_title_row.addWidget(self.settings_btn)

        palette_sub = QLabel("点击色卡可选中；右键删除/重命名/复制；支持单色/4色/图片主色", self.palette_card)
        palette_sub.setObjectName("subtitle")

        self.palette_search = QLineEdit(self.palette_card)
        self.palette_search.setPlaceholderText("搜索色卡名称或颜色")
        self.palette_search.textChanged.connect(self.refresh_palette_grid)

        hero_card = QFrame(self.palette_card)
        hero_card.setObjectName("heroPanel")
        hero_layout = QHBoxLayout(hero_card)
        hero_layout.setContentsMargins(22, 20, 22, 20)
        hero_layout.setSpacing(16)

        hero_text = QVBoxLayout()
        welcome = QLabel("Welcome back", hero_card)
        welcome.setObjectName("eyebrow")
        hero_title = QLabel("ColorMark Studio", hero_card)
        hero_title.setObjectName("heroTitle")
        hero_hint = QLabel("取色、图片主色分析和设计色卡都在一个轻量工作台里。", hero_card)
        hero_hint.setObjectName("heroHint")
        hero_text.addWidget(welcome)
        hero_text.addWidget(hero_title)
        hero_text.addWidget(hero_hint)
        hero_layout.addLayout(hero_text, 1)

        stats_row = QHBoxLayout()
        self.palette_count_badge = self._metric_badge("色卡", "0", "metricWarm", hero_card)
        self.history_count_badge = self._metric_badge("历史", "0", "metricMint", hero_card)
        self.last_color_badge = self._metric_badge("最后", "-", "metricBlue", hero_card)
        stats_row.addWidget(self.palette_count_badge)
        stats_row.addWidget(self.history_count_badge)
        stats_row.addWidget(self.last_color_badge)
        hero_layout.addLayout(stats_row)

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
        self.gen_from_last_btn = MotionButton("按最后取色生成色卡", self.palette_card)
        self.gen_from_last_btn.clicked.connect(self.generate_card_from_last)
        self.gen_harmony_btn = MotionButton("生成搭配色卡", self.palette_card)
        self.gen_harmony_btn.clicked.connect(self.generate_harmony_from_last)
        self.merge_selected_btn = MotionButton("合并选中色卡", self.palette_card)
        self.merge_selected_btn.clicked.connect(self.merge_selected_palettes)
        self.duplicate_selected_btn = MotionButton("复制选中色卡", self.palette_card)
        self.duplicate_selected_btn.clicked.connect(self.duplicate_selected_palette)
        self.delete_selected_btn = MotionButton("删除选定配色卡", self.palette_card)
        self.delete_selected_btn.clicked.connect(self.delete_selected_palette)
        palette_ops_row1.addWidget(self.gen_from_last_btn)
        palette_ops_row1.addWidget(self.gen_harmony_btn)
        palette_ops_row1.addWidget(self.merge_selected_btn)
        palette_ops_row1.addWidget(self.duplicate_selected_btn)
        palette_ops_row1.addWidget(self.delete_selected_btn)

        palette_ops_row2 = QHBoxLayout()
        self.export_txt_btn = MotionButton("TXT", self.palette_card)
        self.export_json_btn = MotionButton("JSON", self.palette_card)
        self.export_css_btn = MotionButton("CSS", self.palette_card)
        self.export_tailwind_btn = MotionButton("Tailwind", self.palette_card)
        self.export_figma_btn = MotionButton("Figma", self.palette_card)
        self.export_ase_btn = MotionButton("ASE", self.palette_card)

        self.export_txt_btn.clicked.connect(lambda: self.export_palette("txt"))
        self.export_json_btn.clicked.connect(lambda: self.export_palette("json"))
        self.export_css_btn.clicked.connect(lambda: self.export_palette("css"))
        self.export_tailwind_btn.clicked.connect(lambda: self.export_palette("tailwind"))
        self.export_figma_btn.clicked.connect(lambda: self.export_palette("figma"))
        self.export_ase_btn.clicked.connect(lambda: self.export_palette("ase"))

        for btn in [
            self.export_txt_btn,
            self.export_json_btn,
            self.export_css_btn,
            self.export_tailwind_btn,
            self.export_figma_btn,
            self.export_ase_btn,
        ]:
            palette_ops_row2.addWidget(btn)

        palette_layout.addLayout(top_title_row)
        palette_layout.addWidget(palette_sub)
        palette_layout.addWidget(self.palette_search)
        palette_layout.addWidget(hero_card)
        palette_layout.addWidget(self.palette_scroll, 1)
        palette_layout.addLayout(palette_ops_row1)
        palette_layout.addLayout(palette_ops_row2)

        self.control_card = QFrame(self)
        self.control_card.setObjectName("sidePanel")
        control_layout = QVBoxLayout(self.control_card)
        control_layout.setContentsMargins(18, 18, 18, 18)
        control_layout.setSpacing(13)

        title = QLabel("Quick Actions", self.control_card)
        title.setObjectName("title")
        subtitle = QLabel("三个入口覆盖屏幕取色、连续取色和图片主色分析。", self.control_card)
        subtitle.setObjectName("subtitle")

        control_layout.addWidget(title)
        control_layout.addWidget(subtitle)

        pick_zone = QWidget(self.control_card)
        pick_zone.setFixedHeight(240)
        pick_zone_layout = QVBoxLayout(pick_zone)
        pick_zone_layout.setContentsMargins(0, 0, 0, 0)
        pick_zone_layout.setSpacing(12)

        self.pick_single_btn = MotionButton("单色取色\nSingle Pick", pick_zone)
        self.pick_single_btn.setObjectName("pickButtonPrimary")
        self.pick_single_btn.setFixedHeight(72)
        self.pick_single_btn.clicked.connect(self.start_single_pick_mode)

        self.pick_multi_btn = MotionButton("连续取色\n最多4色", pick_zone)
        self.pick_multi_btn.setObjectName("pickButtonLilac")
        self.pick_multi_btn.setFixedHeight(72)
        self.pick_multi_btn.clicked.connect(self.start_multi_pick_mode)

        self.image_analyzer_btn = MotionButton("上传图片\n分析主色", pick_zone)
        self.image_analyzer_btn.setObjectName("pickButtonMint")
        self.image_analyzer_btn.setFixedHeight(72)
        self.image_analyzer_btn.clicked.connect(self.open_image_palette_analyzer)

        pick_zone_layout.addWidget(self.pick_single_btn)
        pick_zone_layout.addWidget(self.pick_multi_btn)
        pick_zone_layout.addWidget(self.image_analyzer_btn)
        control_layout.addWidget(pick_zone)
        control_layout.addSpacing(10)

        option_panel = QFrame(self.control_card)
        option_panel.setObjectName("softPanel")
        option_panel.setFixedHeight(158)
        option_layout = QVBoxLayout(option_panel)
        option_layout.setContentsMargins(14, 10, 14, 10)
        option_layout.setSpacing(4)

        options_row = QHBoxLayout()
        self.format_combo = QComboBox(self.control_card)
        self.format_combo.addItems(["HEX", "RGB", "HSL"])
        self.format_combo.setCurrentText(self.state.copy_format)
        self.format_combo.currentTextChanged.connect(self._on_format_changed)

        options_row.addWidget(QLabel("复制格式", self.control_card))
        options_row.addWidget(self.format_combo)
        option_layout.addLayout(options_row)

        self.last_hex_edit = self._readonly_line("-")
        self.last_rgb_edit = self._readonly_line("-")
        self.last_hsl_edit = self._readonly_line("-")

        for label_text, edit in [
            ("HEX", self.last_hex_edit),
            ("RGB", self.last_rgb_edit),
            ("HSL", self.last_hsl_edit),
        ]:
            row = QHBoxLayout()
            row.setSpacing(8)
            label = QLabel(label_text, self.control_card)
            label.setObjectName("fieldLabel")
            label.setFixedWidth(38)
            row.addWidget(label)
            row.addWidget(edit, 1)
            option_layout.addLayout(row)

        control_layout.addWidget(option_panel)

        history_title = QLabel("历史记录（最近 10 次）", self.control_card)
        history_title.setObjectName("subtitle")
        self.history_list = QListWidget(self.control_card)
        self.history_list.itemClicked.connect(self.copy_from_history)
        control_layout.addWidget(history_title)
        control_layout.addWidget(self.history_list, 1)

        self.status_label = QLabel("就绪", self.control_card)
        self.status_label.setObjectName("statusPill")
        self.status_label.setWordWrap(True)
        control_layout.addWidget(self.status_label)

        outer.addWidget(self.sidebar)
        outer.addWidget(self.palette_card, 68)
        outer.addWidget(self.control_card, 32)

    def _metric_badge(self, title: str, value: str, object_name: str, parent) -> QFrame:
        frame = QFrame(parent)
        frame.setObjectName(object_name)
        frame.setMinimumWidth(94)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(1)
        value_label = QLabel(value, frame)
        value_label.setObjectName("metricValue")
        title_label = QLabel(title, frame)
        title_label.setObjectName("metricTitle")
        layout.addWidget(value_label)
        layout.addWidget(title_label)
        frame.value_label = value_label
        return frame

    def _readonly_line(self, text: str) -> QLineEdit:
        edit = QLineEdit(text, self)
        edit.setReadOnly(True)
        edit.setMinimumHeight(28)
        edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        return edit

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if hasattr(self, "palette_scroll"):
            self._palette_resize_timer.start(80)

    def _refresh_palette_grid_for_resize(self) -> None:
        metrics = self._palette_grid_metrics()
        if metrics != self._palette_layout_key:
            self.refresh_palette_grid()

    def _palette_grid_metrics(self) -> tuple[int, int, int]:
        if not hasattr(self, "palette_scroll"):
            return 3, 228, 148

        available = self.palette_scroll.viewport().width()
        if available <= 0:
            available = self.palette_scroll.width()
        available = max(420, available - 4)

        if available < 660:
            cols = 2
        elif available >= 1320:
            cols = 4
        else:
            cols = 3

        spacing = max(14, min(28, available // 48))
        card_width = (available - spacing * (cols - 1)) // cols
        card_width = max(220, min(365, card_width))
        card_height = max(148, min(228, int(card_width * 0.60)))
        return cols, card_width, card_height

    def _init_tray(self) -> None:
        self.tray = QSystemTrayIcon(self)
        self.tray.setIcon(self._create_app_icon())
        self.tray.setToolTip("极简取色工具")

        menu = QMenu(self)
        show_action = QAction("显示主窗口", self)
        pick_action = QAction("屏幕取色", self)
        exit_action = QAction("退出程序", self)

        show_action.triggered.connect(self.restore_main_window)
        pick_action.triggered.connect(self.start_single_pick_mode)
        exit_action.triggered.connect(self.exit_app)

        menu.addAction(show_action)
        menu.addAction(pick_action)
        menu.addSeparator()
        menu.addAction(exit_action)

        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()

    def _init_hotkey(self) -> None:
        self.hotkey = GlobalHotkeyManager(QGuiApplication.instance(), shortcut=self.state.hotkey_shortcut)
        self.hotkey.activated.connect(self.start_single_pick_mode)
        if self.state.hotkey_enabled and self.hotkey.register():
            self.status_label.setText(f"全局快捷键已启用：{self.hotkey.shortcut_text}")
        elif self.state.hotkey_enabled:
            self.status_label.setText("快捷键注册失败，仍可用按钮取色")
        else:
            self.status_label.setText("全局快捷键已禁用")

    def _sync_hotkey(self) -> bool:
        self.hotkey.unregister()
        if not self.state.hotkey_enabled:
            return True

        if not self.hotkey.set_shortcut(self.state.hotkey_shortcut):
            return False
        return self.hotkey.register()

    def _create_app_icon(self) -> QIcon:
        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#1D2027"))
        painter.drawEllipse(4, 4, 56, 56)
        painter.setPen(QPen(QColor("#FFFFFF"), 4))
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(23, 23, 18, 18)
        painter.end()
        return QIcon(pixmap)

    def apply_theme(self, theme: str) -> None:
        normalized = "dark" if theme == "dark" else "moonlight"
        self.state.theme = normalized
        self.setStyleSheet(build_stylesheet(normalized))
        if hasattr(self, "theme_pill"):
            self.theme_pill.setText("Dark" if normalized == "dark" else "Light")

    def _toggle_theme(self) -> None:
        self.apply_theme("dark" if self.state.theme != "dark" else "moonlight")
        self.persist_state()
        self._pulse_widget(self.theme_pill)

    def _pulse_widget(self, widget: QWidget) -> None:
        pulse(widget)

    def _flash_status(self) -> None:
        if hasattr(self, "status_label"):
            pulse(self.status_label, distance=2, duration=80)

    def open_settings(self) -> None:
        dlg = SettingsDialog(self, self.state.theme, self.state.hotkey_enabled, self.state.hotkey_shortcut)
        if dlg.exec() != QDialog.Accepted:
            return

        candidate_shortcut = dlg.hotkey_shortcut or self.state.hotkey_shortcut
        if dlg.hotkey_enabled and GlobalHotkeyManager.parse_shortcut(candidate_shortcut) is None:
            QMessageBox.warning(self, "快捷键无效", "快捷键格式无效，请使用例如 Ctrl+Shift+C")
            return

        self.apply_theme(dlg.selected_theme)
        self.state.hotkey_enabled = dlg.hotkey_enabled
        self.state.hotkey_shortcut = candidate_shortcut

        if not self._sync_hotkey():
            QMessageBox.warning(self, "快捷键不可用", "快捷键注册失败，可能与系统或其他程序冲突。")
            self.status_label.setText("快捷键注册失败，请更换组合键")
            return

        self.persist_state()
        if self.state.hotkey_enabled:
            self.status_label.setText(f"设置已保存，快捷键：{self.hotkey.shortcut_text}")
        else:
            self.status_label.setText("设置已保存，快捷键已禁用")

    def _on_format_changed(self, text: str) -> None:
        self.state.copy_format = text.upper()
        self.refresh_history_list()
        self.persist_state()

    def get_copy_format(self) -> str:
        return self.state.copy_format

    def start_single_pick_mode(self) -> None:
        self._start_pick_mode("single")

    def start_multi_pick_mode(self) -> None:
        self._start_pick_mode("multi")

    def open_image_palette_analyzer(self) -> None:
        dlg = ImagePaletteDialog(self)
        dlg.palette_created.connect(self.add_palette_from_image_colors)
        dlg.exec()

    def add_palette_from_image_colors(self, colors: List[str]) -> None:
        clean: List[str] = []
        for color in colors[:4]:
            try:
                clean.append(normalize_hex(str(color)))
            except ValueError:
                continue

        if not clean:
            self.status_label.setText("图片颜色不可用")
            return

        self._last_pick_batch = list(clean)
        self.state.last_color = clean[0]
        for hx in reversed(clean):
            self.state.history.insert(0, hx)
        self.state.history = self.state.history[:10]

        palette_colors = list(clean)
        if len(palette_colors) > 1:
            while len(palette_colors) < 4:
                palette_colors.append(palette_colors[-1])

        self.state.palettes.append(
            {
                "id": new_palette_id(),
                "name": f"Image {len(self.state.palettes) + 1}",
                "colors": palette_colors[:4],
            }
        )
        self.refresh_all_views()
        self.persist_state()
        self.status_label.setText(f"已从图片生成配色卡：{' / '.join(palette_colors[:4])}")
        self._flash_status()

    def _start_pick_mode(self, mode: str) -> None:
        if self._is_picking:
            return
        self._is_picking = True
        self._pick_mode = mode
        self._last_pick_batch = []
        self.hide()
        self.overlay.start(1 if mode == "single" else 4)

    def _on_pick_canceled(self) -> None:
        self._is_picking = False
        self.restore_main_window()
        self.status_label.setText("已取消取色")

    def _on_colors_picked(self, rgbs: List[tuple]) -> None:
        self._is_picking = False
        if not rgbs:
            self.restore_main_window()
            return

        hexes = [rgb_to_hex(rgb) for rgb in rgbs]
        self._last_pick_batch = hexes

        final_rgb = rgbs[-1]
        final_hex = hexes[-1]

        self.state.last_color = final_hex
        for hx in reversed(hexes):
            self.state.history.insert(0, hx)
        self.state.history = self.state.history[:10]

        copy_text = format_color(final_rgb, self.state.copy_format)
        QGuiApplication.clipboard().setText(copy_text)

        self._highlight_if_exists(final_hex)
        self.refresh_all_views()
        self.persist_state()
        self.restore_main_window()

        if self._pick_mode == "multi":
            self.status_label.setText(f"连续取色完成 {len(hexes)} 个，已复制 {copy_text}")
        else:
            self.status_label.setText(f"已复制 {copy_text}")
        self._flash_status()

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
        self.refresh_dashboard_metrics()

    def refresh_dashboard_metrics(self) -> None:
        if hasattr(self, "palette_count_badge"):
            self.palette_count_badge.value_label.setText(str(len(self.state.palettes)))
            self.history_count_badge.value_label.setText(str(len(self.state.history[:10])))
            self.last_color_badge.value_label.setText(self.state.last_color or "-")

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

    def _ensure_palette_id(self, item: dict) -> str:
        palette_id = str(item.get("id", "")).strip()
        if not palette_id:
            palette_id = new_palette_id()
            item["id"] = palette_id
        return palette_id

    def _palette_matches_filter(self, name: str, colors: List[str]) -> bool:
        if not hasattr(self, "palette_search"):
            return True
        query = self.palette_search.text().strip().lower()
        if not query:
            return True
        haystack = " ".join([name, *colors]).lower()
        return query in haystack

    def refresh_palette_grid(self) -> None:
        cols, card_width, card_height = self._palette_grid_metrics()
        spacing = max(14, min(28, self.palette_scroll.viewport().width() // 48))
        self._palette_layout_key = (cols, card_width, card_height)
        self.palette_grid.setHorizontalSpacing(spacing)
        self.palette_grid.setVerticalSpacing(max(14, spacing - 2))
        self.palette_grid.setAlignment(Qt.AlignTop | Qt.AlignLeft)

        while self.palette_grid.count():
            item = self.palette_grid.takeAt(0)
            widget = item.widget()
            if widget:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()

        self._chips.clear()

        visible_index = 0
        for i, item in enumerate(self.state.palettes):
            name = str(item.get("name", f"Palette {i + 1}"))
            palette_id = self._ensure_palette_id(item)
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
            if not self._palette_matches_filter(name, valid):
                continue

            chip = ColorChip(palette_id, name, valid, self.palette_wrap)
            chip.set_card_size(card_width, card_height)
            chip.clicked.connect(self._copy_palette_color)
            chip.copy_color_requested.connect(self._copy_palette_color)
            chip.copy_palette_requested.connect(self._copy_palette_group_text)
            chip.delete_requested.connect(self._delete_palette_group)
            chip.selected.connect(self._select_palette_group)
            chip.rename_requested.connect(self.rename_palette_group)
            self._chips.append(chip)

            row = visible_index // cols
            col = visible_index % cols
            self.palette_grid.addWidget(chip, row, col, Qt.AlignTop | Qt.AlignLeft)
            visible_index += 1

        rows = max(1, (visible_index + cols - 1) // cols)
        v_spacing = self.palette_grid.verticalSpacing()
        h_spacing = self.palette_grid.horizontalSpacing()
        self.palette_wrap.setMinimumSize(
            cols * card_width + max(0, cols - 1) * h_spacing,
            rows * card_height + max(0, rows - 1) * v_spacing,
        )

        self._apply_selected_chip_state()

    def _select_palette_group(self, palette_id: str) -> None:
        if palette_id in self._selected_palette_ids:
            self._selected_palette_ids.remove(palette_id)
        else:
            self._selected_palette_ids.add(palette_id)
        self._apply_selected_chip_state()
        self.status_label.setText(f"已选中 {len(self._selected_palette_ids)} 个配色卡")

    def _apply_selected_chip_state(self) -> None:
        for chip in self._chips:
            chip.set_selected(chip.palette_id in self._selected_palette_ids)

    def _copy_palette_color(self, hex_color: str) -> None:
        rgb = hex_to_rgb(hex_color)
        text = format_color(rgb, self.state.copy_format)
        QGuiApplication.clipboard().setText(text)
        self.status_label.setText(f"已复制 {text}")
        self._flash_status()

    def _copy_palette_group_text(self, colors: list, mode: str) -> None:
        formatted: List[str] = []
        for color in colors[:4]:
            try:
                rgb = hex_to_rgb(str(color))
            except ValueError:
                continue
            formatted.append(format_color(rgb, self.state.copy_format))

        if not formatted:
            self.status_label.setText("色卡颜色不可用，无法复制")
            return

        if mode == "rows":
            output = "\n".join(formatted)
            self.status_label.setText(f"已复制整张 {len(formatted)} 色卡（多行）")
        elif mode == "line":
            output = " / ".join(formatted)
            self.status_label.setText(f"已复制整张 {len(formatted)} 色卡（一行）")
        else:
            output = json.dumps(
                {
                    "format": self.state.copy_format,
                    "colors": formatted,
                },
                ensure_ascii=False,
                indent=2,
            )
            self.status_label.setText(f"已复制整张 {len(formatted)} 色卡（JSON）")

        QGuiApplication.clipboard().setText(output)
        self._flash_status()

    def _delete_palette_group(self, palette_id: str) -> None:
        idx_to_delete: Optional[int] = None
        for idx, item in enumerate(self.state.palettes):
            if self._ensure_palette_id(item) == palette_id:
                idx_to_delete = idx
                break

        if idx_to_delete is None:
            return

        name = str(self.state.palettes[idx_to_delete].get("name", "Palette"))
        self.state.palettes.pop(idx_to_delete)
        self._selected_palette_ids.discard(palette_id)
        self.refresh_palette_grid()
        self.persist_state()
        self.status_label.setText(f"已删除配色卡 {name}")
        self._flash_status()

    def _make_group_from_hexes(self, hexes: List[str]) -> None:
        clean: List[str] = []
        for hx in hexes:
            try:
                clean.append(normalize_hex(hx))
            except ValueError:
                continue

        if not clean:
            self.status_label.setText("没有可用颜色")
            return

        if len(clean) == 1:
            group = {
                "id": new_palette_id(),
                "name": f"Mono {len(self.state.palettes) + 1}",
                "colors": [clean[0]],
            }
            self.state.palettes.append(group)
            self.status_label.setText(f"已添加单色色卡（{clean[0]}）")
        else:
            colors = clean[:4]
            while len(colors) < 4:
                colors.append(colors[-1])
            group = {
                "id": new_palette_id(),
                "name": f"Custom {len(self.state.palettes) + 1}",
                "colors": colors,
            }
            self.state.palettes.append(group)
            self.status_label.setText(f"已生成 {len(colors)} 色卡")

        self.refresh_palette_grid()
        self.persist_state()
        self.refresh_dashboard_metrics()
        self._flash_status()

    def generate_card_from_last(self) -> None:
        if self._last_pick_batch:
            self._make_group_from_hexes(self._last_pick_batch)
            return
        if self.state.last_color:
            self._make_group_from_hexes([normalize_hex(self.state.last_color)])
            return
        self.status_label.setText("请先取色")

    def generate_harmony_from_last(self) -> None:
        if not self.state.last_color:
            self.status_label.setText("请先取一个基准色")
            return

        anchor = normalize_hex(self.state.last_color)
        colors = build_harmony_palette(anchor)
        self.state.palettes.append(
            {
                "id": new_palette_id(),
                "name": f"Harmony {len(self.state.palettes) + 1}",
                "colors": colors[:4],
            }
        )
        self._last_pick_batch = colors[:4]
        self.refresh_all_views()
        self.persist_state()
        self.status_label.setText(f"已根据 {anchor} 生成搭配色卡")
        self._flash_status()

    def delete_selected_palette(self) -> None:
        if not self._selected_palette_ids:
            self.status_label.setText("请先点击选中配色卡")
            return

        selected = set(self._selected_palette_ids)
        self.state.palettes = [
            item for item in self.state.palettes if self._ensure_palette_id(item) not in selected
        ]
        self._selected_palette_ids.clear()
        self.refresh_palette_grid()
        self.persist_state()
        self.status_label.setText(f"已删除 {len(selected)} 个配色卡")
        self._flash_status()

    def duplicate_selected_palette(self) -> None:
        selected_items = [
            item for item in self.state.palettes if self._ensure_palette_id(item) in self._selected_palette_ids
        ]
        if not selected_items:
            self.status_label.setText("请先点击选中配色卡")
            return

        for item in selected_items:
            colors = item.get("colors", [])
            if not isinstance(colors, list):
                continue
            self.state.palettes.append(
                {
                    "id": new_palette_id(),
                    "name": f"{str(item.get('name', 'Palette'))} Copy",
                    "colors": list(colors[:4]),
                }
            )

        self._selected_palette_ids.clear()
        self.refresh_all_views()
        self.persist_state()
        self.status_label.setText(f"已复制 {len(selected_items)} 个配色卡")
        self._flash_status()

    def merge_selected_palettes(self) -> None:
        selected_items = []
        for item in self.state.palettes:
            if self._ensure_palette_id(item) in self._selected_palette_ids:
                selected_items.append(item)

        if len(selected_items) < 2:
            self.status_label.setText("请至少选中 2 张色卡")
            return

        merged_colors: List[str] = []
        for item in selected_items:
            colors = item.get("colors", [])
            if not isinstance(colors, list) or len(colors) < 1:
                self.status_label.setText("选中色卡中存在空色卡，无法合并")
                return
            for color in colors[:4]:
                try:
                    merged_colors.append(normalize_hex(str(color)))
                except ValueError:
                    self.status_label.setText("存在非法颜色，无法合并")
                    return

        if len(merged_colors) < 2:
            self.status_label.setText("至少需要 2 个颜色才能合并")
            return
        if len(merged_colors) > 4:
            self.status_label.setText("合并后最多只能包含 4 个颜色")
            return

        self.state.palettes = [
            item for item in self.state.palettes if self._ensure_palette_id(item) not in self._selected_palette_ids
        ]
        self.state.palettes.append(
            {
                "id": new_palette_id(),
                "name": f"Merged {len(self.state.palettes) + 1}",
                "colors": merged_colors[:4],
            }
        )
        self._selected_palette_ids.clear()
        self.refresh_palette_grid()
        self.persist_state()
        self.status_label.setText(f"已合并为 {len(merged_colors)} 色卡")
        self._flash_status()

    def rename_palette_group(self, palette_id: str) -> None:
        group_name = "Palette"
        for item in self.state.palettes:
            if self._ensure_palette_id(item) == palette_id:
                group_name = str(item.get("name", "Palette"))
                break

        new_name, ok = QInputDialog.getText(self, "重命名色卡", "请输入新名称：", text=group_name)
        if not ok:
            return
        new_name = new_name.strip()
        if not new_name:
            self.status_label.setText("名称不能为空")
            return

        for item in self.state.palettes:
            if self._ensure_palette_id(item) == palette_id:
                item["name"] = new_name
                break

        self.refresh_palette_grid()
        self.persist_state()
        self.status_label.setText(f"已重命名为 {new_name}")
        self._flash_status()

    def export_palette(self, kind: str) -> None:
        if not self.state.palettes:
            self.status_label.setText("配色卡为空，无法导出")
            return

        now = datetime.now().strftime("%Y%m%d_%H%M%S")

        if kind == "txt":
            filename, _ = QFileDialog.getSaveFileName(self, "导出配色卡 TXT", f"palette_{now}.txt", "Text Files (*.txt)")
            if not filename:
                return
            lines: List[str] = []
            for item in self.state.palettes:
                name = str(item.get("name", "Palette"))
                colors = item.get("colors", [])
                if isinstance(colors, list):
                    lines.append(f"{name}: {' / '.join(str(c) for c in colors[:4])}")
            Path(filename).write_text("\n".join(lines), encoding="utf-8")

        elif kind == "json":
            filename, _ = QFileDialog.getSaveFileName(self, "导出配色卡 JSON", f"palette_{now}.json", "JSON Files (*.json)")
            if not filename:
                return
            data = {"palettes": self.state.palettes}
            Path(filename).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

        elif kind == "css":
            filename, _ = QFileDialog.getSaveFileName(self, "导出 CSS Variables", f"palette_{now}.css", "CSS Files (*.css)")
            if not filename:
                return
            export_css_variables(self.state.palettes, Path(filename))

        elif kind == "tailwind":
            filename, _ = QFileDialog.getSaveFileName(self, "导出 Tailwind", f"tailwind.palette_{now}.js", "JS Files (*.js)")
            if not filename:
                return
            export_tailwind(self.state.palettes, Path(filename))

        elif kind == "figma":
            filename, _ = QFileDialog.getSaveFileName(self, "导出 Figma Tokens", f"figma.tokens_{now}.json", "JSON Files (*.json)")
            if not filename:
                return
            export_figma_tokens(self.state.palettes, Path(filename))

        elif kind == "ase":
            filename, _ = QFileDialog.getSaveFileName(self, "导出 ASE", f"palette_{now}.ase", "ASE Files (*.ase)")
            if not filename:
                return
            export_ase(self.state.palettes, Path(filename))

        else:
            self.status_label.setText("不支持的导出类型")
            return

        self.status_label.setText(f"导出成功：{filename}")
        self._flash_status()

    def copy_from_history(self, item: QListWidgetItem) -> None:
        hex_color = item.data(Qt.UserRole)
        if not hex_color:
            return
        rgb = hex_to_rgb(hex_color)
        text = format_color(rgb, self.state.copy_format)
        QGuiApplication.clipboard().setText(text)
        self.status_label.setText(f"已复制历史颜色 {text}")
        self._flash_status()

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

        msg = QMessageBox(self)
        msg.setWindowTitle("关闭确认")
        msg.setText("请选择关闭方式")
        btn_min = msg.addButton("最小化到托盘", QMessageBox.AcceptRole)
        btn_exit = msg.addButton("退出程序", QMessageBox.DestructiveRole)
        btn_cancel = msg.addButton("取消", QMessageBox.RejectRole)
        msg.exec()

        clicked = msg.clickedButton()
        if clicked == btn_min:
            event.ignore()
            self.hide()
            self.tray.showMessage("极简取色工具", "程序已最小化到托盘")
            return

        if clicked == btn_exit:
            self._force_exit = True
            event.accept()
            self.hotkey.unregister()
            self.overlay.hide()
            self.persist_state()
            return

        if clicked == btn_cancel:
            event.ignore()
            return

        event.ignore()

    def exit_app(self) -> None:
        self._force_exit = True
        self.close()
