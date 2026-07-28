"""Eye tracker availability checks."""

from __future__ import annotations

import importlib
import sys
from collections.abc import Callable
from types import ModuleType


ImportModule = Callable[[str], ModuleType]
StatusSink = Callable[[str], None]


def check_eyetracker(
    *,
    address: str | None = None,
    import_module: ImportModule = importlib.import_module,
    output_sink: StatusSink | None = None,
    error_sink: StatusSink | None = None,
) -> int:
    output = output_sink or print
    error = error_sink or (lambda message: print(message, file=sys.stderr))

    try:
        tobii_research = import_module("tobii_research")
    except ImportError:
        error(
            "Tobii Pro SDK is not available. Install it with "
            "`pip install tobii-research`."
        )
        return 2

    output(f"Tobii Pro SDK {tobii_research.__version__} is available.")
    if address is not None:
        try:
            eyetracker = tobii_research.EyeTracker(address)
        except Exception as error_message:
            error(f"No Tobii eye tracker could be opened at {address}: {error_message}")
            return 3

        output(f"Connected to Tobii eye tracker at {address}.")
        _report_eyetrackers((eyetracker,), output)
        return 0

    eyetrackers = tobii_research.find_all_eyetrackers()
    if not eyetrackers:
        error("No Tobii eye tracker was found. Connect and power on the tracker.")
        return 3

    _report_eyetrackers(eyetrackers, output)
    return 0


def _report_eyetrackers(
    eyetrackers: tuple[object, ...],
    output: StatusSink,
) -> None:
    tracker_count = len(eyetrackers)
    suffix = "" if tracker_count == 1 else "s"
    output(f"Found {tracker_count} Tobii eye tracker{suffix}.")
    for index, eyetracker in enumerate(eyetrackers, start=1):
        output(
            f"{index}. {getattr(eyetracker, 'device_name', eyetracker.model)} "
            f"model={eyetracker.model} "
            f"serial={eyetracker.serial_number} "
            f"address={eyetracker.address}"
        )
