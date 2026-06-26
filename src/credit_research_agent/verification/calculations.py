"""Deterministic calculations for numeric claim verification."""

from __future__ import annotations


def calculate_change(old_value: float, new_value: float) -> float:
    """Return the arithmetic change from old to new."""

    return new_value - old_value


def calculate_percentage_change(old_value: float, new_value: float) -> float | None:
    """Return percentage change rounded to two decimals, or None for zero base."""

    if old_value == 0:
        return None
    return round(((new_value - old_value) / old_value) * 100, 2)


def direction(old_value: float, new_value: float) -> str:
    """Classify direction of movement."""

    if new_value > old_value:
        return "increase"
    if new_value < old_value:
        return "decrease"
    return "no_change"
