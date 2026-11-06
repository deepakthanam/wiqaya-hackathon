"""Small-cell suppression (PROMPT.md §7): any cell whose denominator is < min_n is replaced.

Every API response that returns aggregates passes through `suppress` or `suppress_records`.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

SUPPRESSED = "suppressed (n<11)"
DEFAULT_MIN_N = 11


def suppress(df: pd.DataFrame, min_n: int = DEFAULT_MIN_N, denominator: str = "n",
             value_columns: list[str] | None = None) -> pd.DataFrame:  # fmt: skip
    """Replace value cells in rows whose denominator < min_n. The denominator itself is also masked."""
    if df.empty:
        return df.copy()
    out = df.copy().astype(object)
    cols = value_columns or [c for c in out.columns if c != denominator and pd.api.types.is_numeric_dtype(df[c])]
    small = df[denominator].fillna(0).astype(float) < min_n
    for c in [*cols, denominator]:
        out.loc[small, c] = SUPPRESSED
    out["suppressed"] = small.to_numpy()
    return out


def suppress_records(
    rows: list[dict[str, Any]], min_n: int = DEFAULT_MIN_N, denominator: str = "n"
) -> list[dict[str, Any]]:
    """Record-list variant used by API endpoints."""
    out = []
    for r in rows:
        n = r.get(denominator)
        if n is not None and not isinstance(n, str) and float(n) < min_n:
            masked = {
                k: (SUPPRESSED if isinstance(v, (int, float)) and not isinstance(v, bool) else v) for k, v in r.items()
            }
            masked["suppressed"] = True
            out.append(masked)
        else:
            out.append({**r, "suppressed": False})
    return out


def is_suppression_safe(rows: list[dict[str, Any]], min_n: int = DEFAULT_MIN_N, denominator: str = "n") -> bool:
    """True if no numeric value is exposed for a row whose denominator is below min_n."""
    for r in rows:
        n = r.get(denominator)
        if isinstance(n, (int, float)) and not isinstance(n, bool) and n < min_n:
            return False
    return True
