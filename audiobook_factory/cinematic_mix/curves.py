#!/usr/bin/env python3
"""
Audiobook Factory - Stage 11: Cinematic Mix v2.
Module: curves.py
Provides deterministic interpolation curves and curve evaluation for mix automation.
Supports: linear, ease_in, ease_out, and smooth (cubic Hermite / S-curve).
"""

from __future__ import annotations
import math
from typing import Literal, Union, get_args

CurveType = Literal["linear", "ease_in", "ease_out", "smooth"]
ALLOWED_CURVES = set(get_args(CurveType))
SUPPORTED_CURVES = ALLOWED_CURVES


def evaluate_curve(
    start: float,
    end: float,
    start_value: float,
    end_value: float,
    curve: Union[CurveType, float],
    t: Union[float, CurveType],
) -> float:
    """
    Deterministically evaluates an automation curve at timestamp t.

    Parameters:
        start: Start timestamp in seconds.
        end: End timestamp in seconds (must be strictly > start).
        start_value: Value at start timestamp.
        end_value: Value at end timestamp.
        curve: Interpolation mode ('linear', 'ease_in', 'ease_out', 'smooth').
        t: Current timestamp in seconds.

    Returns:
        Interpolated float value at time t.

    Raises:
        ValueError: If end <= start or curve is not recognized.
    """
    # Allow flexible ordering if caller provided (start, end, s_val, e_val, t, curve)
    if isinstance(curve, (int, float)) and isinstance(t, str):
        t_val = float(curve)
        c_val = str(t)
    else:
        t_val = float(t)
        c_val = str(curve)
    if end <= start:
        raise ValueError(
            f"Zero or negative duration rejected: end ({end}s) must be strictly greater than start ({start}s)"
        )

    curve_norm = str(c_val).strip().lower()
    if curve_norm not in ALLOWED_CURVES:
        raise ValueError(
            f"Invalid curve '{c_val}'. Must be one of: {sorted(ALLOWED_CURVES)}"
        )

    # Out of range clamping
    if t_val <= start:
        return float(start_value)
    if t_val >= end:
        return float(end_value)

    # Normalized progression p in (0.0, 1.0)
    p = (t_val - start) / (end - start)

    if curve_norm == "linear":
        factor = p
    elif curve_norm == "ease_in":
        # Quadratic ease-in: starts slow, accelerates
        factor = p * p
    elif curve_norm == "ease_out":
        # Quadratic ease-out: starts fast, decelerates
        factor = 1.0 - (1.0 - p) * (1.0 - p)
    elif curve_norm == "smooth":
        # Cubic Hermite smoothstep (0 first derivative at endpoints)
        factor = p * p * (3.0 - 2.0 * p)
    else:
        factor = p

    return round(start_value + factor * (end_value - start_value), 6)


def generate_curve_points(
    start: float,
    end: float,
    start_value: float,
    end_value: float,
    curve: CurveType,
    num_points: int = 11,
) -> list[tuple[float, float]]:
    """
    Generates deterministic (time, value) sample points along an automation curve.
    Useful for piecewise filter graph rendering and testing.
    """
    if num_points < 2:
        raise ValueError(f"num_points must be at least 2, got {num_points}")
    if end <= start:
        raise ValueError(f"end ({end}) must be strictly greater than start ({start})")

    step = (end - start) / (num_points - 1)
    points = []
    for i in range(num_points):
        t = start + i * step
        if i == num_points - 1:
            t = end
        v = evaluate_curve(start, end, start_value, end_value, curve, t)
        points.append((round(t, 4), v))
    return points
