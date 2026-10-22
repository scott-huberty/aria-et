import json
import subprocess
import sys
from importlib import metadata
from types import SimpleNamespace
from typing import Any

import pytest

from aria_et.config import AriaEtConfig
from aria_et.sysinfo import (
    CORE_PACKAGES,
    MEDIA_PACKAGES,
    collect_sys_info,
    format_sys_info,
    read_native_versions,
    write_sys_info_snapshot,
)


@pytest.fixture
def collect(tmp_path):
    def run(**overrides):
        options: dict[str, Any] = dict(
            version_lookup=lambda name: "1.2.3",
            distribution_lookup=lambda name: SimpleNamespace(
                read_text=lambda name: None
            ),
            native_reader=lambda: {"ffpyplayer": {"ffmpeg": "6.0", "sdl2": "2.26.4"}},
            registry_reader=lambda: [],
            platform_name="win32",
            environ={},
            config_path=lambda: tmp_path / "config.toml",
            config_loader=lambda: AriaEtConfig(
                tracker_address="saved-address", tracker_serial_number="saved-serial"
            ),
            etm_path_reader=lambda: str(tmp_path / "missing.exe"),
        )
        options.update(overrides)
        return collect_sys_info(**options)

    return run


def broken(*args, **kwargs):
    raise RuntimeError("probe failed\nsecond line")


def test_missing_package_and_failed_probe_are_isolated(collect):
    def lookup(name):
        if name == "psychopy":
            raise metadata.PackageNotFoundError(name)
        if name == "numpy":
            return broken()
        return "1.2.3"

    info = collect(version_lookup=lookup, native_reader=broken)
    assert info["core"]["psychopy"] == "not installed"
    assert info["core"]["numpy"] == "error: probe failed second line"
    assert info["core"]["tobii-research"] == "1.2.3"
    assert info["media"]["native"].startswith("error:")
    assert "not installed" in format_sys_info(info)
    json.dumps(info)


def test_every_baseline_package_is_reported(collect):
    info = collect()
    assert set(CORE_PACKAGES) <= info["core"].keys()
    assert set(MEDIA_PACKAGES) <= info["media"].keys()
    assert "qt6-main" in info["core"]
    assert info["system"]["python"]


def test_registry_filters_names_and_publishers_and_deduplicates(collect):
    entries = [
        {"DisplayName": "Tobii ETM", "DisplayVersion": "2.1"},
        {"DisplayName": "Driver", "Publisher": "TOBII AB", "DisplayVersion": "3.0"},
        {"DisplayName": "Other", "DisplayVersion": "99"},
        {"DisplayName": "Tobii ETM", "DisplayVersion": "2.1"},
    ]
    assert collect(registry_reader=lambda: entries)["tobii"]["installed_software"] == [
        {"name": "Driver", "version": "3.0"},
        {"name": "Tobii ETM", "version": "2.1"},
    ]
    assert collect(registry_reader=broken)["tobii"]["installed_software"].startswith(
        "error:"
    )
    assert (
        collect(platform_name="linux")["tobii"]["installed_software"]
        == "n/a (Windows only)"
    )


def test_etm_missing_and_file_version_probe(collect, tmp_path):
    result = collect()["tobii"]["eye_tracker_manager"]
    assert result == {"path": str(tmp_path / "missing.exe"), "version": "not installed"}
    path = tmp_path / "etm.exe"
    path.touch()
    info = collect(
        etm_path_reader=lambda: str(path), file_version_reader=lambda path: "2.9.0.1"
    )
    assert info["tobii"]["eye_tracker_manager"]["version"] == "2.9.0.1"
    info = collect(etm_path_reader=lambda: str(path), file_version_reader=broken)
    assert info["tobii"]["eye_tracker_manager"]["version"].startswith("error:")
    assert collect(etm_path_reader=broken)["tobii"]["eye_tracker_manager"].startswith(
        "error:"
    )


def test_tracker_property_error_does_not_hide_other_fields(collect):
    class Tracker:
        model = "Spectrum"
        serial_number = "123"
        runtime_version = "2.11"

        @property
        def firmware_version(self):
            raise RuntimeError("firmware unavailable")

    connected = collect(
        include_tracker=True, tracker_opener=lambda **kwargs: Tracker()
    )["tobii"]["connected_tracker"]
    assert connected["model"] == "Spectrum"
    assert connected["runtime_version"] == "2.11"
    assert connected["firmware_version"].startswith("error:")


def test_tracker_is_strictly_opt_in_and_uses_saved_resolution(collect):
    assert "connected_tracker" not in collect(tracker_opener=broken)["tobii"]

    def opener(**kwargs):
        assert kwargs == {"address": "saved-address", "serial_number": "saved-serial"}
        return SimpleNamespace(
            model="Spectrum", serial_number="123", firmware_version="2.6"
        )

    tracker = collect(include_tracker=True, tracker_opener=opener)["tobii"][
        "connected_tracker"
    ]
    assert tracker["model"] == "Spectrum"
    assert tracker["serial_number"] == "123"
    assert tracker["firmware_version"] == "2.6"
    assert tracker["runtime_version"] == "not reported"
    assert collect(include_tracker=True, tracker_opener=broken)["tobii"][
        "connected_tracker"
    ].startswith("error:")


