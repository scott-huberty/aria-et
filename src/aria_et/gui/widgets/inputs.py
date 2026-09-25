"""Input widgets that resist accidental changes."""

from __future__ import annotations

from PySide6.QtWidgets import QSpinBox


class WheelSafeSpinBox(QSpinBox):
    """A spin box the mouse wheel never changes.

    Pages live in scroll areas, so a stock spin box changes value whenever the
    wheel scrolls the page past it. Ignoring the event hands it to the parent,
    which scrolls the page instead. Typing and the arrow buttons still work.
    """

    def wheelEvent(self, event) -> None:
        event.ignore()
