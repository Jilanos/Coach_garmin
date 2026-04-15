from __future__ import annotations

from collections.abc import Mapping
import unicodedata
from typing import Any


_MOJIBAKE_MARKERS = ("Ã", "Â", "â", "�")


def repair_mojibake_text(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    text = value.lstrip("\ufeff")
    if not any(marker in text for marker in _MOJIBAKE_MARKERS):
        return unicodedata.normalize("NFC", text)
    try:
        repaired = text.encode("latin1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        repaired = text
    return unicodedata.normalize("NFC", repaired)


def repair_text_tree(value: Any) -> Any:
    if isinstance(value, str):
        return repair_mojibake_text(value)
    if isinstance(value, Mapping):
        return {repair_text_tree(key): repair_text_tree(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return tuple(repair_text_tree(item) for item in value)
    if isinstance(value, list):
        return [repair_text_tree(item) for item in value]
    if isinstance(value, set):
        return {repair_text_tree(item) for item in value}
    return value
