"""Assembles every module's trilingual word catalogue into platform.i18n."""
from __future__ import annotations

from hkr_hr.attendance.words import WORDS as ATTENDANCE_WORDS
from hkr_hr.documents.words import WORDS as DOCUMENTS_WORDS
from hkr_hr.employees.words import WORDS as EMPLOYEES_WORDS
from hkr_hr.leave.words import WORDS as LEAVE_WORDS
from hkr_hr.payroll.words import WORDS as PAYROLL_WORDS
from hkr_hr.platform.i18n import (
    EN,
    LANGUAGE_OPTIONS,
    OPTION_TRANSLATION_KEYS,
    SYSTEM_MESSAGE_TRANSLATION_KEYS,
    TRANSLATIONS,
    ZH_HANS,
    ZH_HANT,
    normalize_language,
    register_words,
    translate_system_message,
)
from hkr_hr.platform.words import WORDS as PLATFORM_WORDS
from hkr_hr.references.words import WORDS as REFERENCES_WORDS
from hkr_hr.workbench.words import WORDS as WORKBENCH_WORDS

_ALL_CATALOGUES = (
    PLATFORM_WORDS,
    REFERENCES_WORDS,
    DOCUMENTS_WORDS,
    EMPLOYEES_WORDS,
    LEAVE_WORDS,
    ATTENDANCE_WORDS,
    PAYROLL_WORDS,
    WORKBENCH_WORDS,
)

_CONFIGURED = False


def configure_words() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    for catalogue in _ALL_CATALOGUES:
        register_words(catalogue)
    _CONFIGURED = True


configure_words()

__all__ = [
    "EN",
    "LANGUAGE_OPTIONS",
    "OPTION_TRANSLATION_KEYS",
    "SYSTEM_MESSAGE_TRANSLATION_KEYS",
    "TRANSLATIONS",
    "ZH_HANS",
    "ZH_HANT",
    "configure_words",
    "normalize_language",
    "translate_system_message",
]
