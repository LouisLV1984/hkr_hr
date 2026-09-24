from datetime import timedelta, timezone


HONG_KONG_TIMEZONE = timezone(timedelta(hours=8), name="HKT")


def hong_kong_datetime(value):
    """Convert a stored UTC datetime to Hong Kong time.

    Existing database timestamps are naive UTC values. A timezone-aware value
    is also accepted so callers can use the same formatter consistently.
    """
    if value is None:
        return None
    utc_value = (
        value.replace(tzinfo=timezone.utc)
        if value.tzinfo is None
        else value
    )
    return utc_value.astimezone(HONG_KONG_TIMEZONE)
