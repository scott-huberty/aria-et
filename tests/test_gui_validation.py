from aria_et.gui import validation


def test_normalize_subject_strips_prefix_and_whitespace():
    assert validation.normalize_subject("  sub-abby ") == "abby"


def test_normalize_session_strips_prefix():
    assert validation.normalize_session("ses-01") == "01"


def test_is_valid_label_accepts_alphanumeric_only():
    assert validation.is_valid_label("abby01")
    assert not validation.is_valid_label("flush-test")
    assert not validation.is_valid_label("")


def test_suggest_label_removes_invalid_characters():
    assert validation.suggest_label("flush-test") == "flushtest"
    assert validation.suggest_label("sub_01 a") == "sub01a"


def test_label_error_reports_missing_value():
    assert validation.label_error("", "Subject") == "Subject is required."


def test_label_error_includes_suggestion():
    message = validation.label_error("flush-test", "Subject")
    assert message is not None
    assert "flushtest" in message


def test_label_error_is_none_for_valid_label():
    assert validation.label_error("abby", "Subject") is None
