"""Export palette data into design-tool formats."""

from __future__ import annotations

import json
import struct
from pathlib import Path
from typing import Dict, List

from .color_utils import hex_to_rgb, normalize_hex


def flatten_palette_hexes(palettes: List[Dict[str, object]]) -> List[str]:
    result: List[str] = []
    for item in palettes:
        colors = item.get("colors", [])
        if not isinstance(colors, list):
            continue
        for c in colors[:4]:
            try:
                result.append(normalize_hex(str(c)))
            except ValueError:
                continue
    return result


def export_css_variables(palettes: List[Dict[str, object]], path: Path) -> None:
    lines = [":root {"]
    idx = 1
    for item in palettes:
        name = str(item.get("name", "palette")).strip().lower().replace(" ", "-")
        colors = item.get("colors", [])
        if not isinstance(colors, list):
            continue
        for j, c in enumerate(colors[:4], start=1):
            try:
                hx = normalize_hex(str(c))
            except ValueError:
                continue
            lines.append(f"  --{name}-{j}-{idx}: {hx};")
            idx += 1
    lines.append("}")
    path.write_text("\n".join(lines), encoding="utf-8")


def export_tailwind(palettes: List[Dict[str, object]], path: Path) -> None:
    obj: Dict[str, Dict[str, str]] = {}
    for i, item in enumerate(palettes, start=1):
        key = str(item.get("name", f"palette-{i}")).strip().lower().replace(" ", "-")
        colors = item.get("colors", [])
        if not isinstance(colors, list):
            continue
        slots: Dict[str, str] = {}
        for j, c in enumerate(colors[:4], start=1):
            try:
                slots[str(j * 100)] = normalize_hex(str(c))
            except ValueError:
                continue
        if slots:
            obj[key] = slots

    content = "module.exports = {\n  theme: {\n    extend: {\n      colors: " + json.dumps(obj, ensure_ascii=False, indent=8) + "\n    }\n  }\n};\n"
    path.write_text(content, encoding="utf-8")


def export_figma_tokens(palettes: List[Dict[str, object]], path: Path) -> None:
    tokens: Dict[str, Dict[str, Dict[str, str]]] = {}
    for i, item in enumerate(palettes, start=1):
        group = str(item.get("name", f"Palette {i}")).strip()
        colors = item.get("colors", [])
        if not isinstance(colors, list):
            continue
        sub: Dict[str, Dict[str, str]] = {}
        for j, c in enumerate(colors[:4], start=1):
            try:
                hx = normalize_hex(str(c))
            except ValueError:
                continue
            sub[f"Color {j}"] = {"$type": "color", "$value": hx}
        if sub:
            tokens[group] = sub

    path.write_text(json.dumps(tokens, ensure_ascii=False, indent=2), encoding="utf-8")


def _pack_utf16be_name(name: str) -> bytes:
    encoded = name.encode("utf-16-be")
    char_count = len(name) + 1
    return struct.pack(">H", char_count) + encoded + b"\x00\x00"


def _ase_color_block(name: str, hex_color: str) -> bytes:
    r, g, b = hex_to_rgb(hex_color)
    color_mode = b"RGB "
    rgb = struct.pack(">fff", r / 255.0, g / 255.0, b / 255.0)
    color_type = struct.pack(">H", 0)
    payload = _pack_utf16be_name(name) + color_mode + rgb + color_type
    return struct.pack(">HI", 0x0001, len(payload)) + payload


def export_ase(palettes: List[Dict[str, object]], path: Path) -> None:
    blocks: List[bytes] = []
    idx = 1
    for item in palettes:
        base = str(item.get("name", "Palette")).strip()
        colors = item.get("colors", [])
        if not isinstance(colors, list):
            continue
        for j, c in enumerate(colors[:4], start=1):
            try:
                hx = normalize_hex(str(c))
            except ValueError:
                continue
            blocks.append(_ase_color_block(f"{base} {j}", hx))
            idx += 1

    header = b"ASEF" + struct.pack(">HHI", 1, 0, len(blocks))
    path.write_bytes(header + b"".join(blocks))
