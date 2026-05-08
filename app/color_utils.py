"""Color conversion helpers for the picker app."""

from __future__ import annotations

import colorsys
from typing import Dict, List, Tuple

RGB = Tuple[int, int, int]


DEFAULT_PRESET_PALETTES = [
    {"name": "Nord Stone", "colors": ["#1E293B", "#334155", "#64748B", "#E2E8F0"]},
    {"name": "Moss Paper", "colors": ["#2F3E2F", "#4F6D56", "#A3B18A", "#ECEAD7"]},
    {"name": "Ink Sand", "colors": ["#111318", "#3B3F46", "#B8A892", "#F4EFE7"]},
    {"name": "Ocean Fog", "colors": ["#0F172A", "#1E3A5F", "#5A7CA8", "#DDE7F2"]},
    {"name": "Wine Clay", "colors": ["#3A1F2D", "#7A3E48", "#C08C7A", "#F2E6DC"]},
    {"name": "Forest Mist", "colors": ["#1F2A24", "#355B4C", "#8FB3A2", "#E6EFEA"]},
    {"name": "Graphite Gold", "colors": ["#1A1A1D", "#4A4E57", "#B89B6E", "#F6F1E8"]},
    {"name": "Midnight Rose", "colors": ["#171A2A", "#3D3A66", "#A182B7", "#F1E9F8"]},
    {"name": "Cream Cobalt", "colors": ["#1F2A44", "#325D9B", "#7AA5E3", "#F9F6EE"]},
    {"name": "Espresso Linen", "colors": ["#2B2118", "#6C4A2C", "#C7A17A", "#F3ECE2"]},
]


def clamp_rgb(value: int) -> int:
    return max(0, min(255, int(value)))


def normalize_hex(value: str) -> str:
    raw = value.strip().lstrip("#")
    if len(raw) == 3:
        raw = "".join(ch * 2 for ch in raw)
    if len(raw) != 6:
        raise ValueError(f"Invalid hex color: {value}")
    int(raw, 16)
    return f"#{raw.upper()}"


def rgb_to_hex(rgb: RGB) -> str:
    r, g, b = (clamp_rgb(v) for v in rgb)
    return f"#{r:02X}{g:02X}{b:02X}"


def hex_to_rgb(hex_color: str) -> RGB:
    normalized = normalize_hex(hex_color).lstrip("#")
    return int(normalized[0:2], 16), int(normalized[2:4], 16), int(normalized[4:6], 16)


def rgb_to_hsl(rgb: RGB) -> Tuple[int, int, int]:
    r, g, b = (clamp_rgb(v) / 255.0 for v in rgb)
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    return round(h * 360), round(s * 100), round(l * 100)


def hsl_to_rgb(h: int, s: int, l: int) -> RGB:
    hh = (h % 360) / 360.0
    ss = max(0, min(100, s)) / 100.0
    ll = max(0, min(100, l)) / 100.0
    r, g, b = colorsys.hls_to_rgb(hh, ll, ss)
    return round(r * 255), round(g * 255), round(b * 255)


def format_hex(rgb: RGB) -> str:
    return rgb_to_hex(rgb)


def format_rgb(rgb: RGB) -> str:
    r, g, b = (clamp_rgb(v) for v in rgb)
    return f"rgb({r}, {g}, {b})"


def format_hsl(rgb: RGB) -> str:
    h, s, l = rgb_to_hsl(rgb)
    return f"hsl({h}, {s}%, {l}%)"


def format_color(rgb: RGB, format_name: str) -> str:
    key = format_name.strip().upper()
    if key == "HEX":
        return format_hex(rgb)
    if key == "RGB":
        return format_rgb(rgb)
    if key == "HSL":
        return format_hsl(rgb)
    raise ValueError(f"Unsupported format: {format_name}")


def all_formats(rgb: RGB) -> Dict[str, str]:
    return {
        "HEX": format_hex(rgb),
        "RGB": format_rgb(rgb),
        "HSL": format_hsl(rgb),
    }


def build_harmony_palette(anchor_hex: str) -> List[str]:
    """Build a 4-color advanced harmony from an anchor color."""
    base = hex_to_rgb(anchor_hex)
    h, s, l = rgb_to_hsl(base)

    deep = hsl_to_rgb(h, max(18, s - 18), max(10, l - 26))
    primary = hsl_to_rgb(h, max(20, s), max(20, l))
    accent = hsl_to_rgb((h + 32) % 360, min(92, s + 8), min(78, l + 10))
    paper = hsl_to_rgb(h, max(8, s - 34), min(95, l + 34))

    return [rgb_to_hex(deep), rgb_to_hex(primary), rgb_to_hex(accent), rgb_to_hex(paper)]
