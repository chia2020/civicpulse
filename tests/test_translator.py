from src.core.translator import TRANSLATIONS, translate_text
import pytest


def test_ui_translations_contain_required_keys() -> None:
    en_keys = set(TRANSLATIONS["en"].keys())
    te_keys = set(TRANSLATIONS["te"].keys())

    assert "title" in en_keys
    assert "active_issues" in en_keys
    assert "critical_priority" in en_keys
    assert "zones_affected" in en_keys
    assert "resolved_30d" in en_keys
    assert en_keys == te_keys


def test_translate_text_returns_same_if_empty() -> None:
    assert translate_text("", "te") == ""
    assert translate_text("   ", "te") == "   "
    assert translate_text(None, "te") is None


def test_translate_text_invalid_lang_returns_original() -> None:
    text = "Clogged drain near Koti"
    assert translate_text(text, "fr") == text
