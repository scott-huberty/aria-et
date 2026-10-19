"""Entry point for ``aria-et-gui``."""

from __future__ import annotations

import sys
from importlib.resources import as_file

from PySide6.QtGui import QFontDatabase, QIcon, QPixmap
from PySide6.QtWidgets import QApplication

from aria_et.assets import application_icon
from aria_et.config import load_config
from aria_et.gui.main_window import MainWindow
from aria_et.gui.theme import (
    BRAND_FONT_CANDIDATES,
    MONOSPACE_FONT_CANDIDATES,
    resolve_font_family,
    stylesheet,
)


def main(argv: list[str] | None = None) -> int:
    app = QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName("ARIA-ET")
    with as_file(application_icon()) as icon_path:
        app.setWindowIcon(QIcon(QPixmap(str(icon_path))))

    families = QFontDatabase.families()
    brand_font = resolve_font_family(BRAND_FONT_CANDIDATES, families)
    monospace_font = resolve_font_family(MONOSPACE_FONT_CANDIDATES, families)
    if brand_font is not None:
        font = app.font()
        font.setFamily(brand_font)
        app.setFont(font)
    app.setStyleSheet(stylesheet(monospace_font or "monospace"))

    screens = app.screens()
    window = MainWindow(load_config(), screen_count=len(screens))
    if screens:
        # PsychoPy owns the stimulus and ETM displays, so the operator window
        # must stay on the primary screen.
        origin = screens[0].availableGeometry().topLeft()
        window.move(origin.x() + 60, origin.y() + 40)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
