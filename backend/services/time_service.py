from datetime import datetime, timezone


def get_now_utc() -> datetime:
    """
    Canonical time injection point.
    All production code calls this, never datetime.now() directly.
    """
    return datetime.now(timezone.utc)