import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from aria_et.config import AriaEtConfig
from aria_et.gui import state
from aria_et.gui.main_window import MainWindow
from aria_et.gui.pages.setup import SetupPage

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
