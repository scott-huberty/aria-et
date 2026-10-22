# aria-et

[![tests](https://github.com/scott-huberty/aria-et/actions/workflows/tests.yml/badge.svg)](https://github.com/scott-huberty/aria-et/actions/workflows/tests.yml)

Eye-tracking paradigms for the ARIA ABCCT battery recreation.

## Development

Install [pixi](https://pixi.prefix.dev/latest/installation/) **0.82.0** and run
these commands from the repository root on Windows:

```powershell
pixi install --locked
pixi run test
pixi run lint
pixi run typecheck
pixi run gui
pixi run aria-et list-tasks
```

`pixi run typecheck` runs the `ty` type checker on `src`, `tests` and
`scripts`. The pre-commit hook and the CI `typecheck` job run the same pixi
task. To enable the hooks, run `pixi run pre-commit install` once.

The default environment includes the GUI, PsychoPy, Tobii SDK, and test tools.
`pyproject.toml` declares the environments; `pixi.lock` pins the exact conda
builds and PyPI artifacts, including the wheels' bundled media libraries.
Use `pixi install --frozen` to reproduce the lock without resolving packages.

| Environment | Purpose | Command |
| --- | --- | --- |
| `default` | Windows runtime, GUI, and development tools | `pixi run test` |
| `prod` | Same locked Windows runtime and GUI, without test tools | `pixi install --locked -e prod` |
| `docs` | Isolated docs tools on Windows and Linux | `pixi run -e docs docs` |
| `lint` | Isolated Ruff on Windows and Linux | `pixi run -e lint lint` |
| `logo` | Optional logo generation tools on Windows | `pixi run -e logo generate-logos` |

Linux support is limited to docs and lint; stimulus presentation is supported
on Windows. The runtime deliberately keeps the validated PyPI media wheels
and both Qt bindings: the GUI uses conda PySide6, while PsychoPy uses PyPI
PyQt6 in a separate process. Do not replace ffpyplayer's bundled FFmpeg/SDL2
with another decoder build without repeating stimulus validation.

The validated Windows ffpyplayer wheel loads **FFmpeg 6.0**
(`6.0-full_build-www.gyan.dev`) and **SDL2 2.26.4** from its own `share/ffpyplayer`
directory. An independently installed `ffmpeg` executable reports a different
media stack and does not identify the decoder used for AM/SI playback.

To run native Qt widget tests, use `pixi run python -m pytest -m qt_gui`.
Hardware tests are opt-in and run only on the lab machine with a tracker:
`pixi run python -m pytest -m requires_eyetracker tests/test_hardware_smoke.py`.
Never use `-m "not requires_eyetracker"`; the opt-in hook matches marker names
by substring and would enable those hardware tests.

After an intentional dependency change, run `pixi lock`, review the lock diff,
and repeat the relevant tests and stimulus checks. CI uses `--locked` and
rejects a manifest that no longer matches the committed lock.
