"""Live child-position panel: the tracker's track box, both eyes, and distance.

Drawn like DeToX's positioning screen, so the operator sees the same picture
the child saw before calibration, but it stays live during calibration and
runs. It reads a :class:`~aria_et.position_monitor.PositionMonitor` on a timer.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget

from aria_et.calibration import DETOX_EYE_COLORS, POSITION_IDEAL_Z, POSITION_Z_TOLERANCE
from aria_et.gui.theme import PALETTE
from aria_et.position_monitor import (
    STATUS_TEXT,
    classify,
    mean_distance,
    panel_position,
)

REFRESH_MILLISECONDS = 66  # about 15 Hz: smooth enough, and cheap
EYE_RADIUS = 6
CONNECTING_TEXT = "Connecting to tracker…"


class TrackBoxPanel(QWidget):
    """Track box with the eye dots, a distance bar and a status line."""

    def __init__(self, monitor=None, parent=None):
        super().__init__(parent)
        self._monitor = monitor
        self.setMinimumSize(170, 165)
        self.setToolTip(
            "Where the tracker sees the child's eyes inside its tracking box. "
            "Keep both dots near the middle and the distance marker near the "
            "centre line."
        )
        self._timer = QTimer(self)
        self._timer.setInterval(REFRESH_MILLISECONDS)
        self._timer.timeout.connect(self.update)

    def set_monitor(self, monitor) -> None:
        self._monitor = monitor
        self.update()

    def status_key(self) -> str:
        """The current status: a STATUS_TEXT key, or "connecting"."""
        monitor = self._monitor
        if monitor is None or monitor.status in ("stopped", "unavailable"):
            return "no_tracker"
        if monitor.status == "connecting":
            return "connecting"
        return classify(monitor.latest(), monitor.now())

    def status_text(self) -> str:
        key = self.status_key()
        return CONNECTING_TEXT if key == "connecting" else STATUS_TEXT[key]

    # Only refresh while visible, so a hidden panel costs nothing.
    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._timer.start()

    def hideEvent(self, event) -> None:
        super().hideEvent(event)
        self._timer.stop()

    def is_refreshing(self) -> bool:
        return self._timer.isActive()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        width = self.width()
        margin = 10
        title_height = 18
        box = QRectF(margin, title_height + 4, width - 2 * margin, 82)
        bar_y = box.bottom() + 16
        status_y = bar_y + 14

        painter.setPen(QColor(PALETTE["aria_gray"]))
        painter.drawText(
            QRectF(margin, 0, width - 2 * margin, title_height),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            "Child position",
        )

        # Track box, with faint centre guides.
        painter.setPen(QPen(QColor(PALETTE["border"]), 1))
        painter.setBrush(QColor(PALETTE["surface_alt"]))
        painter.drawRoundedRect(box, 4, 4)
        painter.setPen(QPen(QColor(PALETTE["border"]), 1, Qt.PenStyle.DashLine))
        painter.drawLine(
            QPointF(box.center().x(), box.top()),
            QPointF(box.center().x(), box.bottom()),
        )
        painter.drawLine(
            QPointF(box.left(), box.center().y()),
            QPointF(box.right(), box.center().y()),
        )

        key = self.status_key()
        monitor = self._monitor
        sample = None
        if monitor is not None and key not in ("no_tracker", "connecting", "stale"):
            sample = monitor.latest()

        # Eye dots, in DeToX's eye colours (opaque on the light theme).
        if sample is not None:
            for eye, (x, y, _z) in sample.eyes().items():
                px, py = panel_position(x, y)
                red, green, blue, _alpha = DETOX_EYE_COLORS[eye]
                painter.setPen(QPen(QColor(PALETTE["aria_gray"]), 1))
                painter.setBrush(QColor(red, green, blue))
                painter.drawEllipse(
                    QRectF(
                        box.left() + px * box.width() - EYE_RADIUS,
                        box.top() + py * box.height() - EYE_RADIUS,
                        2 * EYE_RADIUS,
                        2 * EYE_RADIUS,
                    )
                )

        # Distance bar: the good band, the ideal line, and the current distance.
        bar = QRectF(box.left(), bar_y - 3, box.width(), 6)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(PALETTE["surface_alt"]))
        painter.drawRoundedRect(bar, 3, 3)
        low = POSITION_IDEAL_Z - POSITION_Z_TOLERANCE
        high = POSITION_IDEAL_Z + POSITION_Z_TOLERANCE
        painter.setBrush(QColor(PALETTE["surface_selected"]))
        painter.drawRect(
            QRectF(
                bar.left() + low * bar.width(),
                bar.top(),
                (high - low) * bar.width(),
                bar.height(),
            )
        )
        ideal_x = bar.left() + POSITION_IDEAL_Z * bar.width()
        painter.setPen(QPen(QColor(PALETTE["aria_teal"]), 2))
        painter.drawLine(
            QPointF(ideal_x, bar.top() - 3), QPointF(ideal_x, bar.bottom() + 3)
        )
        z = mean_distance(sample)
        if z is not None:
            marker_x = bar.left() + min(max(z, 0.0), 1.0) * bar.width()
            painter.setPen(QPen(QColor(PALETTE["aria_gray"]), 1))
            painter.setBrush(QColor(PALETTE["aria_slate"]))
            painter.drawEllipse(QRectF(marker_x - 5, bar.center().y() - 5, 10, 10))
        painter.setPen(QColor(PALETTE["aria_gray"]))
        small = painter.font()
        small.setPointSizeF(max(small.pointSizeF() - 2, 6))
        painter.setFont(small)
        painter.drawText(
            QRectF(bar.left(), bar.bottom() + 1, 40, 12),
            Qt.AlignmentFlag.AlignLeft,
            "near",
        )
        painter.drawText(
            QRectF(bar.right() - 40, bar.bottom() + 1, 40, 12),
            Qt.AlignmentFlag.AlignRight,
            "far",
        )

        # Status line: teal when good, amber otherwise, grey when no data.
        if key == "good":
            color = PALETTE["aria_teal"]
        elif key in ("no_tracker", "connecting"):
            color = PALETTE["aria_gray"]
        else:
            color = PALETTE["amber"]
        font = painter.font()
        font.setPointSizeF(font.pointSizeF() + 2)
        font.setBold(key not in ("no_tracker", "connecting"))
        painter.setFont(font)
        painter.setPen(QColor(color))
        painter.drawText(
            QRectF(margin, status_y + 4, width - 2 * margin, 20),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            self.status_text(),
        )
        painter.end()
