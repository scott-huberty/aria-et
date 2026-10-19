"""Draw ARIA's gaze-density wordmarks and icons; run from the repository root."""

from __future__ import annotations

import sys
from io import BytesIO
from pathlib import Path

import matplotlib as mpl
import numpy as np
from matplotlib import font_manager
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.figure import Figure
from matplotlib.patches import Circle, PathPatch
from matplotlib.textpath import TextPath
from matplotlib.transforms import Affine2D
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from aria_et.gui.theme import PALETTE

TAGLINE = "EYE-TRACKING ACQUISITION"
FONTS = ROOT / "logo" / "fonts"
STATIC = ROOT / "docs" / "source" / "_static"
ICONS = ROOT / "src" / "aria_et" / "assets" / "icons"
PREVIEWS = ROOT / "logo" / "previews"
ICON_SIZES = (16, 24, 32, 48, 64, 128, 256)

# Normalized (x, y, horizontal spread, vertical spread, amplitude). These five
# hand-picked fixation clusters are illustrative, not participant gaze data.
FIXATIONS = (
    (0.12, 0.67, 0.14, 0.32, 1.00),
    (0.36, 0.36, 0.13, 0.22, 0.85),
    (0.57, 0.77, 0.16, 0.24, 1.20),
    (0.77, 0.43, 0.14, 0.29, 1.10),
    (0.94, 0.78, 0.12, 0.25, 0.90),
)


def load_fonts():
    """Use bundled faces exclusively, even if different fonts are installed."""
    properties = []
    for relative in (
        "Montserrat/Montserrat-Black.ttf",
        "NunitoSans/NunitoSans-Regular.ttf",
    ):
        path = FONTS / relative
        if not path.is_file():
            raise FileNotFoundError(f"Required logo font is missing: {path}")
        font_manager.fontManager.addfont(path)
        properties.append(font_manager.FontProperties(fname=path))
    return properties


def fitted_text(text, font, box):
    """Fit outlines into a box, preserving the font's aspect ratio."""
    path = TextPath((0, 0), text, prop=font, size=100)
    bounds = path.get_extents()
    x, y, width, height = box
    scale = min(width / bounds.width, height / bounds.height)
    transform = (
        Affine2D()
        .translate(-bounds.x0, -bounds.y0)
        .scale(scale)
        .translate(
            x + (width - bounds.width * scale) / 2,
            y + (height - bounds.height * scale) / 2,
        )
    )
    return transform.transform_path(path)


def canvas(width, height):
    fig = Figure(figsize=(width / 100, height / 100), dpi=100)
    FigureCanvasAgg(fig)
    ax = fig.add_axes((0, 0, 1, 1))
    ax.set(xlim=(0, width), ylim=(0, height))
    ax.set_axis_off()
    return fig, ax


def gaze_field(width, height):
    x, y = np.meshgrid(np.linspace(0, 1, 800), np.linspace(0, 1, 300))
    density = np.zeros_like(x)
    for cx, cy, sx, sy, amplitude in FIXATIONS:
        density += amplitude * np.exp(
            -0.5 * (((x - cx) / sx) ** 2 + ((y - cy) / sy) ** 2)
        )
    density /= density.max()
    return x * width, y * height, density


def draw_field(ax, paths, width, height, background, *, alpha=0.92):
    """Clip both the heatmap and its contours to the letter outlines."""
    x, y, density = gaze_field(width, height)
    cmap = LinearSegmentedColormap.from_list(
        "aria_gaze",
        [
            PALETTE["aria_blue"],
            PALETTE["aria_periwinkle"],
            PALETTE["aria_teal"],
            PALETTE["aria_green"],
        ],
    )
    for path in paths:
        ax.add_patch(PathPatch(path, facecolor=background, edgecolor="none", zorder=0))
        image = ax.imshow(
            density,
            origin="lower",
            extent=(0, width, 0, height),
            aspect="auto",
            cmap=cmap,
            vmin=0,
            vmax=1,
            alpha=alpha,
            interpolation="bilinear",
            zorder=1,
        )
        image.set_clip_path(path, ax.transData)
        contours = ax.contour(
            x,
            y,
            density,
            levels=np.linspace(0.15, 0.95, 9),
            colors=[PALETTE["aria_teal_dark"]],
            alpha=0.4,
            linewidths=0.8,
            zorder=2,
        )
        contours.set_clip_path(path, ax.transData)


