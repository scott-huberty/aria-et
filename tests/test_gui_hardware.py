import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from aria_et.config import AriaEtConfig, set_config
from aria_et.gui.pages.hardware import NO_SAVED_TRACKER_TEXT, HardwarePage

pytestmark = pytest.mark.qt_gui

TRACKER_LINE = (
    "1. Tobii Pro Spectrum model=Tobii Pro Spectrum serial={serial} "
    "address={address} firmware=2.6.2-orbicularis-0"
)


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


def _discover(page, *trackers):
    page._request_check()
    page.record_output_line("Tobii Pro SDK 2.1.0.1 is available.")
    for index, (serial, address) in enumerate(trackers, start=1):
        line = TRACKER_LINE.format(serial=serial, address=address)
        page.record_output_line(line.replace("1.", f"{index}.", 1))
    page.report_exit(0)


def test_hardware_page_asks_to_save_when_no_tracker_is_configured(qapp, tmp_path):
    page = HardwarePage(AriaEtConfig(data_root=tmp_path))

    assert page._saved_tracker.text() == NO_SAVED_TRACKER_TEXT
    assert page._address_field.text() == ""
    assert page.tracker_address() is None


def test_hardware_page_prefills_saved_tracker(qapp, tmp_path):
    config = AriaEtConfig(
        data_root=tmp_path,
        tracker_address="tobii-prp://169.254.10.180",
        tracker_serial_number="TPSP1-010214213025",
    )

    page = HardwarePage(config)

    assert "TPSP1-010214213025" in page._saved_tracker.text()
    assert page._address_field.text() == "tobii-prp://169.254.10.180"
    # The CLI already defaults to the saved tracker, so no override is sent.
    assert page.tracker_address() is None


def test_hardware_page_saves_the_single_discovered_tracker(qapp, tmp_path):
    page = HardwarePage(AriaEtConfig(data_root=tmp_path))
    requests = []
    page.save_requested.connect(requests.append)

    _discover(page, ("TPSP1-010214213025", "tobii-prp://169.254.10.180"))

    assert page._table.item(0, 4).text() == "2.6.2-orbicularis-0"
    assert page._save_button.isEnabled()
    page._save_button.click()
    assert requests == [
        ["find-eyetracker", "--save", "--serial-number", "TPSP1-010214213025"]
    ]

    # Simulate the CLI having written the config, then report success.
    set_config("tobii.address", "tobii-prp://169.254.10.180")
    set_config("tobii.serial_number", "TPSP1-010214213025")
    page.report_save_exit(0)

    assert "TPSP1-010214213025" in page._saved_tracker.text()
    assert not page._save_button.isEnabled()


def test_hardware_page_needs_a_selection_when_several_trackers_are_found(
    qapp, tmp_path
):
    page = HardwarePage(AriaEtConfig(data_root=tmp_path))
    requests = []
    page.save_requested.connect(requests.append)

    _discover(
        page,
        ("SN1", "tobii-prp://169.254.10.180"),
        ("SN2", "tobii-prp://169.254.10.181"),
    )

    assert not page._save_button.isEnabled()
    page._table.selectRow(1)
    assert page._save_button.isEnabled()
    page._save_button.click()
    assert requests == [["find-eyetracker", "--save", "--serial-number", "SN2"]]
