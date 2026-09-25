"""Input widgets that resist accidental changes.

Pages live in scroll areas, so a stock spin box or combo box changes value
whenever the wheel scrolls the page past it. These widgets ignore the wheel,
which hands the event to the parent so the page scrolls instead. Typing, the
arrow buttons, and clicking to open a combo box's list still work.
"""

from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QDoubleSpinBox, QSpinBox


class WheelSafeSpinBox(QSpinBox):
    """A spin box the mouse wheel never changes."""

    def wheelEvent(self, event) -> None:
        event.ignore()


class WheelSafeDoubleSpinBox(QDoubleSpinBox):
    """A double spin box the mouse wheel never changes."""

    def wheelEvent(self, event) -> None:
        event.ignore()


class WheelSafeComboBox(QComboBox):
    """A combo box the mouse wheel never changes.

    Only the closed box ignores the wheel; the opened list is a separate popup
    widget and still scrolls normally.
    """

    def wheelEvent(self, event) -> None:
        event.ignore()
