"""BIDS entity label validation for GUI form fields."""

from __future__ import annotations

import re

SUBJECT_PREFIX = "sub-"
SESSION_PREFIX = "ses-"
RUN_PREFIX = "run-"

BIDS_LABEL_PATTERN = re.compile(r"^[A-Za-z0-9]+$")
_INVALID_LABEL_CHARACTERS = re.compile(r"[^A-Za-z0-9]+")


def strip_entity_prefix(value: str, prefix: str) -> str:
    return value.strip().removeprefix(prefix)


def normalize_subject(value: str) -> str:
    return strip_entity_prefix(value, SUBJECT_PREFIX)


def normalize_session(value: str) -> str:
    return strip_entity_prefix(value, SESSION_PREFIX)


def is_valid_label(value: str) -> bool:
    return bool(BIDS_LABEL_PATTERN.match(value))


def suggest_label(value: str) -> str:
    return _INVALID_LABEL_CHARACTERS.sub("", value.strip())


def label_error(value: str, field_name: str) -> str | None:
    if not value:
        return f"{field_name} is required."
    if is_valid_label(value):
        return None
    suggestion = suggest_label(value)
    message = f"{field_name} may only contain letters and digits."
    if suggestion:
        message += f' Try "{suggestion}".'
    return message
