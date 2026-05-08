"""Visual theme definitions."""

from __future__ import annotations


def build_stylesheet(theme: str) -> str:
    dark = theme == "dark"

    if dark:
        bg = "#0E1014"
        panel = "#151821"
        panel_alt = "#1B1F2A"
        border = "#2A2F3B"
        text = "#F2F4F7"
        subtext = "#A3ACBA"
        input_bg = "#11141C"
        accent = "#F5C47A"
        accent_alt = "#E8A85B"
        item_hover = "rgba(245, 196, 122, 0.18)"
    else:
        bg = "#F6F3EE"
        panel = "#FFFCF8"
        panel_alt = "#F3EEE7"
        border = "#E5DED4"
        text = "#2C2823"
        subtext = "#7A736A"
        input_bg = "#FFFDF9"
        accent = "#B58143"
        accent_alt = "#A66A2E"
        item_hover = "rgba(166, 106, 46, 0.14)"

    return f"""
    QWidget {{
        background-color: {bg};
        color: {text};
        font-family: "Segoe UI", "PingFang SC", "Microsoft YaHei";
        font-size: 13px;
    }}
    QFrame#card {{
        background-color: {panel};
        border: 1px solid {border};
        border-radius: 18px;
    }}
    QFrame#paletteChip {{
        background-color: {panel_alt};
        border: 1px solid {border};
        border-radius: 14px;
    }}
    QLabel#title {{
        font-size: 23px;
        font-weight: 620;
        color: {text};
    }}
    QLabel#subtitle {{
        font-size: 12px;
        color: {subtext};
    }}
    QLabel#chipName {{
        font-size: 12px;
        font-weight: 600;
        color: {text};
    }}
    QLabel#chipCode {{
        font-size: 10px;
        color: {subtext};
    }}
    QFrame#quadPreview {{
        border: 1px solid {border};
        border-radius: 10px;
        background: transparent;
    }}
    QPushButton {{
        background-color: {panel};
        border: 1px solid {border};
        border-radius: 11px;
        padding: 8px 12px;
    }}
    QPushButton:hover {{
        border-color: {accent};
        background-color: {panel_alt};
    }}
    QPushButton#pickButton {{
        background-color: {accent_alt};
        color: #FFFFFF;
        border: 0;
        font-size: 28px;
        font-weight: 700;
        letter-spacing: 1px;
        border-radius: 20px;
        padding: 16px;
        min-height: 88px;
    }}
    QPushButton#pickButton:hover {{
        background-color: {accent};
    }}
    QLineEdit, QComboBox, QListWidget {{
        background-color: {input_bg};
        border: 1px solid {border};
        border-radius: 11px;
        padding: 7px;
    }}
    QListWidget::item {{
        padding: 7px;
        border-radius: 8px;
    }}
    QListWidget::item:selected {{
        background-color: {item_hover};
    }}
    QListWidget::item:hover {{
        background-color: {item_hover};
    }}
    QScrollArea {{
        background: transparent;
        border: 0;
    }}
    QScrollBar:vertical {{
        width: 9px;
        background: transparent;
    }}
    QScrollBar::handle:vertical {{
        background: rgba(120, 126, 138, 0.55);
        border-radius: 4px;
    }}
    """
