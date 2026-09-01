import pytest


def pytest_collection_modifyitems(config, items):
    marker_expression = config.getoption("-m")

    skip_psychopy_smoke = pytest.mark.skip(
        reason="Run with `pytest -m psychopy_smoke` to execute PsychoPy GUI smoke tests."
    )
    skip_requires_eyetracker = pytest.mark.skip(
        reason=(
            "Run with `ARIA_ET_HARDWARE=1 pytest -m requires_eyetracker` "
            "to execute Tobii hardware smoke tests."
        )
    )
    skip_qt_gui = pytest.mark.skip(
        reason=(
            "Run with `QT_QPA_PLATFORM=offscreen pytest -m qt_gui` "
            "to execute Qt widget tests."
        )
    )
    for item in items:
        if "qt_gui" in item.keywords and "qt_gui" not in marker_expression:
            item.add_marker(skip_qt_gui)
        if (
            "psychopy_smoke" in item.keywords
            and "psychopy_smoke" not in marker_expression
        ):
            item.add_marker(skip_psychopy_smoke)
        if (
            "requires_eyetracker" in item.keywords
            and "requires_eyetracker" not in marker_expression
        ):
            item.add_marker(skip_requires_eyetracker)
