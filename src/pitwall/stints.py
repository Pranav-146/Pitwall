"""Stint boundaries, checked stop by stop against the pit table.

OpenF1 `stints` ends a stint one lap before the pit stop in some races, while `pit` agrees
with Jolpica. That one pattern is corrected here. Anything else is reported, not patched.
"""

from typing import NamedTuple

import pandas as pd


class StintRepair(NamedTuple):
    stints: pd.DataFrame
    corrections: list[dict]
    problems: list[str]


def snap_stints_to_pits(stints: pd.DataFrame, pits: pd.DataFrame) -> StintRepair:
    """Move stint boundaries that sit exactly one lap before their pit stop."""
    repaired = stints.sort_values(["driver_number", "stint_number"], ignore_index=True)
    corrections, problems = [], []

    for number, group in repaired.groupby("driver_number"):
        stops = sorted(pits.loc[pits["driver_number"] == number, "lap_number"].unique().tolist())
        boundaries = group.index[:-1]
        ends = group["lap_end"].iloc[:-1].tolist()
        gaps = [stop - end for stop, end in zip(stops, ends)]
        if len(stops) != len(boundaries) or any(gap not in (0, 1) for gap in gaps):
            problems.append(f"car {number}: stint ends {ends} but pit stops {stops}")
            continue
        for row, stop, gap in zip(boundaries, stops, gaps):
            if gap == 1:
                corrections.append(
                    {
                        "driver_number": int(number),
                        "stint_number": int(repaired.at[row, "stint_number"]),
                        "old_lap_end": int(repaired.at[row, "lap_end"]),
                        "new_lap_end": int(stop),
                    }
                )
            repaired.at[row, "lap_end"] = stop
            repaired.at[row + 1, "lap_start"] = stop + 1

    return StintRepair(repaired, corrections, problems)
