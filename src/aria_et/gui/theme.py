"""ARIA brand palette and Qt stylesheet for the GUI."""

from __future__ import annotations

# Exact values from the ARIA Google Doc template colour table. Do not adjust
# these without a corresponding change to the template.
PALETTE: dict[str, str] = {
    "aria_teal": "#006860",
    "aria_teal_dark": "#004D47",
    "aria_green": "#6CC351",
    "aria_blue": "#356584",
    "aria_slate": "#5F6E78",
    "aria_periwinkle": "#878CBE",
    "aria_gray": "#595959",
    "aria_black": "#000000",
    # Chrome and status neutrals. The document palette has no window chrome or
    # failure states, so these are additions rather than brand colours.
    "surface": "#FFFFFF",
    "surface_alt": "#F4F6F7",
    "surface_selected": "#E6F0EF",
    "border": "#D8DEE1",
    "amber": "#B37A00",
    "amber_surface": "#FFF6E0",
    "red": "#B3261E",
}

BRAND_FONT_CANDIDATES = ("Nunito Sans", "Montserrat")
MONOSPACE_FONT_CANDIDATES = ("SF Mono", "Menlo", "Consolas", "Courier New")


def resolve_font_family(candidates, available) -> str | None:
    available_set = set(available)
    for candidate in candidates:
        if candidate in available_set:
            return candidate
    return None


_STYLESHEET = """
QWidget {{
    background-color: {surface_alt};
    color: {aria_black};
    font-size: 13px;
}}

QLabel#PageHeading {{
    color: {aria_teal};
    font-size: 20px;
    font-weight: 600;
}}

QLabel#SectionHeading {{
    color: {aria_blue};
    font-size: 15px;
    font-weight: 600;
}}

QLabel#SubsectionHeading {{
    color: {aria_slate};
    font-size: 13px;
    font-weight: 600;
}}

QLabel#HelperText {{
    color: {aria_gray};
    font-size: 12px;
}}

QLabel#ErrorText {{
    color: {red};
    font-size: 12px;
}}

QFrame#Card {{
    background-color: {surface};
    border: 1px solid {border};
    border-radius: 6px;
}}

QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
    background-color: {surface};
    border: 1px solid {border};
    border-radius: 4px;
    padding: 5px 7px;
}}

QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
    border: 1px solid {aria_teal};
}}

QLineEdit[invalid="true"] {{
    border: 1px solid {red};
}}

QPushButton {{
    background-color: {surface};
    border: 1px solid {border};
    border-radius: 4px;
    padding: 6px 14px;
}}

QPushButton:hover {{
    border: 1px solid {aria_teal};
}}

QPushButton:disabled {{
    color: {aria_gray};
    border: 1px solid {border};
}}

QPushButton#Primary {{
    background-color: {aria_teal};
    border: 1px solid {aria_teal};
    color: {surface};
    font-weight: 600;
}}

QPushButton#Primary:hover {{
    background-color: {aria_teal_dark};
    border: 1px solid {aria_teal_dark};
}}

QPushButton#Primary:disabled {{
    background-color: {border};
    border: 1px solid {border};
    color: {aria_gray};
}}

QPushButton#Destructive {{
    background-color: {red};
    border: 1px solid {red};
    color: {surface};
    font-weight: 600;
}}

QListWidget#NavList {{
    background-color: {surface};
    border: none;
    border-right: 1px solid {border};
    outline: none;
}}

QListWidget#NavList::item {{
    padding: 10px 14px;
    color: {aria_slate};
}}

QListWidget#NavList::item:selected {{
    background-color: {surface_selected};
    color: {aria_teal};
    font-weight: 600;
}}

QPlainTextEdit#LogPane {{
    background-color: {surface};
    border: 1px solid {border};
    border-radius: 4px;
    font-family: "{monospace_font}";
    font-size: 12px;
}}

QLabel#ModeBanner {{
    background-color: {amber_surface};
    color: {amber};
    border: 1px solid {amber};
    border-radius: 4px;
    font-weight: 700;
    padding: 8px 12px;
}}

QProgressBar {{
    background-color: {surface_alt};
    border: 1px solid {border};
    border-radius: 4px;
    text-align: center;
}}

QProgressBar::chunk {{
    background-color: {aria_periwinkle};
    border-radius: 3px;
}}
"""


def stylesheet(monospace_font: str = "monospace") -> str:
    return _STYLESHEET.format(monospace_font=monospace_font, **PALETTE)
