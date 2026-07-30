import pytest


def pytest_collection_modifyitems(config, items):
    marker_expression = config.getoption("-m")
    if "psychopy_smoke" in marker_expression:
        return

    skip_psychopy_smoke = pytest.mark.skip(
        reason="Run with `pytest -m psychopy_smoke` to execute PsychoPy GUI smoke tests."
    )
    for item in items:
        if "psychopy_smoke" in item.keywords:
            item.add_marker(skip_psychopy_smoke)
