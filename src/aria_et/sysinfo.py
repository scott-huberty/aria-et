"""Software provenance without importing PsychoPy or contacting a tracker.

Native version queries run in a short-lived subprocess with a timeout: a broken
audio driver must not hold up acquisition. The Windows ffpyplayer wheel has no
Python version API for its bundled FFmpeg/SDL2. We use its documented ``dep_bins``
paths, call ``av_version_info`` and ``SDL_GetVersion`` on those DLLs, and record
their paths. This was verified against the locked 4.5.3 wheel (FFmpeg 6.0,
SDL2 2.26.4); DLL major-version filenames alone are not full library versions.
"""

# Diagnostic and archival probes must survive arbitrary broken installations.
# ruff: noqa: BLE001, S110

from __future__ import annotations

import ctypes
import importlib
import io
import json
import os
import platform
import shutil
import subprocess
import sys
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import url2pathname

CORE_PACKAGES = (
    "psychopy",
    "tobii-research",
    "dvst-detox",
    "PySide6",
    "numpy",
    "opencv-python",
    "pyglet",
    "PyQt6",
    "PyQt6-Qt6",
)
MEDIA_PACKAGES = (
    "ffpyplayer",
    "psychtoolbox",
    "sounddevice",
    "soundfile",
    "python-vlc",
    "moviepy",
    "imageio-ffmpeg",
)


def _error(exc: Exception) -> str:
    return "error: " + (" ".join(str(exc).split()) or type(exc).__name__)[:240]


def _probe(function, *args, **kwargs):
    try:
        return function(*args, **kwargs)
    except metadata.PackageNotFoundError:
        return "not installed"
    except Exception as exc:
        return _error(exc)


def _environment(environ):
    if environ.get("PIXI_ENVIRONMENT_NAME") or environ.get("PIXI_PROJECT_ROOT"):
        return {
            "kind": "pixi",
            "name": environ.get("PIXI_ENVIRONMENT_NAME"),
            "prefix": sys.prefix,
            "project_root": environ.get("PIXI_PROJECT_ROOT"),
        }
    if environ.get("CONDA_PREFIX") or environ.get("CONDA_DEFAULT_ENV"):
        return {
            "kind": "conda",
            "name": environ.get("CONDA_DEFAULT_ENV"),
            "prefix": environ.get("CONDA_PREFIX", sys.prefix),
        }
    return {"kind": "python", "name": None, "prefix": sys.prefix}


def _git_info(root):
    def run(*args):
        return subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True,
            text=True,
            check=True,
            timeout=2.0,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        ).stdout.strip()

    result = {}
    errors = []
    for field, args in (
        ("commit", ("rev-parse", "--short", "HEAD")),
        ("dirty", ("status", "--porcelain", "--untracked-files=normal")),
    ):
        try:
            value = run(*args)
            result[field] = bool(value) if field == "dirty" else value
        except (OSError, subprocess.SubprocessError) as exc:
            errors.append(f"{args[0]}: {_error(exc)}")
    if errors:
        result["error"] = "; ".join(errors)
    return result


def _installation(distribution_lookup, git_reader):
    from aria_et import __version__

    result = {"version": __version__}
    try:
        raw = distribution_lookup("aria-et").read_text("direct_url.json")
        direct = json.loads(raw) if raw else {}
        result["editable"] = bool(direct.get("dir_info", {}).get("editable", False))
        if result["editable"] and direct.get("url", "").startswith("file:"):
            parsed = urlparse(direct["url"])
            root = url2pathname(parsed.path)
            if parsed.netloc:
                root = "//" + parsed.netloc + root
            result["source"] = root
            result["git"] = _probe(git_reader, Path(root))
    except Exception as exc:
        result["installation"] = _error(exc)
    return result


