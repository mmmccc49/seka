from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


APP_NAME = "ColorMark Studio"
EXE_NAME = "ColorMarkStudio.exe"


def resource_dir() -> Path:
    if hasattr(sys, "_MEIPASS"):
        return Path(getattr(sys, "_MEIPASS"))
    return Path(__file__).resolve().parent


def install_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    if not base:
        base = str(Path.home() / "AppData" / "Local")
    return Path(base) / "Programs" / APP_NAME


def create_shortcut(path: Path, target: Path, description: str) -> None:
    import win32com.client  # type: ignore

    shell = win32com.client.Dispatch("WScript.Shell")
    shortcut = shell.CreateShortcut(str(path))
    shortcut.TargetPath = str(target)
    shortcut.WorkingDirectory = str(target.parent)
    shortcut.Description = description
    shortcut.Save()


def install_app(create_desktop: bool, create_start_menu: bool) -> Path:
    source = resource_dir() / EXE_NAME
    if not source.exists():
        raise FileNotFoundError(f"Missing bundled application: {source}")

    target_dir = install_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    target_exe = target_dir / EXE_NAME
    shutil.copy2(source, target_exe)

    if create_desktop:
        desktop = Path(os.environ.get("USERPROFILE", str(Path.home()))) / "Desktop"
        create_shortcut(desktop / f"{APP_NAME}.lnk", target_exe, "Desktop color picker and palette tool")

    if create_start_menu:
        programs = Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
        create_shortcut(programs / f"{APP_NAME}.lnk", target_exe, "Desktop color picker and palette tool")

    return target_exe


class InstallerWindow(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} Setup")
        self.setFixedSize(420, 260)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(14)

        title = QLabel(APP_NAME, self)
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title.setFont(title_font)

        desc = QLabel(
            "将安装桌面取色与配色卡工具到当前用户目录，并创建快捷方式。",
            self,
        )
        desc.setWordWrap(True)

        path_label = QLabel(f"安装位置：{install_dir()}", self)
        path_label.setWordWrap(True)
        path_label.setStyleSheet("color: #666;")

        self.desktop_check = QCheckBox("创建桌面快捷方式", self)
        self.desktop_check.setChecked(True)
        self.start_menu_check = QCheckBox("创建开始菜单快捷方式", self)
        self.start_menu_check.setChecked(True)

        install_btn = QPushButton("安装", self)
        install_btn.setMinimumHeight(36)
        install_btn.clicked.connect(self.install)

        layout.addWidget(title)
        layout.addWidget(desc)
        layout.addWidget(path_label)
        layout.addStretch(1)
        layout.addWidget(self.desktop_check)
        layout.addWidget(self.start_menu_check)
        layout.addWidget(install_btn)

    def install(self) -> None:
        try:
            target = install_app(self.desktop_check.isChecked(), self.start_menu_check.isChecked())
        except Exception as exc:
            QMessageBox.critical(self, "安装失败", str(exc))
            return

        QMessageBox.information(self, "安装完成", f"{APP_NAME} 已安装到：\n{target}")
        self.close()


def main() -> int:
    app = QApplication(sys.argv)
    app.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    window = InstallerWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
