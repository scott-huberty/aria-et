import json

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from aria_et.config import AriaEtConfig
from aria_et.gui import state
from aria_et.gui.pages.battery import (
    BUFFERED_SAMPLE_CAVEAT,
    BatteryPage,
    describe_stop_confirmation,
)
from aria_et.gui.widgets.crash_panel import (
    CRASH_LOG_LINES,
    NO_END_EVENT_MESSAGE,
    CrashPanel,
    describe_crash,
)

pytestmark = pytest.mark.qt_gui


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def config(tmp_path):
    return AriaEtConfig(data_root=tmp_path / "aria-data")


@pytest.fixture
def session(config):
    return state.SessionState(subject="abby", data_root=config.data_root)


def _run_dir(session, task_id, run_label, events):
    directory = (
        session.sourcedata_root
        / "sub-abby"
        / f"ses-{session.session}"
        / f"task-{task_id}_run-{run_label}"
    )
    directory.mkdir(parents=True)
    (directory / "events.jsonl").write_text(
        "".join(json.dumps({"name": name}) + "\n" for name in events),
        encoding="utf-8",
    )
    return directory


def _ready_page(config, session):
    page = BatteryPage(config)
    page.set_session(session)
    page.set_tracker_checked(True)
    return page


def test_stop_confirmation_names_the_task_and_the_consequence():
    prompt = describe_stop_confirmation("social-interactive")

    assert prompt.startswith("Stop Social Interactive?")
    assert "marked incomplete" in prompt


def test_stop_confirmation_mentions_the_caveat_only_where_it_applies(monkeypatch):
    monkeypatch.setattr("aria_et.gui.pages.battery.SIGINT_SUPPORTED", False)

    assert BUFFERED_SAMPLE_CAVEAT in describe_stop_confirmation("social-interactive")


def test_stop_is_only_emitted_once_confirmed(qapp, config, session):
    page = _ready_page(config, session)
    page._start_run("social-interactive")
    stops = []
    page.stop_requested.connect(lambda: stops.append(True))

    page._confirm_stop()

    assert stops == [True]


def test_a_confirmed_stop_does_not_raise_the_crash_panel(qapp, config, session):
    page = _ready_page(config, session)
    page._start_run("social-interactive")
    _run_dir(session, "social-interactive", "01", ["social-interactive.started"])
    page._confirm_stop()

    page.report_exit(0, ["some output"])

    assert not page._crash_panel.isVisibleTo(page)


def test_an_unexpected_incomplete_run_raises_the_crash_panel(qapp, config, session):
    page = _ready_page(config, session)
    page._start_run("social-interactive")
    _run_dir(session, "social-interactive", "01", ["social-interactive.started"])

    page.report_exit(0, ["glDeleteBuffers"])

    assert page._crash_panel.isVisibleTo(page)
    assert "run-01" in page._crash_panel._detail.text()
    assert "glDeleteBuffers" in page._crash_panel._log.toPlainText()


def test_a_failed_run_raises_the_crash_panel(qapp, config, session):
    page = _ready_page(config, session)
    page._start_run("social-interactive")

    page.report_exit(2, [])

    assert page._crash_panel.isVisibleTo(page)
    assert "exit code 2" in page._crash_panel._detail.text()


def test_a_completed_run_leaves_the_crash_panel_hidden(qapp, config, session):
    page = _ready_page(config, session)
    page._start_run("social-interactive")
    _run_dir(
        session,
        "social-interactive",
        "01",
        ["social-interactive.started", "social-interactive.ended"],
    )

    page.report_exit(0, [])

    assert not page._crash_panel.isVisibleTo(page)


def test_a_new_run_clears_the_previous_crash(qapp, config, session):
    page = _ready_page(config, session)
    page._start_run("social-interactive")
    page.report_exit(1, [])
    assert page._crash_panel.isVisibleTo(page)

    page._start_run("social-interactive")

    assert not page._crash_panel.isVisibleTo(page)


def test_describe_crash_explains_a_clean_exit_without_an_end_event():
    assert describe_crash("Social Interactive", "01", 0) == (
        f"Social Interactive — run-01 — exit code 0. {NO_END_EVENT_MESSAGE}"
    )


def test_describe_crash_uses_the_exit_code_message(qapp):
    detail = describe_crash("Social Interactive", None, 2)

    assert detail.startswith("Social Interactive — exit code 2.")
    assert "Tobii Pro SDK" in detail


def test_crash_panel_keeps_only_the_last_lines(qapp, tmp_path):
    panel = CrashPanel()

    panel.show_crash(
        "Social Interactive",
        run_label="01",
        exit_code=1,
        log_lines=[str(number) for number in range(100)],
        run_dir=tmp_path,
    )

    lines = panel._log.toPlainText().splitlines()
    assert len(lines) == CRASH_LOG_LINES
    assert lines[-1] == "99"


def test_crash_panel_offers_the_log_only_when_it_exists(qapp, tmp_path):
    panel = CrashPanel()

    panel.show_crash(
        "Social Interactive",
        run_label="01",
        exit_code=1,
        log_lines=[],
        run_dir=tmp_path,
    )
    assert panel._open_folder.isEnabled()
    assert not panel._open_log.isEnabled()

    (tmp_path / "session.log").write_text("", encoding="utf-8")
    panel.show_crash(
        "Social Interactive",
        run_label="01",
        exit_code=1,
        log_lines=[],
        run_dir=tmp_path,
    )
    assert panel._open_log.isEnabled()
