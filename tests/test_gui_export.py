import json

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QLabel

from aria_et.cli import build_parser
from aria_et.config import AriaEtConfig
from aria_et.gui import state
from aria_et.gui.pages.export import NO_RUNS_TEXT, ExportPage

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


def _write_run(session, task_id, run_label, *, events=(), tracker="tobii", gaze=True):
    directory = (
        session.sourcedata_root
        / "sub-abby"
        / f"ses-{session.session}"
        / f"task-{task_id}_run-{run_label}"
    )
    directory.mkdir(parents=True)
    (directory / "session.json").write_text(
        json.dumps({"tracker": tracker}), encoding="utf-8"
    )
    (directory / "events.jsonl").write_text(
        "".join(json.dumps({"name": name}) + "\n" for name in events),
        encoding="utf-8",
    )
    if gaze:
        (directory / "gaze.jsonl").write_text('{"x": 0}\n', encoding="utf-8")
    return directory


def _complete(task_id):
    return (f"{task_id}.started", f"{task_id}.ended")


def test_export_shows_no_runs_without_a_session(qapp, config):
    page = ExportPage(config)

    assert page._boxes == []
    assert page._runs_container.findChild(QLabel).text() == NO_RUNS_TEXT


def test_export_pre_checks_only_complete_runs(qapp, config, session):
    _write_run(
        session, "activity-monitoring", "01", events=_complete("activity-monitoring")
    )
    _write_run(
        session, "social-interactive", "01", events=("social-interactive.started",)
    )
    page = ExportPage(config)

    page.set_session(session)

    checked = {c.run.task_id for c in page.selected_candidates()}
    assert checked == {"activity-monitoring"}


def test_export_select_all_skips_runs_without_gaze(qapp, config, session):
    _write_run(
        session, "activity-monitoring", "01", events=_complete("activity-monitoring")
    )
    _write_run(
        session,
        "social-interactive",
        "01",
        events=_complete("social-interactive"),
        tracker="none",
    )
    page = ExportPage(config)
    page.set_session(session)

    page._on_select_all()

    assert {c.run.task_id for c in page.selected_candidates()} == {
        "activity-monitoring"
    }


def test_export_select_complete_only_drops_an_incomplete_run(qapp, config, session):
    _write_run(
        session, "activity-monitoring", "01", events=("activity-monitoring.started",)
    )
    page = ExportPage(config)
    page.set_session(session)
    page._boxes[0][0].setChecked(True)

    page._on_select_complete()

    assert page.selected_candidates() == []


def test_export_shows_the_bids_root_for_the_session(qapp, config, session):
    page = ExportPage(config)

    page.set_session(session)

    assert page._bids_root.text() == str(state.bids_root(session.data_root))
    assert page._bids_root.isReadOnly()


def test_export_emits_args_the_cli_accepts(qapp, config, session):
    run_dir = _write_run(
        session, "activity-monitoring", "01", events=_complete("activity-monitoring")
    )
    page = ExportPage(config)
    page.set_session(session)
    emitted = []
    page.export_requested.connect(emitted.append)

    page._start_export()

    build_parser(config).parse_args(emitted[0])
    assert emitted[0] == [
        "export-bids",
        "--input",
        str(run_dir),
        "--output",
        str(state.bids_root(session.data_root)),
    ]


def test_export_runs_the_selection_one_at_a_time(qapp, config, session):
    _write_run(
        session, "activity-monitoring", "01", events=_complete("activity-monitoring")
    )
    _write_run(
        session, "social-interactive", "01", events=_complete("social-interactive")
    )
    page = ExportPage(config)
    page.set_session(session)
    emitted = []
    page.export_requested.connect(emitted.append)

    page._start_export()
    assert len(emitted) == 1
    assert not page._export_button.isEnabled()

    page.report_exit(0)
    assert len(emitted) == 2

    page.report_exit(0)
    assert len(emitted) == 2
    assert page._export_button.isEnabled()


def test_export_lists_the_files_a_successful_run_wrote(qapp, config, session):
    _write_run(
        session, "activity-monitoring", "01", events=_complete("activity-monitoring")
    )
    page = ExportPage(config)
    page.set_session(session)
    page._start_export()

    page.record_output_line("Exported BIDS eyetracking files to /data/bids.")
    page.record_output_line("/data/bids/sub-abby/eyetrack.tsv.gz")
    page.report_exit(0)

    lines = page._results_label.text().splitlines()
    assert lines[0] == "✓  task-activity-monitoring_run-01"
    assert lines[1].strip() == "/data/bids/sub-abby/eyetrack.tsv.gz"


def test_export_marks_a_failed_run_with_its_exit_code(qapp, config, session):
    _write_run(
        session, "activity-monitoring", "01", events=_complete("activity-monitoring")
    )
    page = ExportPage(config)
    page.set_session(session)
    page._start_export()

    page.report_exit(1)

    assert "exit code 1" in page._results_label.text()


def test_export_continues_after_one_run_fails(qapp, config, session):
    _write_run(
        session, "activity-monitoring", "01", events=_complete("activity-monitoring")
    )
    _write_run(
        session, "social-interactive", "01", events=_complete("social-interactive")
    )
    page = ExportPage(config)
    page.set_session(session)
    emitted = []
    page.export_requested.connect(emitted.append)

    page._start_export()
    page.report_exit(1)

    assert len(emitted) == 2


def test_export_abandons_the_queue_when_the_process_cannot_start(qapp, config, session):
    _write_run(
        session, "activity-monitoring", "01", events=_complete("activity-monitoring")
    )
    _write_run(
        session, "social-interactive", "01", events=_complete("social-interactive")
    )
    page = ExportPage(config)
    page.set_session(session)
    emitted = []
    page.export_requested.connect(emitted.append)

    page._start_export()
    page.report_failed_to_start("aria-et is not installed")

    assert len(emitted) == 1
    assert "aria-et is not installed" in page._results_label.text()
    assert page._export_button.isEnabled()


def test_export_does_nothing_without_a_selection(qapp, config, session):
    _write_run(
        session, "activity-monitoring", "01", events=("activity-monitoring.started",)
    )
    page = ExportPage(config)
    page.set_session(session)
    emitted = []
    page.export_requested.connect(emitted.append)

    page._start_export()

    assert emitted == []


@pytest.mark.parametrize("exit_codes, succeeded", [((0, 0), True), ((0, 1), False)])
def test_export_reports_success_only_when_every_run_exported(
    qapp, config, session, exit_codes, succeeded
):
    for task_id in ("activity-monitoring", "social-interactive"):
        _write_run(session, task_id, "01", events=_complete(task_id))
    page = ExportPage(config)
    page.set_session(session)
    assert not page.export_succeeded

    page._start_export()
    for code in exit_codes:
        page.report_exit(code)

    assert page.export_succeeded is succeeded


def test_export_success_resets_for_a_new_session(qapp, config, session):
    _write_run(
        session, "activity-monitoring", "01", events=_complete("activity-monitoring")
    )
    page = ExportPage(config)
    page.set_session(session)
    page._start_export()
    page.report_exit(0)
    assert page.export_succeeded

    page.set_session(state.SessionState(subject="bobby", data_root=config.data_root))

    assert not page.export_succeeded


def test_export_is_not_a_success_when_the_command_fails_to_start(
    qapp, config, session
):
    page = ExportPage(config)
    page.set_session(session)

    page.report_failed_to_start("aria-et could not be started")

    assert not page.export_succeeded

