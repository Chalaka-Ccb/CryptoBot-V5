from math import isfinite


def finite_number(name: str, value: float, *, positive: bool = False) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a finite number")
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError(f"{name} must be a finite number") from error
    if not isfinite(result) or (positive and result <= 0):
        raise ValueError(f"{name} must be finite" + (" and greater than 0" if positive else ""))
    return result
