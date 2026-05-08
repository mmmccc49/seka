"""Windows global hotkey registration via native event filter."""

from __future__ import annotations

import ctypes
import os
from ctypes import wintypes

from PySide6.QtCore import QObject, QAbstractNativeEventFilter, Signal


class GlobalHotkeyManager(QObject, QAbstractNativeEventFilter):
    activated = Signal()

    WM_HOTKEY = 0x0312
    MOD_CONTROL = 0x0002
    MOD_SHIFT = 0x0004
    VK_C = 0x43

    def __init__(self, app, hotkey_id: int = 0xBEEF) -> None:
        super().__init__()
        self._app = app
        self._hotkey_id = hotkey_id
        self._installed_filter = False
        self._registered = False

        self._user32 = None
        if os.name == "nt":
            self._user32 = ctypes.windll.user32

    @property
    def is_registered(self) -> bool:
        return self._registered

    def register(self) -> bool:
        if self._user32 is None:
            return False

        self.unregister()
        ok = self._user32.RegisterHotKey(
            None,
            self._hotkey_id,
            self.MOD_CONTROL | self.MOD_SHIFT,
            self.VK_C,
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
