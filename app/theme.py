"""Visual theme definitions."""

from __future__ import annotations


def build_stylesheet(theme: str) -> str:
    dark = theme == "dark"

    if dark:
        bg = "#111216"
        panel = "#20222B"
        panel_alt = "#292B36"
        canvas = "#181B23"
        soft_panel = "#252833"
        border = "#3B3E4A"
        text = "#F8F7F2"
        subtext = "#A7ABB8"
        input_bg = "#191B22"
        nav_bg = "#1A1C24"
        active = "#D9FF51"
        active_text = "#141414"
        hero_a = "#7D75FF"
        hero_b = "#F46D8D"
        mint = "#8AF0C6"
        lilac = "#B7B2FF"
        warm = "#FFD35C"
        blue = "#76C9FF"
        danger = "#FF7B8D"
        shadow = "#000000"
        item_hover = "#2D3340"
    else:
        bg = "#F5F4EC"
        panel = "#FFFDF7"
        panel_alt = "#F0F1E6"
        canvas = "#F4F4EF"
        soft_panel = "#F8F7EF"
        border = "#E7E0D2"
        text = "#17181B"
        subtext = "#74736C"
        input_bg = "#FFFFFF"
        nav_bg = "#FDFBF4"
        active = "#151515"
        active_text = "#FFFFFF"
        hero_a = "#8B7CFF"
        hero_b = "#F06685"
        mint = "#BDF7CD"
        lilac = "#C8C4FF"
        warm = "#FFE26F"
        blue = "#BFE2FF"
        danger = "#F87684"
        shadow = "#C9C1B5"
        item_hover = "#EFEFE6"

    return f"""
    QWidget#appRoot {{
        background-color: {bg};
        color: {text};
        font-size: 13px;
    }}
    QWidget {{
        color: {text};
        font-size: 13px;
    }}
    QLabel {{
        background: transparent;
    }}
    QFrame#sidebar {{
        background-color: {nav_bg};
        border: 1px solid {border};
        border-radius: 26px;
        min-width: 78px;
        max-width: 86px;
    }}
    QLabel#logoBadge {{
        min-width: 46px;
        min-height: 46px;
        border-radius: 23px;
        background-color: transparent;
    }}
    QPushButton#navButton,
    QPushButton#navButtonActive,
    QPushButton#themePill {{
        border: 0;
        border-radius: 18px;
        padding: 10px 4px;
        min-height: 48px;
        font-size: 11px;
        font-weight: 650;
    }}
    QPushButton#navButton {{
        background-color: transparent;
        color: {subtext};
    }}
    QPushButton#navButton:hover {{
        background-color: {panel_alt};
        color: {text};
    }}
    QPushButton#navButtonActive {{
        background-color: {active};
        color: {active_text};
    }}
    QPushButton#themePill {{
        background-color: {panel_alt};
        color: {text};
        min-height: 36px;
    }}
    QFrame#card,
    QFrame#sidePanel {{
        background-color: {panel};
        border: 1px solid {border};
        border-radius: 28px;
    }}
    QFrame#softPanel {{
        background-color: {soft_panel};
        border: 1px solid {border};
        border-radius: 24px;
    }}
    QFrame#heroPanel {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {hero_a}, stop:1 {hero_b});
        border: 0;
        border-radius: 28px;
    }}
    QLabel#eyebrow {{
        color: #FFFFFF;
        font-size: 12px;
        font-weight: 700;
    }}
    QLabel#heroTitle {{
        color: #FFFFFF;
        font-size: 30px;
        font-weight: 820;
    }}
    QLabel#heroHint {{
        color: #F4F1FF;
        font-size: 13px;
        font-weight: 520;
    }}
    QFrame#metricWarm,
    QFrame#metricMint,
    QFrame#metricBlue {{
        border: 0;
        border-radius: 22px;
    }}
    QFrame#metricWarm {{
        background-color: {warm};
    }}
    QFrame#metricMint {{
        background-color: {mint};
    }}
    QFrame#metricBlue {{
        background-color: {blue};
    }}
    QLabel#metricValue {{
        color: #17181B;
        font-size: 21px;
        font-weight: 850;
    }}
    QLabel#metricTitle {{
        color: #454545;
        font-size: 11px;
        font-weight: 650;
    }}
    QFrame#paletteChip {{
        background-color: {panel_alt};
        border: 1px solid {border};
        border-radius: 24px;
    }}
    QFrame#paletteChip:hover {{
        border-color: {active};
        background-color: {soft_panel};
    }}
    QLabel#title {{
        font-size: 25px;
        font-weight: 780;
        color: {text};
    }}
    QLabel#subtitle {{
        font-size: 12px;
        color: {subtext};
    }}
    QLabel#fieldLabel {{
        font-size: 12px;
        font-weight: 750;
        color: {subtext};
    }}
    QLabel#statusPill {{
        background-color: {soft_panel};
        border: 1px solid {border};
        border-radius: 18px;
        padding: 10px 12px;
        font-size: 12px;
        color: {subtext};
    }}
    QLabel#chipName {{
        font-size: 12px;
        font-weight: 750;
        color: {text};
    }}
    QLabel#chipCode {{
        font-size: 10px;
        color: {subtext};
    }}
    QFrame#quadPreview {{
        border: 0;
        border-radius: 18px;
        background: transparent;
    }}
    QPushButton {{
        background-color: {soft_panel};
        border: 1px solid {border};
        border-radius: 16px;
        padding: 8px 12px;
        color: {text};
        font-weight: 650;
    }}
    QPushButton:hover {{
        background-color: {panel_alt};
        border-color: {active};
    }}
    QPushButton#pickButtonPrimary,
    QPushButton#pickButtonLilac,
    QPushButton#pickButtonMint {{
        border: 0;
        border-radius: 28px;
        color: #17181B;
        font-size: 17px;
        font-weight: 850;
        text-align: left;
        min-height: 48px;
        max-height: 48px;
        padding: 12px 18px;
    }}
    QPushButton#pickButtonPrimary {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {warm}, stop:1 #FF9E67);
    }}
    QPushButton#pickButtonLilac {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {lilac}, stop:1 {blue});
    }}
    QPushButton#pickButtonMint {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {mint}, stop:1 #E8FF7D);
    }}
    QPushButton#pickButtonPrimary:hover,
    QPushButton#pickButtonLilac:hover,
    QPushButton#pickButtonMint:hover {{
        border: 2px solid #FFFFFF;
    }}
    QLineEdit,
    QComboBox,
    QListWidget {{
        background-color: {input_bg};
        border: 1px solid {border};
        border-radius: 16px;
        padding: 8px;
        color: {text};
    }}
    QComboBox {{
        min-height: 28px;
        padding: 7px 34px 7px 12px;
    }}
    QComboBox::drop-down {{
        border: 0;
        width: 30px;
        border-top-right-radius: 16px;
        border-bottom-right-radius: 16px;
        background-color: {panel_alt};
    }}
    QComboBox::down-arrow {{
        image: none;
        width: 0;
        height: 0;
        border-left: 5px solid transparent;
        border-right: 5px solid transparent;
        border-top: 6px solid {subtext};
        margin-right: 10px;
    }}
    QComboBox QAbstractItemView {{
        background-color: {panel};
        color: {text};
        border: 1px solid {border};
        border-radius: 14px;
        padding: 6px;
        selection-background-color: {item_hover};
        outline: 0;
    }}
    QListWidget {{
        outline: 0;
    }}
    QListWidget::item {{
        padding: 9px;
        border-radius: 12px;
    }}
    QListWidget::item:selected {{
        background-color: {active};
        color: {active_text};
    }}
    QListWidget::item:hover {{
        background-color: {item_hover};
    }}
    QScrollArea {{
        background-color: {canvas};
        border: 0;
        border-radius: 0;
    }}
    QScrollArea > QWidget > QWidget {{
        background-color: {canvas};
    }}
    QScrollBar:vertical {{
        width: 9px;
        background: transparent;
    }}
    QScrollBar::handle:vertical {{
        background: {border};
        border-radius: 4px;
    }}
    QMenu {{
        background-color: {panel};
        border: 1px solid {border};
        border-radius: 14px;
        padding: 6px;
    }}
    QMenu::item {{
        padding: 7px 22px;
        border-radius: 8px;
    }}
    QMenu::item:selected {{
        background-color: {item_hover};
    }}
    """
