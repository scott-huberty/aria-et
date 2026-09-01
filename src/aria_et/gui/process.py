"""QProcess wrapper that runs the ARIA-ET CLI as a child process."""

from __future__ import annotations

import os
import signal
import sys
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, QTimer, Signal

SIGINT_SUPPORTED = os.name != "nt"

SIGINT_GRACE_MILLISECONDS = 10_000
SIGTERM_GRACE_MILLISECONDS = 5_000


class CliProcess(QObject):
    """Runs ``python -m aria_et.cli ...`` and streams its merged output."""

    started = Signal()
    output_line = Signal(str)
    finished = Signal(int)
    failed_to_start = Signal(str)

    def __init__(self, parent: QObject | None = None, executable: str | None = None):
        super().__init__(parent)
        self._executable = executable or sys.executable
        self._buffer = ""
        self._process = QProcess(self)
        self._process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self._process.setProcessEnvironment(QProcessEnvironment.systemEnvironment())
        self._process.setWorkingDirectory(str(Path.home()))
        self._process.readyReadStandardOutput.connect(self._drain_output)
        self._process.started.connect(self.started)
        self._process.finished.connect(self._on_finished)
        self._process.errorOccurred.connect(self._on_error)

    def start(self, args: list[str]) -> None:
        if self.is_running():
            raise RuntimeError("A CLI process is already running.")
        self._buffer = ""
        self._process.start(self._executable, ["-m", "aria_et.cli", *args])

    def is_running(self) -> bool:
        return self._process.state() != QProcess.ProcessState.NotRunning

    def request_stop(self) -> None:
        """Interrupt the child so its ``finally`` blocks drain the gaze writer."""
        if not self.is_running():
            return
        if SIGINT_SUPPORTED:
            os.kill(self._process.processId(), signal.SIGINT)
            QTimer.singleShot(SIGINT_GRACE_MILLISECONDS, self._escalate_to_terminate)
        else:
            self._escalate_to_terminate()

    def kill(self) -> None:
        if self.is_running():
            self._process.kill()

    def _escalate_to_terminate(self) -> None:
        if not self.is_running():
            return
        self._process.terminate()
        QTimer.singleShot(SIGTERM_GRACE_MILLISECONDS, self.kill)

    def _drain_output(self) -> None:
        chunk = bytes(self._process.readAllStandardOutput()).decode(
            "utf-8", errors="replace"
        )
        lines, self._buffer = split_output_lines(self._buffer, chunk)
        for line in lines:
            self.output_line.emit(line)

    def _flush_buffer(self) -> None:
        if self._buffer:
            self.output_line.emit(self._buffer)
            self._buffer = ""

    def _on_finished(self, exit_code: int, _status: QProcess.ExitStatus) -> None:
        self._drain_output()
        self._flush_buffer()
        self.finished.emit(exit_code)

    def _on_error(self, error: QProcess.ProcessError) -> None:
        if error is QProcess.ProcessError.FailedToStart:
            self.failed_to_start.emit(
                f"Could not start {self._executable}: {self._process.errorString()}"
            )


def split_output_lines(buffer: str, chunk: str) -> tuple[list[str], str]:
    """Split a decoded chunk into whole lines plus the remaining partial line."""
    combined = buffer + chunk.replace("\r\n", "\n")
    *lines, remainder = combined.split("\n")
    return lines, remainder
