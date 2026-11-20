"""Pure corporate hierarchy sorting and display-name normalization rules."""
from __future__ import annotations

from datetime import datetime
import re
import unicodedata


DEFAULT_DEPARTMENT_ORDER = {
    "MANAGEMENT": 10,
    "管理層": 10,
    "管理层": 10,
    "ENGINEERING": 20,
    "工程管理部": 20,
    "COMMERCIAL": 30,
    "成本合約部": 30,
    "成本合约部": 30,
    "船機設備部": 40,
    "船机设备部": 40,
    "FINANCE": 50,
    "財務部": 50,
    "财务部": 50,
    "HR": 60,
    "人事行政部": 60,
    "SITE": 70,
    "地盤": 70,
    "地盘": 70,
    "印尼瑞沃": 80,
}


def normalize_reference_display(value):
    text = unicodedata.normalize("NFKC", str(value or "")).strip()
    return re.sub(r"\s+", " ", text)


def slug_code(value):
    text = unicodedata.normalize("NFKD", str(value or "")).encode(
        "ascii",
        "ignore",
    ).decode("ascii")
    text = re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_").upper()
    return text[:80] or f"VALUE_{datetime.utcnow():%H%M%S%f}"


def reference_sort_order(list_code, value):
    """Return custom sort_order, corporate department default, or 500."""
    if value is None:
        return 9999
    meta = value.metadata_json if isinstance(value.metadata_json, dict) else {}
    raw_custom = meta.get("sort_order")
    if raw_custom is not None and not isinstance(raw_custom, bool):
        try:
            return int(raw_custom)
        except (TypeError, ValueError):
            pass
    if list_code == "department":
        code_key = (value.code or "").strip().upper()
        name_key = (value.display_name or "").strip()
        if code_key in DEFAULT_DEPARTMENT_ORDER:
            return DEFAULT_DEPARTMENT_ORDER[code_key]
        if name_key in DEFAULT_DEPARTMENT_ORDER:
            return DEFAULT_DEPARTMENT_ORDER[name_key]
    return 500


def reference_sort_key(list_code, value):
    """Sort reference values by sort_order then case-insensitive display_name."""
    if value is None:
        return (1, 9999, "")
    return (0, reference_sort_order(list_code, value), (value.display_name or "").casefold())
