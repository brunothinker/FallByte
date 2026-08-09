def validate_quality_value(val: int | float | str, default: int = 80) -> int:
    """
    Validates and clamps quality value between 1 and 100.
    Returns 'default' if the provided value is invalid.
    """
    try:
        q = int(float(val))
        return max(1, min(100, q))
    except (ValueError, TypeError):
        return default