def windows_file_version(path):
    """Read VS_FIXEDFILEINFO through version.dll; no pywin32 dependency."""
    from ctypes import wintypes

    dll = ctypes.WinDLL("version", use_last_error=True)
    dll.GetFileVersionInfoSizeW.argtypes = [
        wintypes.LPCWSTR,
        ctypes.POINTER(wintypes.DWORD),
    ]
    dll.GetFileVersionInfoSizeW.restype = wintypes.DWORD
    dll.GetFileVersionInfoW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.c_void_p,
    ]
    dll.GetFileVersionInfoW.restype = wintypes.BOOL
    dll.VerQueryValueW.argtypes = [
        ctypes.c_void_p,
        wintypes.LPCWSTR,
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.POINTER(wintypes.UINT),
    ]
    dll.VerQueryValueW.restype = wintypes.BOOL
    ignored = wintypes.DWORD()
    size = dll.GetFileVersionInfoSizeW(str(path), ctypes.byref(ignored))
    if not size:
        raise ctypes.WinError(ctypes.get_last_error())
    data = ctypes.create_string_buffer(size)
    if not dll.GetFileVersionInfoW(str(path), 0, size, data):
        raise ctypes.WinError(ctypes.get_last_error())
    pointer, length = ctypes.c_void_p(), wintypes.UINT()
    if not dll.VerQueryValueW(data, "\\", ctypes.byref(pointer), ctypes.byref(length)):
        raise ctypes.WinError(ctypes.get_last_error())
    # VS_FIXEDFILEINFO is thirteen DWORDs; file version is DWORDs 2 and 3.
    if length.value < 13 * 4:
        raise ValueError("Invalid file version resource")
    values = ctypes.cast(pointer, ctypes.POINTER(wintypes.DWORD))
    if values[0] != 0xFEEF04BD:
        raise ValueError("Invalid file version signature")
    return ".".join(
        str(v)
        for v in (
            values[2] >> 16,
            values[2] & 65535,
            values[3] >> 16,
            values[3] & 65535,
        )
    )


def read_uninstall_registry():
    """Read both Windows registry views, including per-user installations."""
    import winreg

    entries = []
    key_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"
    for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
            try:
                with winreg.OpenKey(hive, key_path, 0, winreg.KEY_READ | view) as root:
                    for index in range(winreg.QueryInfoKey(root)[0]):
                        try:
                            with winreg.OpenKey(
                                root, winreg.EnumKey(root, index)
                            ) as key:
                                entry = {}
                                for field in (
                                    "DisplayName",
                                    "DisplayVersion",
                                    "Publisher",
                                ):
                                    try:
                                        entry[field] = winreg.QueryValueEx(key, field)[
                                            0
                                        ]
                                    except FileNotFoundError:
                                        pass
                                entries.append(entry)
                        except OSError as exc:
                            entries.append({"error": _error(exc)})
            except FileNotFoundError:
                continue
            except OSError as exc:
                entries.append({"error": _error(exc)})
    return entries


def _tobii_software(entries):
    result = []
    for entry in entries:
        if "error" in entry:
            row = {"error": str(entry["error"])}
        elif (
            "tobii"
            in (
                str(entry.get("DisplayName", ""))
                + " "
                + str(entry.get("Publisher", ""))
            ).lower()
        ):
            row = {
                "name": str(entry.get("DisplayName", "Tobii product")),
                "version": str(entry.get("DisplayVersion", "not reported")),
            }
        else:
            continue
        if row not in result:
            result.append(row)
    return sorted(result, key=lambda row: row.get("name", row.get("error", "")))


def _ffpyplayer_native():
    ffpyplayer = importlib.import_module("ffpyplayer")
    result = {}
    for name, pattern in (("ffmpeg", "avutil-*.dll"), ("sdl2", "SDL2.dll")):

        def read(name=name, pattern=pattern):
            paths = [
                p
                for directory in ffpyplayer.dep_bins
                for p in Path(directory).glob(pattern)
            ]
            if not paths:
                raise FileNotFoundError(f"No bundled {pattern} in ffpyplayer.dep_bins")
            path = paths[0]
            dll = ctypes.CDLL(str(path))
            if name == "ffmpeg":
                dll.av_version_info.argtypes = []
                dll.av_version_info.restype = ctypes.c_char_p
                value = dll.av_version_info().decode("utf-8")
            else:

                class SDLVersion(ctypes.Structure):
                    _fields_ = [
                        ("major", ctypes.c_uint8),
                        ("minor", ctypes.c_uint8),
                        ("patch", ctypes.c_uint8),
                    ]

                value_struct = SDLVersion()
                dll.SDL_GetVersion.argtypes = [ctypes.POINTER(SDLVersion)]
                dll.SDL_GetVersion.restype = None
                dll.SDL_GetVersion(ctypes.byref(value_struct))
                value = (
                    f"{value_struct.major}.{value_struct.minor}.{value_struct.patch}"
                )
            return {"version": value, "path": str(path)}

        result[name] = _probe(read)
    return result


def _native_versions():
    def portaudio():
        value, description = importlib.import_module(
            "sounddevice"
        ).get_portaudio_version()
        return {"version": value, "description": description}

    return {
        "ffpyplayer": _probe(_ffpyplayer_native),
        "portaudio": _probe(portaudio),
        "libsndfile": _probe(
            lambda: importlib.import_module("soundfile").__libsndfile_version__
        ),
    }


