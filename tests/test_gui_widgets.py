import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel, QMessageBox

from aria_et.config import AriaEtConfig
from aria_et.gui import state
from aria_et.gui.main_window import MainWindow
from aria_et.gui.pages.setup import SetupPage, required_display_count

pytestmark = pytest.mark.qt_gui

_ENABLED = Qt.ItemFlag.ItemIsEnabled


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def config(tmp_path):
    return AriaEtConfig(data_root=tmp_path / "aria-data")


def test_setup_page_blocks_typing_invalid_characters(qapp, config):
    page = SetupPage(config)

    QTest.keyClicks(page._subject_field, "flush-test")

    assert page._subject_field.text() == "flushtest"


def test_setup_page_offers_a_correction_for_an_invalid_label(qapp, config):
    page = SetupPage(config)
    page._subject_field.setText("flush-test")

    assert page._fix_button.isVisibleTo(page)
    assert not page._open_button.isEnabled()

    page._fix_labels()

    assert page._subject_field.text() == "flushtest"
    assert page._open_button.isEnabled()
    assert not page._fix_button.isVisibleTo(page)


def test_setup_page_defaults_the_session_to_01(qapp, config):
    assert SetupPage(config)._session_field.text() == state.DEFAULT_SESSION_LABEL


def test_setup_page_disables_open_until_the_subject_is_valid(qapp, config):
    page = SetupPage(config)

    assert not page._open_button.isEnabled()

    page._subject_field.setText("abby")

    assert page._open_button.isEnabled()


def test_setup_page_opens_a_new_session(qapp, config):
    page = SetupPage(config)
    page._subject_field.setText("abby")

    page._open_session()

    assert page.session is not None
    assert page.session.session == "01"
    assert page.session.mode is state.RunMode.ACQUISITION
    assert not page._open_button.isVisible()


def test_setup_page_hides_dry_run_without_the_env_gate(qapp, config, monkeypatch):
    monkeypatch.delenv(state.DRY_RUN_ENV_VAR, raising=False)

    page = SetupPage(config)

    modes = [
        page._mode_selector.itemData(i) for i in range(page._mode_selector.count())
    ]
    assert modes == [state.RunMode.ACQUISITION]


def test_setup_page_offers_dry_run_when_gated_on(qapp, config, monkeypatch):
    monkeypatch.setenv(state.DRY_RUN_ENV_VAR, "1")

    page = SetupPage(config)

    modes = [
        page._mode_selector.itemData(i) for i in range(page._mode_selector.count())
    ]
    assert modes == [state.RunMode.ACQUISITION, state.RunMode.DRY_RUN]
    assert page.selected_mode() is state.RunMode.ACQUISITION


def test_setup_mode_ignores_the_mouse_wheel(qapp, config, monkeypatch):
    monkeypatch.setenv(state.DRY_RUN_ENV_VAR, "1")
    # Switching to dry run opens a modal confirmation; record it instead of
    # blocking, so a regression fails here rather than hanging the test run.
    prompts = []
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args, **kwargs: prompts.append(args) or QMessageBox.StandardButton.No,
    )
    page = SetupPage(config)

    wheel = QWheelEvent(
        QPointF(5, 5),
        QPointF(5, 5),
        QPoint(0, 0),
        QPoint(0, -120),  # scrolling down would select the next mode, dry run
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )
    QApplication.sendEvent(page._mode_selector, wheel)

    assert prompts == []
    assert page.selected_mode() is state.RunMode.ACQUISITION
    assert not wheel.isAccepted()  # left for the page's scroll area


def test_main_window_disables_later_pages_until_a_session_is_open(qapp, config):
    window = MainWindow(config)

    assert window._nav.item(1).flags() & _ENABLED
    assert not window._nav.item(3).flags() & _ENABLED


def test_main_window_enables_later_pages_once_a_session_opens(qapp, config):
    window = MainWindow(config)

    window._on_session_opened(
        state.SessionState(subject="abby", data_root=config.data_root)
    )

    assert window._nav.item(3).flags() & _ENABLED


