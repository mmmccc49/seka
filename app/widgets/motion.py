"""Small reusable motion helpers for the Qt interface."""

from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPoint, QPropertyAnimation, QSequentialAnimationGroup, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QGraphicsDropShadowEffect, QGraphicsOpacityEffect, QPushButton, QWidget


class MotionButton(QPushButton):
    """A QPushButton with a lightweight hover lift and click pulse."""

    def __init__(self, text: str = "", parent=None) -> None:
        super().__init__(text, parent)
        self._shadow = QGraphicsDropShadowEffect(self)
        self._shadow.setBlurRadius(18)
        self._shadow.setOffset(0, 7)
        self._shadow.setColor(QColor(33, 40, 52, 34))
        self.setGraphicsEffect(self._shadow)

    def enterEvent(self, event) -> None:
        self._set_lifted(True)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._set_lifted(False)
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:
        self._shadow.setBlurRadius(12)
        self._shadow.setOffset(0, 3)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        super().mouseReleaseEvent(event)
        QTimer.singleShot(80, lambda: self._set_lifted(self.underMouse()))

    def _set_lifted(self, lifted: bool) -> None:
        self._shadow.setBlurRadius(24 if lifted else 18)
        self._shadow.setOffset(0, 12 if lifted else 7)


def fade_in(widget: QWidget, duration: int = 260, delay: int = 0) -> None:
    """Fade a widget in once it has been added to a visible layout."""

    effect = QGraphicsOpacityEffect(widget)
    effect.setOpacity(0.0)
    widget.setGraphicsEffect(effect)

    anim = QPropertyAnimation(effect, b"opacity", widget)
    anim.setDuration(duration)
    anim.setStartValue(0.0)
    anim.setEndValue(1.0)
    anim.setEasingCurve(QEasingCurve.OutCubic)

    if delay <= 0:
        anim.start(QPropertyAnimation.DeleteWhenStopped)
    else:
        QTimer.singleShot(delay, lambda: anim.start(QPropertyAnimation.DeleteWhenStopped))


def pulse(widget: QWidget, distance: int = 3, duration: int = 90) -> None:
    """Small vertical pulse useful after a successful command."""

    start = widget.pos()
    up = QPropertyAnimation(widget, b"pos", widget)
    up.setDuration(duration)
    up.setStartValue(start)
    up.setEndValue(start + QPoint(0, -distance))
    up.setEasingCurve(QEasingCurve.OutCubic)

    down = QPropertyAnimation(widget, b"pos", widget)
    down.setDuration(duration + 30)
    down.setStartValue(start + QPoint(0, -distance))
    down.setEndValue(start)
    down.setEasingCurve(QEasingCurve.OutCubic)

    group = QSequentialAnimationGroup(widget)
    group.addAnimation(up)
    group.addAnimation(down)
    group.start(QSequentialAnimationGroup.DeleteWhenStopped)
