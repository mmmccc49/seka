"""Windows global hotkey registration via native event filter."""

from __future__ import annotations

import ctypes
import os
from ctypes import wintypes
from typing import Optional, Tuple

from PySide6.QtCore import QObject, QAbstractNativeEventFilter, Signal


class GlobalHotkeyManager(QObject, QAbstractNativeEventFilter):
    activated = Signal()

    WM_HOTKEY = 0x0312
    MOD_ALT = 0x0001
    MOD_CONTROL = 0x0002
    MOD_SHIFT = 0x0004

    def __init__(self, app, hotkey_id: int = 0xBEEF, shortcut: str = "Ctrl+Shift+C") -> None:
        super().__init__()
        self._app = app
        self._hotkey_id = hotkey_id
        self._installed_filter = False
        self._registered = False

        self._shortcut_text = "Ctrl+Shift+C"
        self._modifiers = self.MOD_CONTROL | self.MOD_SHIFT
        self._vk = 0x43

        self._user32 = None
        if os.name == "nt":
            self._user32 = ctypes.windll.user32

        self.set_shortcut(shortcut)

    @property
    def is_registered(self) -> bool:
        return self._registered

    @property
    def shortcut_text(self) -> str:
        return self._shortcut_text

    @staticmethod
    def parse_shortcut(shortcut: str) -> Optional[Tuple[int, int, str]]:
        if not shortcut:
            return None

        text = shortcut.strip().replace(" ", "")
        parts = [p for p in text.split("+") if p]
        if len(parts) < 2:
            return None

        key_token = parts[-1].upper()
        mod_tokens = [p.lower() for p in parts[:-1]]

        modifiers = 0
        for token in mod_tokens:
            if token in {"ctrl", "control"}:
                modifiers |= GlobalHotkeyManager.MOD_CONTROL
            elif token == "shift":
                modifiers |= GlobalHotkeyManager.MOD_SHIFT
            elif token == "alt":
                modifiers |= GlobalHotkeyManager.MOD_ALT
            else:
                return None

        if modifiers == 0:
            return None

        vk: Optional[int] = None
        if len(key_token) == 1 and key_token.isalpha():
            vk = ord(key_token)
        elif len(key_token) == 1 and key_token.isdigit():
            vk = ord(key_token)
        elif key_token.startswith("F") and key_token[1:].isdigit():
            fn = int(key_token[1:])
            if 1 <= fn <= 24:
                vk = 0x70 + (fn - 1)

        if vk is None:
            return None

        order = [
            (GlobalHotkeyManager.MOD_CONTROL, "Ctrl"),
            (GlobalHotkeyManager.MOD_SHIFT, "Shift"),
            (GlobalHotkeyManager.MOD_ALT, "Alt"),
        ]
        names = [name for bit, name in order if modifiers & bit]
        canonical = "+".join(names + [key_token])
        return modifiers, vk, canonical

    def set_shortcut(self, shortcut: str) -> bool:
        parsed = self.parse_shortcut(shortcut)
        if parsed is None:
            return False

        modifiers, vk, canonical = parsed
        self._modifiers = modifiers
        self._vk = vk
        self._shortcut_text = canonical

        if self._registered:
            self.register()
        return True

    def register(self) -> bool:
        if self._user32 is None:
            return False

        self.unregister()
        ok = self._user32.RegisterHotKey(
            None,
            self._hotkey_id,
            self._modifiers,
            self._vk,
        )
        self._registered = bool(ok)
        if self._registered and not self._installed_filter:
            self._app.installNativeEventFilter(self)
            self._installed_filter = True
        return self._registered

    def unregister(self) -> None:
        if self._registered and self._user32 is not None:
            self._user32.UnregisterHotKey(None, self._hotkey_id)
        self._registered = False

        if self._installed_filter:
            self._app.removeNativeEventFilter(self)
            self._installed_filter = False

    def nativeEventFilter(self, event_type, message):
        if self._user32 is None:
            return False, 0

        event_type_text = str(event_type)
        if "windows" not in event_type_text:
            return False, 0

        msg = wintypes.MSG.from_address(int(message))
        if msg.message == self.WM_HOTKEY and msg.wParam == self._hotkey_id:
            self.activated.emit()
            return True, 0
        return False, 0