def save_wordmark(letter_font, tagline_font, *, dark=False, small=False):
    width, height = (1000, 240) if small else (1000, 320)
    fig, ax = canvas(width, height)
    letters = fitted_text(
        "ARIA", letter_font, (24, 20 if small else 80, 952, 200 if small else 220)
    )
    draw_field(
        ax,
        [letters],
        width,
        height,
        PALETTE["aria_slate"] if dark else PALETTE["surface"],
    )
    if not small:
        bounds = letters.get_extents()
        tagline = fitted_text(TAGLINE, tagline_font, (bounds.x0, 27, bounds.width, 23))
        ax.add_patch(
            PathPatch(
                tagline,
                facecolor=PALETTE["border"] if dark else PALETTE["aria_gray"],
                edgecolor="none",
            )
        )
    name = "aria_logo_small" if small else "aria_logo_dark" if dark else "aria_logo"
    fig.savefig(
        STATIC / f"{name}.svg",
        transparent=True,
        metadata={"Date": None, "Creator": "ARIA logo generator", "Title": "ARIA"},
    )
    # Commit raster previews as well: reviewers need no SVG renderer.
    fig.savefig(
        PREVIEWS / f"{name}.png",
        dpi=100,
        facecolor=PALETTE["aria_teal_dark"] if dark else PALETTE["surface"],
        metadata={"Software": "ARIA logo generator"},
    )
    fig.clear()


def save_icons(letter_font):
    fig, ax = canvas(256, 256)
    ax.add_patch(
        Circle(
            (128, 128),
            126,
            facecolor=PALETTE["aria_teal_dark"],
            edgecolor="none",
            zorder=-1,
        )
    )
    paths = [fitted_text("ARIA", letter_font, (10, 92, 236, 72))]
    draw_field(ax, paths, 256, 256, PALETTE["surface"], alpha=0.40)
    buffer = BytesIO()
    fig.savefig(buffer, format="png", dpi=400, transparent=True)
    buffer.seek(0)
    with Image.open(buffer) as rendered:
        icon = rendered.convert("RGBA").resize((256, 256), Image.Resampling.LANCZOS)
    icon.save(ICONS / "aria_icon.png")
    sizes = [(size, size) for size in ICON_SIZES]
    icon.save(ICONS / "aria_icon.ico", sizes=sizes)
    icon.save(STATIC / "favicon.ico", sizes=sizes)
    icon.save(PREVIEWS / "aria_icon.png")
    # Show the actual ICO frames, including a nearest-neighbour enlargement
    # alongside the native 16 px frame, for visual review of small-size detail.
    with Image.open(STATIC / "favicon.ico") as favicon:
        strip = Image.new("RGBA", (448, 144), PALETTE["surface"])
        for size, offset in ((16, 8), (24, 40), (32, 80), (48, 128), (64, 192)):
            frame = favicon.ico.getimage((size, size))
            strip.alpha_composite(frame, (offset, 8))
        smallest = favicon.ico.getimage((16, 16))
        strip.alpha_composite(
            smallest.resize((128, 128), Image.Resampling.NEAREST), (288, 8)
        )
        strip.save(PREVIEWS / "favicon.png")
        strip.save(PREVIEWS / "aria_icon_ico.png")
    fig.clear()


def main():
    for directory in (STATIC, ICONS, PREVIEWS):
        directory.mkdir(parents=True, exist_ok=True)
    # SVG otherwise contains timestamps and randomly salted clip-path IDs.
    with mpl.rc_context(
        {
            "svg.hashsalt": "aria-et-logo-v1",
            "svg.fonttype": "path",
            "path.simplify": False,
        }
    ):
        letters, tagline = load_fonts()
        save_wordmark(letters, tagline)
        save_wordmark(letters, tagline, dark=True)
        save_wordmark(letters, tagline, small=True)
        save_icons(letters)
    print("Regenerated ARIA logos, icons, and PNG previews.")


if __name__ == "__main__":
    main()
