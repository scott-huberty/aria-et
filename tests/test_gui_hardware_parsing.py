import pytest

pytest.importorskip("PySide6")

from aria_et.gui.pages.hardware import parse_tracker_lines

CHECK_OUTPUT = [
    "Tobii Pro SDK 2.1.0.1 is available.",
    "Found 1 Tobii eye tracker.",
    (
        "1. Tobii Pro Spectrum model=Tobii Pro Spectrum "
        "serial=TPSP1-010214213025 address=tobii-prp://169.254.10.180"
    ),
]


def test_parse_tracker_lines_extracts_the_discovered_tracker():
    assert parse_tracker_lines(CHECK_OUTPUT) == [
        {
            "name": "Tobii Pro Spectrum",
            "model": "Tobii Pro Spectrum",
            "serial": "TPSP1-010214213025",
            "address": "tobii-prp://169.254.10.180",
            "firmware": "unknown",
        }
    ]


def test_parse_tracker_lines_ignores_prose():
    assert parse_tracker_lines(CHECK_OUTPUT[:2]) == []


def test_parse_tracker_lines_handles_multiple_trackers():
    lines = CHECK_OUTPUT + [
        "2. Second Tracker model=Spectrum serial=SN2 address=tobii-prp://169.254.10.181"
    ]

    assert [tracker["serial"] for tracker in parse_tracker_lines(lines)] == [
        "TPSP1-010214213025",
        "SN2",
    ]
