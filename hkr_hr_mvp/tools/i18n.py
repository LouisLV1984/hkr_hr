"""Transitional compatibility shim; translations now live in ``hkr_hr/*/words.py``."""
from hkr_hr.app.words import (
    EN,
    LANGUAGE_OPTIONS,
    OPTION_TRANSLATION_KEYS,
    SYSTEM_MESSAGE_TRANSLATION_KEYS,
    TRANSLATIONS,
    ZH_HANS,
    ZH_HANT,
    normalize_language,
    translate_system_message,
)

__all__ = [
    "EN",
    "LANGUAGE_OPTIONS",
    "OPTION_TRANSLATION_KEYS",
    "SYSTEM_MESSAGE_TRANSLATION_KEYS",
    "TRANSLATIONS",
    "ZH_HANS",
    "ZH_HANT",
    "normalize_language",
    "translate_system_message",
]
