from typing import Union


def validate_quality_value(
    val: Union[int, float, str], default: int = 80
) -> int:
    """
    Validates and clamps quality value strictly between 1 and 100.
    Returns 'default' if input parsing fails.
    """
    try:
        q = int(float(val))
        return max(1, min(100, q))
    except (ValueError, TypeError):
        return default