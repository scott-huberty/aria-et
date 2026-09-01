"""A small coloured status indicator used in the header and Hardware page."""

from __future__ import annotations

from enum import Enum

from PySide6.QtWidgets import QLabel

from aria_et.gui.theme import PALETTE


class PillTone(Enum):
    NEUTRAL = "neutral"
    BUSY = "busy"
    GOOD = "good"
    WARNING = "warning"
    BAD = "bad"


_TONE_COLORS: dict[PillTone, tuple[str, str]] = {
    PillTone.NEUTRAL: (PALETTE["surface_alt"], PALETTE["aria_gray"]),
    PillTone.BUSY: (PALETTE["surface_selected"], PALETTE["aria_blue"]),
    PillTone.GOOD: (PALETTE["surface_selected"], PALETTE["aria_teal"]),
    PillTone.WARNING: (PALETTE["amber_surface"], PALETTE["amber"]),
    PillTone.BAD: ("#FBE9E7", PALETTE["red"]),
}


class StatusPill(QLabel):
    def __init__(self, text: str = "", tone: PillTone = PillTone.NEUTRAL, parent=None):
        super().__init__(parent)
        self.set_status(text, tone)

    def set_status(self, text: str, tone: PillTone) -> None:
        background, foreground = _TONE_COLORS[tone]
        self.setText(f"●  {text}" if text else "")
        self.setStyleSheet(
            f"background-color: {background};"
            f" color: {foreground};"
            f" border: 1px solid {foreground};"
            " border-radius: 10px;"
            " padding: 3px 10px;"
            " font-weight: 600;"
        )