def read_native_versions():
    """Allow cold starts while bounding native import/driver stalls to four seconds."""
    result = subprocess.run(
        [sys.executable, "-m", "aria_et.sysinfo", "--native"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
        timeout=4.0,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    return json.loads(result.stdout)


def _qt_version():
    matches = sorted((Path(sys.prefix) / "conda-meta").glob("qt6-main-*.json"))
    if not matches:
        return "not installed (conda qt6-main)"
    return json.loads(matches[0].read_text(encoding="utf-8"))["version"]


def _executable():
    if sys.argv[0] in ("-c", "-m", ""):
        return sys.executable
    path = Path(shutil.which(sys.argv[0]) or sys.argv[0]).absolute()
    # Windows console launchers may strip .exe from argv[0].
    if (
        sys.platform == "win32"
        and path.suffix != ".exe"
        and path.with_suffix(".exe").is_file()
    ):
        path = path.with_suffix(".exe")
    return str(path)


def _package_version(lookup, name):
    return str(lookup(name)).strip()


def collect_sys_info(
    *,
    include_tracker: bool = False,
    version_lookup=metadata.version,
    distribution_lookup=metadata.distribution,
    registry_reader=read_uninstall_registry,
    tracker_opener=None,
    config_loader=None,
    config_path=None,
    etm_path_reader=None,
    file_version_reader=windows_file_version,
    native_reader=read_native_versions,
    git_reader=_git_info,
    environ=None,
    platform_name=None,
) -> dict:
    """Collect independent, injectable probes; failures stay in their own rows."""
    from aria_et.config import default_config_path, load_config
    from aria_et.eyetracker import default_eyetracker_manager_path, open_eyetracker

    now = datetime.now().astimezone()
    platform_name = sys.platform if platform_name is None else platform_name
    path = _probe(config_path or default_config_path)
    config = _probe(config_loader or load_config)
    info = {
        "schema_version": 1,
        "collected_at": {
            "local": now.isoformat(),
            "utc": now.astimezone(timezone.utc).isoformat(),
        },
        "system": {
            "platform": _probe(platform.platform),
            "machine": _probe(platform.machine),
            "python": _probe(platform.python_version),
            "python_executable": sys.executable,
            "executable": _probe(_executable),
            "environment": _probe(
                _environment, os.environ if environ is None else environ
            ),
        },
        "aria_et": _installation(distribution_lookup, git_reader),
        "config": {
            "path": str(path),
            "exists": _probe(lambda: Path(path).exists()),
            "data_root": _probe(lambda: str(config.data_root)),
        },
        "core": {
            name: _probe(_package_version, version_lookup, name)
            for name in CORE_PACKAGES
        },
        "media": {
            name: {"version": _probe(_package_version, version_lookup, name)}
            for name in MEDIA_PACKAGES
        },
        "tobii": {},
    }
    if isinstance(config, str):
        info["config"]["error"] = config
        info["config"]["data_root"] = config
    info["core"]["qt6-main"] = _probe(_qt_version)
    info["media"]["native"] = _probe(native_reader)
    etm_path = _probe(
        lambda: (
            config.eye_tracker_manager
            or (etm_path_reader or default_eyetracker_manager_path)()
        )
    )
    if isinstance(config, str):
        etm_path = _probe(etm_path_reader or default_eyetracker_manager_path)

    def etm():
        if str(etm_path).startswith("error:"):
            return etm_path
        path = Path(etm_path)
        if not path.is_file():
            return {"path": str(path), "version": "not installed"}
        return {
            "path": str(path),
            "version": _probe(file_version_reader, path)
            if platform_name == "win32"
            else "n/a (Windows only)",
        }

    info["tobii"]["eye_tracker_manager"] = _probe(etm)
    info["tobii"]["installed_software"] = (
        _probe(lambda: _tobii_software(registry_reader()))
        if platform_name == "win32"
        else "n/a (Windows only)"
    )
    info["tobii"]["saved_tracker"] = _probe(
        lambda: {
            "address": config.tracker_address,
            "serial_number": config.tracker_serial_number,
        }
    )
    if isinstance(config, str):
        info["tobii"]["saved_tracker"] = config
    if include_tracker:

        def connected():
            from aria_et.cli import resolve_tracker

            if isinstance(config, str):
                return config
            address, serial = resolve_tracker(None, config)
            tracker = (tracker_opener or open_eyetracker)(
                address=address, serial_number=serial
            )
            return {
                field: _probe(
                    lambda field=field: getattr(tracker, field, "not reported")
                )
                for field in (
                    "device_name",
                    "model",
                    "serial_number",
                    "firmware_version",
                    "address",
                    "runtime_version",
                )
            }

        info["tobii"]["connected_tracker"] = _probe(connected)
    return info


def format_sys_info(info: dict) -> str:
    """Render current or archived JSON as an aligned, readable table."""
    lines = []

    def row(label, value, indent=""):
        if isinstance(value, dict):
            value = "; ".join(f"{k}={v}" for k, v in value.items())
        lines.append((indent + label, str(value)))

    system = info.get("system", {})
    if system:
        row("Platform", f"{system.get('platform')} ({system.get('machine')})")
        row("Python", f"{system.get('python')} ({system.get('python_executable')})")
        environment = system.get("environment", {})
        if isinstance(environment, dict):
            row(
                "Environment",
                f"{environment.get('kind')} env {environment.get('name')!r} ({environment.get('prefix')})",
            )
        else:
            row("Environment", environment)
        row("Executable", system.get("executable"))
    installation = info.get("aria_et", {})
    if installation:
        details = []
        if installation.get("editable"):
            details.append("editable")
        git = installation.get("git", {})
        if isinstance(git, dict) and git.get("commit"):
            details.append("git " + git["commit"])
            if git.get("dirty"):
                details.append("dirty")
        if isinstance(git, dict) and git.get("error"):
            details.append(git["error"])
        if installation.get("installation"):
            details.append(installation["installation"])
        row(
            "aria-et",
            str(installation.get("version"))
            + (f" ({', '.join(details)})" if details else ""),
        )
    config = info.get("config", {})
    if config:
        state = (
            "exists"
            if config.get("exists") is True
            else "missing"
            if config.get("exists") is False
            else config.get("exists")
        )
        row("Config", f"{config.get('path')} ({state})")
        row("Data root", config.get("data_root"))
    if "collected_at" in info:
        row("Collected at", info["collected_at"])
    if "error" in info:
        row("Error", info["error"])
    lines.extend(["", "Core"])
    for label, value in info.get("core", {}).items():
        row(label, value, "  ")
    lines.extend(["", "Media"])
    media = info.get("media", {})
    native = media.get("native", {})
    for label, value in media.items():
        if label != "native":
            row(label, value.get("version") if isinstance(value, dict) else value, "  ")
    if isinstance(native, dict):
        ffpyplayer = native.get("ffpyplayer", {})
        if isinstance(ffpyplayer, dict):
            for key, label in (("ffmpeg", "FFmpeg"), ("sdl2", "SDL2")):
                value = ffpyplayer.get(key, "not reported")
                row(
                    label,
                    value.get("version") if isinstance(value, dict) else value,
                    "  ",
                )
        else:
            row("FFmpeg / SDL2", ffpyplayer, "  ")
        audio = native.get("portaudio", "not reported")
        row(
            "PortAudio",
            audio.get("description") if isinstance(audio, dict) else audio,
            "  ",
        )
        row("libsndfile", native.get("libsndfile", "not reported"), "  ")
    else:
        row("Native libraries", native, "  ")
    lines.extend(["", "Tobii"])
    for key, label in (
        ("eye_tracker_manager", "Eye Tracker Manager"),
        ("installed_software", "Installed Tobii software"),
        ("saved_tracker", "Saved tracker"),
        ("connected_tracker", "Connected tracker"),
    ):
        if key not in info.get("tobii", {}):
            continue
        value = info["tobii"][key]
        if isinstance(value, list):
            row(label, "" if value else "none found", "  ")
            for item in value:
                row(
                    item.get("name", "Registry probe"),
                    item.get("version", item.get("error")),
                    "    ",
                )
        else:
            row(label, value, "  ")
    width = max((len(line[0]) for line in lines if isinstance(line, tuple)), default=22)
    return "\n".join(
        f"{line[0]:<{width}} {line[1]}" if isinstance(line, tuple) else line
        for line in lines
    )


def write_sys_info_snapshot(
    directory: Path, *, collector=None, error_sink=None
) -> dict:
    """Best effort provenance: never open a tracker or interrupt acquisition."""
    path = Path(directory) / "sys_info.json"
    try:
        info = (collector or collect_sys_info)(include_tracker=False)
        # Also give injected collectors the archive's required schema and timestamps.
        now = datetime.now().astimezone()
        info = {**info, "schema_version": 1}
        info.setdefault(
            "collected_at",
            {"local": now.isoformat(), "utc": now.astimezone(timezone.utc).isoformat()},
        )
        path.write_text(
            json.dumps(info, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        return info
    except Exception as exc:
        info = {"schema_version": 1, "error": _error(exc)}
        try:
            path.write_text(
                json.dumps(info, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
        except Exception:
            pass
        try:
            if error_sink is not None:
                error_sink(f"System info snapshot: {info['error']}")
            else:
                with (Path(directory) / "session.log").open(
                    "a", encoding="utf-8"
                ) as log:
                    log.write(f"System info snapshot: {info['error']}\n")
        except Exception:
            pass
        return info


if __name__ == "__main__" and sys.argv[1:] == ["--native"]:
    with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
        result = _native_versions()
    print(json.dumps(result))
