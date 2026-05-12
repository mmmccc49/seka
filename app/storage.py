"""Persistent storage for palette and history."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional
from uuid import uuid4

from .color_utils import DEFAULT_PRESET_PALETTES, normalize_hex


PaletteItem = Dict[str, object]


def new_palette_id() -> str:
    return uuid4().hex


@dataclass
class AppState:
    palettes: List[PaletteItem] = field(
        default_factory=lambda: [{**dict(item), "id": new_palette_id()} for item in DEFAULT_PRESET_PALETTES]
    )
    history: List[str] = field(default_factory=list)
    last_color: Optional[str] = None
    copy_format: str = "HEX"
    theme: str = "moonlight"
    hotkey_enabled: bool = True
    hotkey_shortcut: str = "Ctrl+Shift+C"


class StateStore:
    def __init__(self, filename: str = "color_picker_state.json") -> None:
        self.path = Path.home() / ".apple_min_color_picker" / filename
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _normalize_palette_item(self, item: object) -> Optional[PaletteItem]:
        if not isinstance(item, dict):
            return None
        palette_id = str(item.get("id", "")).strip() or new_palette_id()
        name = str(item.get("name", "Palette"))
        colors_raw = item.get("colors")
        if not isinstance(colors_raw, list):
            return None

        colors: List[str] = []
        for value in colors_raw[:4]:
            try:
                colors.append(normalize_hex(str(value)))
            except ValueError:
                continue

        if len(colors) == 0:
            return None

        return {"id": palette_id, "name": name, "colors": colors[:4]}

    def _migrate_old_palette(self, old_palette: List[object]) -> List[PaletteItem]:
        result: List[PaletteItem] = []
        buffer: List[str] = []
        for value in old_palette:
            try:
                buffer.append(normalize_hex(str(value)))
            except ValueError:
                continue

        for i in range(0, len(buffer), 4):
            chunk = buffer[i : i + 4]
            if len(chunk) >= 1:
                result.append({"id": new_palette_id(), "name": f"Legacy {len(result) + 1}", "colors": chunk})

        return result

    def load(self) -> AppState:
        if not self.path.exists():
            return AppState()

        try:
            raw: Dict[str, object] = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return AppState()

        state = AppState()

        palettes = raw.get("palettes")
        palette_old = raw.get("palette")
        history = raw.get("history")
        last_color = raw.get("last_color")
        copy_format = raw.get("copy_format")
        theme = raw.get("theme")
        hotkey_enabled = raw.get("hotkey_enabled")
        hotkey_shortcut = raw.get("hotkey_shortcut")

        parsed: List[PaletteItem] = []
        if isinstance(palettes, list):
            for item in palettes:
                normalized = self._normalize_palette_item(item)
                if normalized:
                    parsed.append(normalized)
        elif isinstance(palette_old, list):
            parsed = self._migrate_old_palette(palette_old)

        if parsed:
            state.palettes = parsed

        if isinstance(history, list):
            cleaned: List[str] = []
            for value in history[:10]:
                try:
                    cleaned.append(normalize_hex(str(value)))
                except ValueError:
                    continue
            state.history = cleaned

        if isinstance(last_color, str):
            try:
                state.last_color = normalize_hex(last_color)
            except ValueError:
                state.last_color = None

        if isinstance(copy_format, str) and copy_format.upper() in {"HEX", "RGB", "HSL"}:
            state.copy_format = copy_format.upper()

        if isinstance(theme, str) and theme.lower() in {"moonlight", "dark"}:
            state.theme = theme.lower()
        if isinstance(hotkey_enabled, bool):
            state.hotkey_enabled = hotkey_enabled
        if isinstance(hotkey_shortcut, str) and hotkey_shortcut.strip():
            state.hotkey_shortcut = hotkey_shortcut.strip()

        if not state.palettes:
            state.palettes = [dict(item) for item in DEFAULT_PRESET_PALETTES]

        seen_ids: set[str] = set()
        for item in state.palettes:
            palette_id = str(item.get("id", "")).strip()
            if not palette_id or palette_id in seen_ids:
                palette_id = new_palette_id()
                item["id"] = palette_id
            seen_ids.add(palette_id)

        return state

    def save(self, state: AppState) -> None:
        data = {
            "palettes": state.palettes,
            "history": state.history[:10],
            "last_color": state.last_color,
            "copy_format": state.copy_format,
            "theme": state.theme,
            "hotkey_enabled": state.hotkey_enabled,
            "hotkey_shortcut": state.hotkey_shortcut,
        }
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
