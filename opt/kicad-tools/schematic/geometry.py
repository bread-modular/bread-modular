"""Exact orthogonal wire geometry, not a symbol or connectivity engine."""
from decimal import Decimal, InvalidOperation
import math


def decimal(value):
    if type(value) not in (int, float, str):
        raise ValueError("Coordinates must be finite numbers, never booleans")
    try:
        result = Decimal(str(value))
    except InvalidOperation as error:
        raise ValueError("Invalid coordinate") from error
    if not result.is_finite() or abs(result) > 1000:
        raise ValueError("Coordinates must be finite and within +/-1000 mm")
    return result


def point(values, grid=None, json_input=False):
    if not isinstance(values, (list, tuple)) or len(values) != 2:
        raise ValueError("Expected [x_mm, y_mm]")
    if json_input and any(type(v) not in (int, float) for v in values):
        raise ValueError("JSON coordinates must be numbers")
    result = tuple(decimal(v) for v in values)
    if grid and any(v % grid for v in result):
        raise ValueError("Off-grid coordinate; choose explicit grid_mm and exact multiples")
    return result


def number(value):
    return format(value.normalize(), "f") if value else "0"


def xy(p):
    return " ".join(number(v) for v in p)


def public(p):
    return [float(v) for v in p]


def segment(a, b):
    if a == b or (a[0] != b[0] and a[1] != b[1]):
        raise ValueError("Only nonzero orthogonal wire segments are supported")
    return (a, b)


def contains(s, p):
    a, b = s
    return (a[0] == b[0] == p[0] and min(a[1], b[1]) <= p[1] <= max(a[1], b[1]) or
            a[1] == b[1] == p[1] and min(a[0], b[0]) <= p[0] <= max(a[0], b[0]))


def intersection(first, second):
    """None, one exact point, or a rejected collinear overlap."""
    a, b = first
    c, d = second
    vertical = a[0] == b[0]
    if vertical == (c[0] == d[0]):
        fixed, varying = (0, 1) if vertical else (1, 0)
        if a[fixed] != c[fixed]:
            return None
        low = max(min(a[varying], b[varying]), min(c[varying], d[varying]))
        high = min(max(a[varying], b[varying]), max(c[varying], d[varying]))
        if low > high:
            return None
        if low < high:
            raise ValueError("Collinear overlapping/duplicate wires are not supported")
        return (a[0], low) if vertical else (low, a[1])
    p = (a[0], c[1]) if vertical else (c[0], a[1])
    return p if contains(first, p) and contains(second, p) else None


def validate(segments, junctions, no_joins, labels, no_connects):
    # Bound quadratic work. Native KiCad, not this function, owns pin/net semantics.
    if len(segments) > 1024:
        raise ValueError("At most 1024 total wire segments supported")
    required = set()
    for i, first in enumerate(segments):
        for second in segments[i + 1:]:
            p = intersection(first, second)
            if p is None or p in first and p in second:
                continue  # shared endpoints connect naturally
            if p in junctions:
                continue
            if p not in no_joins:
                raise ValueError(f"Ambiguous wire crossing/T-join at {public(p)}; add_junction or explicit no_join required")
            if p in first or p in second:
                raise ValueError("no_join requires interior/interior crossing, never a T-join")
            required.add(p)
    if set(no_joins) != required:
        raise ValueError("Unused/conflicting no_join declaration (junction/shared endpoint/non-crossing)")
    if set(no_joins) & (set(junctions) | set(labels)):
        raise ValueError("Labels/junctions cannot sit at a no_join crossing")
    for p in junctions:
        arms = set()
        for a, b in segments:
            if contains((a, b), p):
                for end in (a, b):
                    if end != p:
                        arms.add((int(math.copysign(1, end[0] - p[0])) if end[0] != p[0] else 0,
                                  int(math.copysign(1, end[1] - p[1])) if end[1] != p[1] else 0))
        if len(arms) < 3:
            raise ValueError("Junction requires at least three wire arms")
    for p in no_connects:
        if any(contains(s, p) for s in segments) or p in labels:
            raise ValueError("Wire/label conflicts with a no_connect marker")
