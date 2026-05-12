"""Image upload and dominant-color analysis UI."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QGuiApplication, QImage, QImageReader, QPainter, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .color_utils import normalize_hex, rgb_to_hex


COMMON_IMAGE_EXTENSIONS = {
    ".bmp",
    ".gif",
    ".heic",
    ".heif",
    ".jpeg",
    ".jpg",
    ".png",
    ".tif",
    ".tiff",
    ".webp",
}


def _qt_supported_suffixes() -> set[str]:
    suffixes: set[str] = set()
    for fmt in QImageReader.supportedImageFormats():
        try:
            suffixes.add(f".{bytes(fmt).decode('ascii').lower()}")
        except UnicodeDecodeError:
            continue
    if ".jpeg" in suffixes:
        suffixes.add(".jpg")
    if ".jpg" in suffixes:
        suffixes.add(".jpeg")
    return suffixes | COMMON_IMAGE_EXTENSIONS


SUPPORTED_IMAGE_SUFFIXES = _qt_supported_suffixes()


def is_supported_image_path(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in SUPPORTED_IMAGE_SUFFIXES


def image_file_filter() -> str:
    preferred = [
        ".png",
        ".jpg",
        ".jpeg",
        ".webp",
        ".bmp",
        ".gif",
        ".tif",
        ".tiff",
        ".heic",
        ".heif",
    ]
    ordered = [suffix for suffix in preferred if suffix in SUPPORTED_IMAGE_SUFFIXES]
    extras = sorted(SUPPORTED_IMAGE_SUFFIXES - set(ordered))
    patterns = " ".join(f"*{suffix}" for suffix in ordered + extras)
    return f"图片文件 ({patterns});;所有文件 (*.*)"


def find_supported_images(directory: Path, limit: int = 300) -> List[Path]:
    found: List[Path] = []
    try:
        for path in directory.rglob("*"):
            if is_supported_image_path(path):
                found.append(path)
                if len(found) >= limit:
                    break
    except OSError:
        return []
    return sorted(found, key=lambda p: str(p).lower())


def load_qimage(path: Path) -> QImage:
    reader = QImageReader(str(path))
    reader.setAutoTransform(True)
    image = reader.read()
    if image.isNull():
        raise ValueError(reader.errorString() or "无法读取图片")
    return image


def _color_distance_sq(a: Tuple[float, float, float], b: Tuple[float, float, float]) -> float:
    dr = a[0] - b[0]
    dg = a[1] - b[1]
    db = a[2] - b[2]
    return (0.30 * dr * dr) + (0.59 * dg * dg) + (0.11 * db * db)


def _quantized_bins(image: QImage, max_side: int = 180) -> List[Tuple[float, float, float, int]]:
    if image.isNull():
        return []

    working = image.convertToFormat(QImage.Format_ARGB32)
    if max(working.width(), working.height()) > max_side:
        working = working.scaled(max_side, max_side, Qt.KeepAspectRatio, Qt.FastTransformation)

    area = max(1, working.width() * working.height())
    step = max(1, round(math.sqrt(area / 18000)))
    bins: Dict[Tuple[int, int, int], List[int]] = {}

    for y in range(0, working.height(), step):
        for x in range(0, working.width(), step):
            color = working.pixelColor(x, y)
            if color.alpha() < 32:
                continue
            r, g, b = color.red(), color.green(), color.blue()
            key = (r // 18, g // 18, b // 18)
            bucket = bins.setdefault(key, [0, 0, 0, 0])
            bucket[0] += r
            bucket[1] += g
            bucket[2] += b
            bucket[3] += 1

    points: List[Tuple[float, float, float, int]] = []
    for total_r, total_g, total_b, weight in bins.values():
        if weight > 0:
            points.append((total_r / weight, total_g / weight, total_b / weight, weight))
    return points


def _seed_centers(points: List[Tuple[float, float, float, int]], count: int) -> List[Tuple[float, float, float]]:
    centers: List[Tuple[float, float, float]] = []
    ranked = sorted(points, key=lambda item: item[3], reverse=True)

    for threshold in (74, 58, 42, 28, 0):
        for r, g, b, _weight in ranked:
            candidate = (r, g, b)
            if candidate in centers:
                continue
            if all(_color_distance_sq(candidate, center) ** 0.5 >= threshold for center in centers):
                centers.append(candidate)
            if len(centers) >= count:
                return centers
    return centers


def extract_dominant_colors(image: QImage, count: int = 8) -> List[str]:
    """Return up to ``count`` visually distinct dominant colors from a QImage."""

    target_count = max(1, int(count))
    points = _quantized_bins(image)
    if not points:
        return []

    centers = _seed_centers(points, target_count)
    if not centers:
        return []

    weights = [0 for _ in centers]
    for _ in range(8):
        buckets = [[0.0, 0.0, 0.0, 0] for _ in centers]
        for r, g, b, weight in points:
            idx = min(
                range(len(centers)),
                key=lambda i: _color_distance_sq((r, g, b), centers[i]),
            )
            buckets[idx][0] += r * weight
            buckets[idx][1] += g * weight
            buckets[idx][2] += b * weight
            buckets[idx][3] += weight

        next_centers: List[Tuple[float, float, float]] = []
        weights = []
        for idx, bucket in enumerate(buckets):
            weight = bucket[3]
            if weight:
                next_centers.append((bucket[0] / weight, bucket[1] / weight, bucket[2] / weight))
                weights.append(weight)
            else:
                next_centers.append(centers[idx])
                weights.append(0)
        centers = next_centers

    ranked_clusters = []
    for center, weight in zip(centers, weights):
        if weight <= 0:
            continue
        vibrancy = (max(center) - min(center)) / 255.0
        ranked_clusters.append((center, weight * (0.86 + 0.14 * vibrancy)))

    ranked_clusters.sort(key=lambda item: item[1], reverse=True)

    selected: List[Tuple[float, float, float]] = []
    for center, _score in ranked_clusters:
        if all(_color_distance_sq(center, existing) ** 0.5 >= 20 for existing in selected):
            selected.append(center)
        if len(selected) >= target_count:
            break

    if len(selected) < target_count:
        for r, g, b, _weight in sorted(points, key=lambda item: item[3], reverse=True):
            candidate = (r, g, b)
            if all(_color_distance_sq(candidate, existing) ** 0.5 >= 12 for existing in selected):
                selected.append(candidate)
            if len(selected) >= target_count:
                break

    if len(selected) < target_count:
        ranked_points = [(r, g, b) for r, g, b, _weight in sorted(points, key=lambda item: item[3], reverse=True)]
        for candidate in ranked_points:
            selected.append(candidate)
            if len(selected) >= target_count:
                break

    while selected and len(selected) < target_count:
        selected.append(selected[-1])

    return [rgb_to_hex((round(r), round(g), round(b))) for r, g, b in selected[:target_count]]


def _first_acceptable_path_from_urls(urls: Iterable[object]) -> Optional[Path]:
    for url in urls:
        if not url.isLocalFile():
            continue
        path = Path(url.toLocalFile())
        if path.is_dir() or is_supported_image_path(path):
            return path
    return None


class UploadDropFrame(QFrame):
    path_dropped = Signal(str)
    browse_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("uploadDropFrame")
        self.setAcceptDrops(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumSize(520, 300)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(12)
        layout.setAlignment(Qt.AlignCenter)

        mark = QLabel("IMG", self)
        mark.setObjectName("uploadMark")
        mark.setAlignment(Qt.AlignCenter)

        title = QLabel("拖入图片", self)
        title.setObjectName("uploadTitle")
        title.setAlignment(Qt.AlignCenter)

        hint = QLabel("支持常见图片格式，也可以从文件夹中选择", self)
        hint.setObjectName("uploadHint")
        hint.setAlignment(Qt.AlignCenter)

        layout.addStretch(1)
        layout.addWidget(mark, 0, Qt.AlignCenter)
        layout.addWidget(title)
        layout.addWidget(hint)
        layout.addStretch(1)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self.browse_requested.emit()
            event.accept()
            return
        super().mousePressEvent(event)

    def dragEnterEvent(self, event) -> None:
        if _first_acceptable_path_from_urls(event.mimeData().urls()) is not None:
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dropEvent(self, event) -> None:
        path = _first_acceptable_path_from_urls(event.mimeData().urls())
        if path is None:
            super().dropEvent(event)
            return
        self.path_dropped.emit(str(path))
        event.acceptProposedAction()


class DominantColorChip(QFrame):
    toggled = Signal(str, bool)

    def __init__(self, color: str, parent=None) -> None:
        super().__init__(parent)
        self.color = normalize_hex(color)
        self._selected = False
        self._dot_size = 48
        self.setObjectName("dominantColorChip")
        self.setFixedSize(70, 86)
        self.setCursor(Qt.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(3, 3, 3, 3)
        layout.setSpacing(5)
        layout.setAlignment(Qt.AlignCenter)

        self.dot = QLabel(self)
        self.dot.setObjectName("dominantColorDot")
        self.dot.setFixedSize(self._dot_size, self._dot_size)

        self.code = QLabel(self.color, self)
        self.code.setObjectName("dominantColorCode")
        self.code.setAlignment(Qt.AlignCenter)

        layout.addWidget(self.dot, 0, Qt.AlignCenter)
        layout.addWidget(self.code)
        self._sync_style()

    def is_selected(self) -> bool:
        return self._selected

    def set_selected(self, selected: bool) -> None:
        self._selected = bool(selected)
        self._sync_style()

    def _sync_style(self) -> None:
        ring = "#FAFFFFFF" if self._selected else "#38FFFFFF"
        width = 4 if self._selected else 1
        self.dot.setStyleSheet(
            f"""
            QLabel#dominantColorDot {{
                background-color: {self.color};
                border-radius: {self._dot_size // 2}px;
                border: {width}px solid {ring};
            }}
            """
        )

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self.set_selected(not self._selected)
            self.toggled.emit(self.color, self._selected)
            event.accept()
            return
        super().mousePressEvent(event)


class PhotoStage(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._pixmap = QPixmap()
        self.setAutoFillBackground(False)

    def set_pixmap(self, pixmap: QPixmap) -> None:
        self._pixmap = pixmap
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        painter.fillRect(self.rect(), QColor("#DDE3E7"))

        if not self._pixmap.isNull():
            scaled = self._pixmap.scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            x = (self.width() - scaled.width()) // 2
            y = (self.height() - scaled.height()) // 2
            painter.drawPixmap(x, y, scaled)
            painter.fillRect(self.rect(), QColor(12, 18, 24, 18))

        super().paintEvent(event)


class PhotoAnalysisPage(PhotoStage):
    generate_requested = Signal(list)
    change_requested = Signal()
    back_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._colors: List[str] = []
        self._chips: List[DominantColorChip] = []

        self.top_bar = QWidget(self)
        top_layout = QHBoxLayout(self.top_bar)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(10)

        self.back_btn = QPushButton("返回", self.top_bar)
        self.back_btn.setObjectName("floatingGlassButton")
        self.back_btn.clicked.connect(self.back_requested.emit)

        title_box = QWidget(self.top_bar)
        title_layout = QVBoxLayout(title_box)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(0)
        self.title_label = QLabel("图片主色分析", title_box)
        self.title_label.setObjectName("floatingTitle")
        self.path_label = QLabel("", title_box)
        self.path_label.setObjectName("floatingHint")
        title_layout.addWidget(self.title_label)
        title_layout.addWidget(self.path_label)

        self.change_btn = QPushButton("换图", self.top_bar)
        self.change_btn.setObjectName("floatingGlassButton")
        self.change_btn.clicked.connect(self.change_requested.emit)

        top_layout.addWidget(self.back_btn)
        top_layout.addWidget(title_box)
        top_layout.addStretch(1)
        top_layout.addWidget(self.change_btn)

        self.panel = QFrame(self)
        self.panel.setObjectName("analysisGlassPanel")
        panel_shadow = QGraphicsDropShadowEffect(self.panel)
        panel_shadow.setBlurRadius(38)
        panel_shadow.setOffset(0, 18)
        panel_shadow.setColor(QColor(0, 0, 0, 90))
        self.panel.setGraphicsEffect(panel_shadow)

        panel_layout = QVBoxLayout(self.panel)
        panel_layout.setContentsMargins(18, 12, 18, 12)
        panel_layout.setSpacing(10)

        self.colors_row = QHBoxLayout()
        self.colors_row.setSpacing(6)
        self.colors_row.setAlignment(Qt.AlignCenter)

        action_row = QHBoxLayout()
        action_row.setSpacing(8)
        self.status_label = QLabel("选择 1 到 4 种颜色生成色卡", self.panel)
        self.status_label.setObjectName("glassStatus")
        self.select_first_btn = QPushButton("选择前 4 色", self.panel)
        self.select_first_btn.setObjectName("analysisSmallButton")
        self.clear_btn = QPushButton("清空选择", self.panel)
        self.clear_btn.setObjectName("analysisSmallButton")
        self.generate_btn = QPushButton("生成色卡", self.panel)
        self.generate_btn.setObjectName("analysisPrimaryButton")
        for btn in [self.select_first_btn, self.clear_btn, self.generate_btn]:
            btn.setFixedHeight(32)

        self.select_first_btn.clicked.connect(self._select_first_four)
        self.clear_btn.clicked.connect(self._clear_selection)
        self.generate_btn.clicked.connect(self._emit_generate)

        action_row.addWidget(self.status_label)
        action_row.addStretch(1)
        action_row.addWidget(self.select_first_btn)
        action_row.addWidget(self.clear_btn)
        action_row.addWidget(self.generate_btn)

        panel_layout.addLayout(self.colors_row)
        panel_layout.addSpacing(8)
        panel_layout.addLayout(action_row)

    def resizeEvent(self, event) -> None:
        margin = 26
        self.top_bar.setGeometry(margin, margin, max(320, self.width() - margin * 2), 56)
        panel_width = min(max(620, self.width() - margin * 2), 860)
        panel_height = 140
        self.panel.setGeometry(
            (self.width() - panel_width) // 2,
            max(margin + 76, self.height() - panel_height - margin),
            panel_width,
            panel_height,
        )
        super().resizeEvent(event)

    def set_photo(self, pixmap: QPixmap, filename: str, colors: List[str]) -> None:
        self.set_pixmap(pixmap)
        self.path_label.setText(filename)
        self._colors = [normalize_hex(color) for color in colors]
        self._rebuild_chips()

    def _rebuild_chips(self) -> None:
        while self.colors_row.count():
            item = self.colors_row.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        self._chips.clear()
        for idx, color in enumerate(self._colors):
            chip = DominantColorChip(color, self.panel)
            chip.set_selected(idx < 4)
            chip.toggled.connect(lambda color_value, selected, ref=chip: self._handle_chip_toggle(ref, color_value, selected))
            self._chips.append(chip)
            self.colors_row.addWidget(chip)

        self._sync_status()

    def _selected_colors(self) -> List[str]:
        return [chip.color for chip in self._chips if chip.is_selected()]

    def _handle_chip_toggle(self, chip: DominantColorChip, _color: str, selected: bool) -> None:
        if selected and len(self._selected_colors()) > 4:
            chip.set_selected(False)
            self.status_label.setText("最多选择 4 种颜色")
            return
        self._sync_status()

    def _sync_status(self) -> None:
        count = len(self._selected_colors())
        if count == 0:
            self.status_label.setText("选择 1 到 4 种颜色生成色卡")
        else:
            self.status_label.setText(f"已选择 {count} 种颜色")

    def _select_first_four(self) -> None:
        for idx, chip in enumerate(self._chips):
            chip.set_selected(idx < 4)
        self._sync_status()

    def _clear_selection(self) -> None:
        for chip in self._chips:
            chip.set_selected(False)
        self._sync_status()

    def _emit_generate(self) -> None:
        selected = self._selected_colors()
        if not selected:
            self.status_label.setText("请先选择颜色")
            return
        self.generate_requested.emit(selected)

    def mark_generated(self) -> None:
        self.status_label.setText("已加入左侧配色卡")


class ImagePaletteDialog(QDialog):
    palette_created = Signal(list)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("上传图片分析主色")
        self.resize(960, 720)
        self.setMinimumSize(700, 540)
        self.setAcceptDrops(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.stack = QStackedWidget(self)
        layout.addWidget(self.stack)

        self.upload_page = self._build_upload_page()
        self.analysis_page = PhotoAnalysisPage(self)
        self.analysis_page.back_requested.connect(self._show_upload_page)
        self.analysis_page.change_requested.connect(self.choose_image)
        self.analysis_page.generate_requested.connect(self._create_palette)

        self.stack.addWidget(self.upload_page)
        self.stack.addWidget(self.analysis_page)
        self.setStyleSheet(ANALYZER_STYLESHEET)

    def _resize_for_photo(self, image: QImage) -> None:
        if image.isNull():
            return

        screen = self.screen() or QGuiApplication.primaryScreen()
        available = screen.availableGeometry() if screen is not None else None
        max_w = int((available.width() if available else 1280) * 0.86)
        max_h = int((available.height() if available else 900) * 0.86)
        min_w, min_h = 700, 540

        ratio = image.width() / max(1, image.height())
        chrome_h = 0

        if ratio >= 1:
            target_w = min(max_w, max(min_w, int(max_h * ratio)))
            target_h = int(target_w / ratio) + chrome_h
            if target_h > max_h:
                target_h = max_h
                target_w = int((target_h - chrome_h) * ratio)
        else:
            target_h = min(max_h, max(min_h, int(max_w / ratio)))
            target_w = int((target_h - chrome_h) * ratio)
            if target_w > max_w:
                target_w = max_w
                target_h = int(target_w / ratio) + chrome_h

        if ratio >= 0.9:
            min_w = 820

        target_w = max(min_w, min(max_w, target_w))
        target_h = max(min_h, min(max_h, target_h))
        self.resize(target_w, target_h)

    def _build_upload_page(self) -> QWidget:
        page = QWidget(self)
        page.setObjectName("imageAnalyzerRoot")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(42, 38, 42, 38)
        layout.setSpacing(22)

        top = QHBoxLayout()
        heading_box = QWidget(page)
        heading_layout = QVBoxLayout(heading_box)
        heading_layout.setContentsMargins(0, 0, 0, 0)
        heading_layout.setSpacing(2)
        title = QLabel("上传图片", heading_box)
        title.setObjectName("analyzerTitle")
        subtitle = QLabel("拖入图片或从文件夹中选择，自动提取照片中的 8 种主要颜色", heading_box)
        subtitle.setObjectName("analyzerSubtitle")
        heading_layout.addWidget(title)
        heading_layout.addWidget(subtitle)

        close_btn = QPushButton("关闭", page)
        close_btn.setObjectName("floatingGlassButton")
        close_btn.clicked.connect(self.reject)

        top.addWidget(heading_box)
        top.addStretch(1)
        top.addWidget(close_btn)

        drop_frame = UploadDropFrame(page)
        drop_frame.path_dropped.connect(self.load_path)
        drop_frame.browse_requested.connect(self.choose_image)
        drop_shadow = QGraphicsDropShadowEffect(drop_frame)
        drop_shadow.setBlurRadius(36)
        drop_shadow.setOffset(0, 22)
        drop_shadow.setColor(QColor(32, 43, 55, 42))
        drop_frame.setGraphicsEffect(drop_shadow)

        action_row = QHBoxLayout()
        action_row.setSpacing(12)
        choose_file = QPushButton("选择图片", page)
        choose_file.setObjectName("primaryGlassButton")
        choose_file.clicked.connect(self.choose_image)
        choose_folder = QPushButton("选择文件夹", page)
        choose_folder.setObjectName("smallGlassButton")
        choose_folder.clicked.connect(self.choose_folder)
        action_row.addStretch(1)
        action_row.addWidget(choose_file)
        action_row.addWidget(choose_folder)
        action_row.addStretch(1)

        layout.addLayout(top)
        layout.addStretch(1)
        layout.addWidget(drop_frame, 0, Qt.AlignCenter)
        layout.addLayout(action_row)
        layout.addStretch(1)
        return page

    def choose_image(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(self, "选择图片", str(Path.home()), image_file_filter())
        if filename:
            self.load_path(filename)

    def choose_folder(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "选择图片所在文件夹", str(Path.home()))
        if directory:
            self.load_path(directory)

    def load_path(self, raw_path: str) -> None:
        path = Path(raw_path)
        if path.is_dir():
            path = self._choose_image_from_directory(path)
            if path is None:
                return

        if not path.exists():
            QMessageBox.warning(self, "图片不存在", "请选择有效的图片文件")
            return

        try:
            image = load_qimage(path)
        except ValueError as exc:
            QMessageBox.warning(self, "无法读取图片", str(exc))
            return

        colors = extract_dominant_colors(image, 8)
        if not colors:
            QMessageBox.warning(self, "未提取到颜色", "这张图片没有可分析的有效像素")
            return

        self._resize_for_photo(image)
        self.analysis_page.set_photo(QPixmap.fromImage(image), path.name, colors)
        self.stack.setCurrentWidget(self.analysis_page)

    def _choose_image_from_directory(self, directory: Path) -> Optional[Path]:
        images = find_supported_images(directory)
        if not images:
            QMessageBox.warning(self, "未找到图片", "这个文件夹里没有可识别的图片")
            return None
        if len(images) == 1:
            return images[0]

        labels = [str(path.relative_to(directory)) for path in images]
        choice, ok = QInputDialog.getItem(self, "选择图片", "文件夹内图片：", labels, 0, False)
        if not ok:
            return None
        return images[labels.index(choice)]

    def _show_upload_page(self) -> None:
        self.stack.setCurrentWidget(self.upload_page)

    def _create_palette(self, colors: List[str]) -> None:
        clean = []
        for color in colors[:4]:
            try:
                clean.append(normalize_hex(str(color)))
            except ValueError:
                continue
        if not clean:
            return
        self.palette_created.emit(clean)
        self.analysis_page.mark_generated()

    def dragEnterEvent(self, event) -> None:
        if _first_acceptable_path_from_urls(event.mimeData().urls()) is not None:
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dropEvent(self, event) -> None:
        path = _first_acceptable_path_from_urls(event.mimeData().urls())
        if path is None:
            super().dropEvent(event)
            return
        self.load_path(str(path))
        event.acceptProposedAction()


ANALYZER_STYLESHEET = """
QWidget#imageAnalyzerRoot {
    background-color: #EEF2F5;
    color: #131820;
}
QLabel {
    background: transparent;
}
QLabel#analyzerTitle {
    font-size: 30px;
    font-weight: 650;
    color: #131820;
}
QLabel#analyzerSubtitle,
QLabel#uploadHint,
QLabel#floatingHint,
QLabel#glassStatus {
    color: #9E1F2937;
}
QLabel#uploadTitle {
    font-size: 24px;
    font-weight: 650;
    color: #17202A;
}
QLabel#uploadMark {
    min-width: 76px;
    min-height: 76px;
    border-radius: 38px;
    background-color: #94FFFFFF;
    color: #B8182029;
    border: 1px solid #D1FFFFFF;
    font-size: 17px;
    font-weight: 700;
}
QFrame#uploadDropFrame {
    background-color: #8AFFFFFF;
    border: 1px solid #E6FFFFFF;
    border-radius: 32px;
}
QFrame#uploadDropFrame:hover {
    background-color: #A8FFFFFF;
    border: 1px solid #942391E0;
}
QFrame#analysisGlassPanel {
    background-color: #6BEEF6FA;
    border: 1px solid #BDFFFFFF;
    border-radius: 44px;
}
QFrame#dominantColorChip {
    background: transparent;
    border: 0;
}
QLabel#dominantColorCode {
    color: #E6FFFFFF;
    font-size: 11px;
    font-weight: 650;
}
QLabel#floatingTitle {
    color: #F5FFFFFF;
    font-size: 17px;
    font-weight: 650;
}
QLabel#floatingHint {
    color: #C2FFFFFF;
}
QPushButton {
    font-size: 14px;
    font-weight: 620;
    border-radius: 18px;
    padding: 9px 16px;
}
QPushButton#floatingGlassButton,
QPushButton#smallGlassButton,
QPushButton#analysisSmallButton {
    background-color: #75FFFFFF;
    border: 1px solid #B8FFFFFF;
    color: #151B23;
}
QPushButton#floatingGlassButton:hover,
QPushButton#smallGlassButton:hover,
QPushButton#analysisSmallButton:hover {
    background-color: #A8FFFFFF;
}
QPushButton#analysisSmallButton {
    border-radius: 16px;
    padding: 4px 14px;
    font-size: 13px;
}
QPushButton#primaryGlassButton,
QPushButton#analysisPrimaryButton {
    background-color: #E61C8BE0;
    border: 1px solid #80FFFFFF;
    color: #FFFFFF;
}
QPushButton#analysisPrimaryButton {
    border-radius: 16px;
    padding: 4px 16px;
    font-size: 13px;
}
QPushButton#primaryGlassButton:hover,
QPushButton#analysisPrimaryButton:hover {
    background-color: #F50E80D6;
}
"""
