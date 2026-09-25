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
