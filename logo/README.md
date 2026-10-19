# ARIA logo sources

The generator draws five fixed, illustrative Gaussian fixation clusters with
NumPy. Matplotlib clips the gaze-density heatmap and its contours to Montserrat
Black letter outlines, with a Nunito Sans Regular tagline. Colours come directly
from `PALETTE` in `src/aria_et/gui/theme.py`; there is no participant gaze data.
The approach is inspired by MNE-Python's `logo/generate_mne_logos.py`.

## Regenerate

Generation dependencies are recorded separately as the **optional `logo` extra**
in `pyproject.toml`: Matplotlib 3.10.9, NumPy 2.2.6, and Pillow 12.3.0. They are
not added to the application's runtime dependency list.

In an existing development environment:

```powershell
conda activate aria-et
python -m pip install --no-build-isolation -e ".[logo]"
python logo/generate_aria_logos.py
```

For a throwaway generation environment, without the application's dependencies:

```powershell
conda create -n aria-logo -c conda-forge python=3.10 matplotlib=3.10.9 numpy=2.2.6 pillow=12.3.0
conda activate aria-logo
python logo/generate_aria_logos.py
```

Run the script from the repository root. Both fonts are bundled; generation
does not download anything. A missing font raises `FileNotFoundError` instead
of substituting an installed font. SVGs contain outlined text, so viewing the
logos does not require these fonts either.

The script uses fixed coordinates, a fixed SVG ID salt, and no timestamps or
randomness. Running it twice with the same rendering environment produces
identical bytes, including PNG previews. Keep the pinned dependencies when
regenerating; FreeType and other native renderer versions may affect output
across platforms. Activate the conda environment before running Python so its
native rendering libraries can be found on Windows.

## Outputs

| File | Purpose |
| --- | --- |
| `docs/source/_static/aria_logo.svg` | Transparent light-mode wordmark and tagline |
| `docs/source/_static/aria_logo_dark.svg` | Transparent dark-mode wordmark and light tagline |
| `docs/source/_static/aria_logo_small.svg` | Compact wordmark without the tagline |
| `docs/source/_static/favicon.ico` | Docs favicon with all seven Windows sizes |
| `src/aria_et/assets/icons/aria_icon.png` | Transparent 256 × 256 round GUI icon |
| `src/aria_et/assets/icons/aria_icon.ico` | Windows icon for future installers and shortcuts |
| `logo/previews/*.png` | Raster previews of each variant for PR review |

The round icon keeps **ARIA on one line**, matching the wordmarks. Both ICO
files are made from the PNG with Pillow and contain 16, 24, 32,
48, 64, 128, and 256 px frames. `favicon.png` and `aria_icon_ico.png` show native
16–64 px frames followed by a nearest-neighbour enlargement of the 16 px frame.
Qt uses the PNG because its SVG renderer cannot render these clip paths.

`TAGLINE` near the top of the generator is **EYE-TRACKING ACQUISITION**, shortened
during review. It is shared by both full wordmarks; the generator makes no
assumption about what the ARIA acronym means.

The generated icons are ordinary Git files outside the `assets/abcct/` LFS
pattern and are included by the existing package-data configuration.

## Fonts and licenses

The unmodified static TTFs are bundled with their respective SIL OFL licenses:

- [Montserrat Black source](https://github.com/JulietaUla/Montserrat/blob/555facfb2a18c72c3c0380f0d9c0f060453a9058/fonts/ttf/Montserrat-Black.ttf),
  [license](fonts/Montserrat/OFL.txt).
- [Nunito Sans Regular source](https://github.com/googlefonts/NunitoSans/blob/058bd7a2f33d6ad5ef1df985b3db403622016a8c/fonts/ttf/NunitoSans-Regular.ttf),
  [license](fonts/NunitoSans/OFL.txt).

SHA256 of the bundled TTFs:

```text
ea67b37f8776eebea135cd1fe9adeaf6f9427683e8dc11ab8398b6be5f102c60  Montserrat-Black.ttf
cfc5795f8333c94332ec2d2634056a9a7637484f89fa0f6f7d1a4efcfdfb0efa  NunitoSans-Regular.ttf
```