def _nav_done(window):
    return [window._nav.item(row).toolTip() == "Complete" for row in range(5)]


def test_sidebar_marks_nothing_done_before_a_session(qapp, config):
    window = MainWindow(config)

    assert _nav_done(window) == [False] * 5
    assert window._nav.item(3).text() == "4  Battery"


def test_sidebar_marks_setup_done_and_counts_tasks_once_a_session_opens(
    qapp, config
):
    window = MainWindow(config)

    window._on_session_opened(
        state.SessionState(subject="abby", data_root=config.data_root)
    )

    assert _nav_done(window) == [True, False, False, False, False]
    assert window._nav.item(3).text().endswith("0/4")


def test_sidebar_clears_when_the_session_closes(qapp, config):
    window = MainWindow(config)
    window._on_session_opened(
        state.SessionState(subject="abby", data_root=config.data_root)
    )

    window._on_session_closed()

    assert _nav_done(window) == [False] * 5


def test_sidebar_updates_when_a_command_finishes(qapp, config):
    session = state.SessionState(subject="abby", data_root=config.data_root)
    window = MainWindow(config)
    window._on_session_opened(session)
    calibration = (
        session.sourcedata_root / "sub-abby" / "ses-01" / "calibrations"
        / "calibration-20260925T120000"
    )
    calibration.mkdir(parents=True)

    window._on_process_finished(0)  # e.g. a calibration command just exited

    assert _nav_done(window)[2]


def test_sidebar_never_disables_pages_it_marks_not_done(qapp, config):
    window = MainWindow(config)
    window._on_session_opened(
        state.SessionState(subject="abby", data_root=config.data_root)
    )

    for row in range(5):
        assert window._nav.item(row).flags() & _ENABLED


SETUP_NEXT, HARDWARE_NEXT, CALIBRATION_NEXT, BATTERY_NEXT = range(4)


def _next_enabled(window):
    return [button.isEnabled() for button in window._next_buttons]


def test_next_buttons_are_labelled_with_the_page_they_lead_to(qapp, config):
    window = MainWindow(config)

    assert [button.text() for button in window._next_buttons] == [
        "Next: Hardware  →",
        "Next: Calibration  →",
        "Next: Battery  →",
        "Next: Export  →",
    ]


def test_next_buttons_use_the_next_style(qapp, config):
    # The theme styles #Next: teal when clickable, locked-input grey when not.
    window = MainWindow(config)

    assert {button.objectName() for button in window._next_buttons} == {"Next"}


def test_theme_styles_next_buttons_in_both_states():
    from aria_et.gui.theme import PALETTE, stylesheet

    css = stylesheet()
    enabled = css.split("QPushButton#Next {", 1)[1].split("}", 1)[0]
    disabled = css.split("QPushButton#Next:disabled {", 1)[1].split("}", 1)[0]
    assert PALETTE["aria_teal"] in enabled
    assert PALETTE["surface_alt"] in disabled
    assert PALETTE["text_disabled"] in disabled


def test_next_buttons_start_greyed_out(qapp, config):
    window = MainWindow(config)

    assert _next_enabled(window) == [False] * 4


def test_setup_next_unlocks_once_a_session_opens_and_moves_to_hardware(
    qapp, config
):
    window = MainWindow(config)
    window._on_session_opened(
        state.SessionState(subject="abby", data_root=config.data_root)
    )

    assert _next_enabled(window) == [True, False, False, False]

    window._next_buttons[SETUP_NEXT].click()
    assert window._nav.currentRow() == 1
    assert window._pages.currentIndex() == 1


def test_hardware_next_respects_the_existing_session_gate(qapp, config):
    window = MainWindow(config)
    window._hardware_page._connected = True  # stand-in for a passed tracker check

    window._refresh_nav_progress()
    # Hardware is done, but Calibration stays locked until a session opens.
    assert not window._next_buttons[HARDWARE_NEXT].isEnabled()

    window._on_session_opened(
        state.SessionState(subject="abby", data_root=config.data_root)
    )
    assert window._next_buttons[HARDWARE_NEXT].isEnabled()


