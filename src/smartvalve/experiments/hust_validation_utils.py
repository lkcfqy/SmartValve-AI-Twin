"""Small comparison helpers used only by post-outcome HUST validators."""

from __future__ import annotations

import math
from numbers import Real


def assert_findings_equal(
    recomputed: dict[str, object],
    saved: dict[str, object],
    *,
    absolute_tolerance: float = 1e-12,
) -> float:
    """Allow serialization-scale float drift while keeping structure exact.

    Producers compute findings from in-memory values, whereas independent validators
    recompute them from 12-significant-digit CSV artifacts. Exact dictionary equality
    therefore rejects harmless sub-picounit rounding and also rejects two IEEE NaNs.
    Booleans and non-numeric values remain exact.
    """

    if set(recomputed) != set(saved):
        raise ValueError("HUST size-matched finding keys do not reproduce")
    maximum_difference = 0.0
    for key in sorted(recomputed):
        left = recomputed[key]
        right = saved[key]
        if isinstance(left, bool) or isinstance(right, bool):
            if type(left) is not bool or type(right) is not bool or left != right:
                raise ValueError(f"HUST size-matched boolean finding changed: {key}")
            continue
        if isinstance(left, Real) and isinstance(right, Real):
            left_value = float(left)
            right_value = float(right)
            if math.isnan(left_value) or math.isnan(right_value):
                if not (math.isnan(left_value) and math.isnan(right_value)):
                    raise ValueError(f"HUST size-matched NaN finding changed: {key}")
                continue
            difference = abs(left_value - right_value)
            maximum_difference = max(maximum_difference, difference)
            if difference > absolute_tolerance:
                raise ValueError(
                    f"HUST size-matched numeric finding changed: {key}; "
                    f"difference={difference}"
                )
            continue
        if left != right:
            raise ValueError(f"HUST size-matched finding changed: {key}")
    return maximum_difference