def test_broken_config_does_not_hide_software_versions(collect):
    info = collect(config_loader=broken)
    assert info["config"]["error"].startswith("error:")
    assert info["core"]["psychopy"] == "1.2.3"


@pytest.mark.parametrize(
    "environ,kind",
    [
        ({"PIXI_ENVIRONMENT_NAME": "prod", "CONDA_PREFIX": "other"}, "pixi"),
        ({"CONDA_PREFIX": "prefix", "CONDA_DEFAULT_ENV": "aria-et"}, "conda"),
        ({}, "python"),
    ],
)
def test_environment_detection(collect, environ, kind):
    assert collect(environ=environ)["system"]["environment"]["kind"] == kind


def test_editable_install_records_git(collect, tmp_path):
    direct = {"url": tmp_path.as_uri(), "dir_info": {"editable": True}}
    info = collect(
        distribution_lookup=lambda name: SimpleNamespace(
            read_text=lambda name: json.dumps(direct)
        ),
        git_reader=lambda root: {"commit": "123abc", "dirty": True},
    )
    assert info["aria_et"]["editable"] is True
    assert info["aria_et"]["git"] == {"commit": "123abc", "dirty": True}


@pytest.mark.parametrize("failure", ["status", "rev-parse", "both", None])
def test_git_queries_preserve_independent_results(monkeypatch, tmp_path, failure):
    from aria_et.sysinfo import _git_info

    calls = []

    def run(command, **kwargs):
        assert kwargs["timeout"] == 2.0
        action = command[3]
        calls.append(action)
        if failure == action or failure == "both":
            raise subprocess.TimeoutExpired(command, 2.0)
        return SimpleNamespace(
            stdout="abc123\n" if action == "rev-parse" else " M file.py\n"
        )

    monkeypatch.setattr(subprocess, "run", run)
    info = _git_info(tmp_path)
    assert calls == ["rev-parse", "status"]
    if failure not in ("rev-parse", "both"):
        assert info["commit"] == "abc123"
    else:
        assert "commit" not in info
    if failure not in ("status", "both"):
        assert info["dirty"] is True
    else:
        assert "dirty" not in info
    if failure:
        assert "error" in info
        assert "timed out" in info["error"]
    else:
        assert "error" not in info


def test_missing_git_records_error(monkeypatch, tmp_path):
    from aria_et.sysinfo import _git_info

    def run(*args, **kwargs):
        raise FileNotFoundError("git not found")

    monkeypatch.setattr(subprocess, "run", run)
    info = _git_info(tmp_path)
    assert set(info) == {"error"}
    assert "git not found" in info["error"]


def test_git_error_is_visible_in_text():
    info = {
        "aria_et": {
            "version": "0.1.0",
            "git": {"commit": "abc123", "error": "status: timed out"},
        }
    }
    text = format_sys_info(info)
    assert "git abc123" in text
    assert "status: timed out" in text


def test_long_tobii_labels_keep_values_aligned():
    info = {
        "core": {"numpy": "core-marker"},
        "tobii": {
            "installed_software": [
                {
                    "name": "A long Tobii software product name",
                    "version": "version-marker",
                }
            ],
            "saved_tracker": "tracker-marker",
        },
    }
    text = format_sys_info(info)
    columns = [
        line.index(marker)
        for marker in ("core-marker", "version-marker", "tracker-marker")
        for line in text.splitlines()
        if marker in line
    ]
    assert len(set(columns)) == 1


def test_native_worker_is_bounded(monkeypatch):
    def run(*args, **kwargs):
        assert kwargs["timeout"] == 4.0
        assert "--native" in args[0]
        raise subprocess.TimeoutExpired(args[0], 4.0)

    monkeypatch.setattr(subprocess, "run", run)
    with pytest.raises(subprocess.TimeoutExpired):
        read_native_versions()


def test_default_probe_never_imports_display_or_tracker_packages():
    # A fresh interpreter avoids imports performed by other tests in this process.
    script = """
import sys
from aria_et.sysinfo import collect_sys_info
collect_sys_info(native_reader=lambda: {})
assert not any(name in sys.modules for name in
               ('psychopy', 'PySide6', 'PyQt6', 'tobii_research', 'numpy'))
"""
    subprocess.run(
        [sys.executable, "-c", script], check=True, capture_output=True, timeout=5
    )


def test_snapshot_collector_and_serialization_failures_are_best_effort(tmp_path):
    for collector in (broken, lambda **kwargs: {"bad": object()}):
        result = write_sys_info_snapshot(tmp_path, collector=collector)
        assert result["schema_version"] == 1
        assert "error" in json.loads((tmp_path / "sys_info.json").read_text())
    assert "System info snapshot:" in (tmp_path / "session.log").read_text()


def test_snapshot_write_failure_never_raises(tmp_path):
    assert "error" in write_sys_info_snapshot(
        tmp_path / "missing", collector=lambda **kwargs: {}
    )