def test_next_is_only_a_shortcut_the_sidebar_still_reaches_every_page(
    qapp, config
):
    window = MainWindow(config)
    window._on_session_opened(
        state.SessionState(subject="abby", data_root=config.data_root)
    )
    assert not window._next_buttons[HARDWARE_NEXT].isEnabled()

    window._nav.setCurrentRow(2)  # Calibration, without a tracker check

    assert window._pages.currentIndex() == 2


def _window_after_a_successful_export(config):
    window = MainWindow(config)
    # Open through the Setup page, as the operator does.
    window._setup_page._subject_field.setText("abby")
    window._setup_page._open_session()
    window._export_page._export_succeeded = True  # stand-in for a clean export
    window._refresh_nav_progress()
    return window


def test_export_offers_close_session_instead_of_next(qapp, config):
    window = MainWindow(config)

    button = window._close_session_button
    assert button.text() == "Close session"
    assert button.objectName() == "Next"  # same teal/grey states as Next
    assert not button.isEnabled()


def test_close_session_unlocks_only_after_a_successful_export(qapp, config):
    window = MainWindow(config)
    window._on_session_opened(
        state.SessionState(subject="abby", data_root=config.data_root)
    )
    assert not window._close_session_button.isEnabled()

    window._export_page._export_succeeded = True
    window._refresh_nav_progress()

    assert window._close_session_button.isEnabled()


def test_close_session_ends_the_session_and_returns_to_setup(qapp, config):
    window = _window_after_a_successful_export(config)
    window._nav.setCurrentRow(4)

    window._close_session_button.click()

    assert window._session is None
    assert window._setup_page.session is None
    assert not window._setup_page._open_button.isHidden()
    assert window._nav.currentRow() == 0
    assert not window._close_session_button.isEnabled()


def test_close_session_is_greyed_out_while_a_command_runs(
    qapp, config, monkeypatch
):
    window = _window_after_a_successful_export(config)
    monkeypatch.setattr(window._process, "is_running", lambda: True)

    window._refresh_nav_progress()

    assert not window._close_session_button.isEnabled()


def test_main_window_shows_the_dry_run_banner(qapp, config):
    window = MainWindow(config)

    window._on_session_opened(
        state.SessionState(
            subject="abby", data_root=config.data_root, mode=state.RunMode.DRY_RUN
        )
    )

    assert window._mode_banner.isVisibleTo(window)
    assert "NO GAZE DATA" in window._mode_banner.text()


def test_main_window_hides_the_banner_in_acquisition_mode(qapp, config):
    window = MainWindow(config)

    window._on_session_opened(
        state.SessionState(subject="abby", data_root=config.data_root)
    )

    assert not window._mode_banner.isVisibleTo(window)


@pytest.mark.parametrize(
    "psychopy_screen, etm_screen, expected",
    [
        (1, 2, 2),  # lab defaults: both mean the second display
        (0, 1, 1),  # both on the primary display
        (1, 3, 3),  # ETM on the third display
        (2, 1, 3),  # stimulus on the third display
    ],
)
def test_required_display_count_uses_each_screen_numbering(
    tmp_path, psychopy_screen, etm_screen, expected
):
    config = AriaEtConfig(
        data_root=tmp_path, psychopy_screen=psychopy_screen, etm_screen=etm_screen
    )

    assert required_display_count(config) == expected


def _display_warning(page):
    return next(
        label
        for label in page.findChildren(QLabel)
        if "display(s) detected" in label.text()
    )


@pytest.mark.parametrize("screen_count, shown", [(1, True), (2, False)])
def test_setup_warns_only_when_the_default_screens_need_more_displays(
    qapp, config, screen_count, shown
):
    page = SetupPage(config, screen_count=screen_count)

    warning = _display_warning(page)
    assert warning.isHidden() is not shown
    assert "expects at least 2" in warning.text()
