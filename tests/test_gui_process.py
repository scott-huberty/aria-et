import pytest

from aria_et.gui.state import ExitSeverity, describe_exit_code

pytest.importorskip("PySide6")

from aria_et.gui.process import split_output_lines


def test_split_output_lines_holds_back_a_partial_line():
    lines, remainder = split_output_lines("", "first\nsec")

    assert lines == ["first"]
    assert remainder == "sec"


def test_split_output_lines_completes_a_held_back_line():
    lines, remainder = split_output_lines("sec", "ond\n")

    assert lines == ["second"]
    assert remainder == ""


def test_split_output_lines_normalizes_windows_line_endings():
    lines, _ = split_output_lines("", "a\r\nb\r\n")

    assert lines == ["a", "b"]


@pytest.mark.parametrize(
    ("code", "severity"),
    [
        (0, ExitSeverity.SUCCESS),
        (1, ExitSeverity.ERROR),
        (2, ExitSeverity.ERROR),
        (3, ExitSeverity.WARNING),
    ],
)
def test_exit_code_severity(code, severity):
    assert describe_exit_code(code).severity is severity


def test_sdk_missing_exit_code_names_the_sdk():
    assert "SDK" in describe_exit_code(2).message


def test_tracker_missing_exit_code_suggests_the_ethernet_link():
    assert "Ethernet" in describe_exit_code(3).message


def test_unknown_exit_code_falls_back_to_an_error():
    outcome = describe_exit_code(42)

    assert outcome.severity is ExitSeverity.ERROR
    assert "42" in outcome.message
