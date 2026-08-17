from opencc import OpenCC


_TO_SIMPLIFIED = OpenCC("t2s")
_TO_TRADITIONAL = OpenCC("s2t")


def chinese_search_variants(value):
    """Return original, Simplified Chinese and Traditional Chinese variants."""
    text = (value or "").strip()
    if not text:
        return []
    return sorted(
        {
            text,
            _TO_SIMPLIFIED.convert(text),
            _TO_TRADITIONAL.convert(text),
        }
    )
