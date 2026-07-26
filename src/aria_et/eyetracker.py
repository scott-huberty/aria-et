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
    eyetrackers = tobii_research.find_all_eyetrackers()
    if not eyetrackers:
        error("No Tobii eye tracker was found. Connect and power on the tracker.")
        return 3

    tracker_count = len(eyetrackers)
    suffix = "" if tracker_count == 1 else "s"
    output(f"Found {tracker_count} Tobii eye tracker{suffix}.")
    for index, eyetracker in enumerate(eyetrackers, start=1):
        output(
            f"{index}. {eyetracker.device_name} "
            f"model={eyetracker.model} "
            f"serial={eyetracker.serial_number} "
            f"address={eyetracker.address}"
        )

    return 0
