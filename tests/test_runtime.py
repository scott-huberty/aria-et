import sys

import pytest

from aria_et.runtime import ManualClock


def test_manual_clock_rejects_negative_time():
    clock = ManualClock()

    with pytest.raises(ValueError, match="seconds must be non-negative"):
        clock.advance(-1)


def test_runtime_contract_does_not_import_backend_modules():
    assert "psychopy" not in sys.modules
    assert "titta" not in sys.modules
