"""Run the lap flags on real races and check the SC/VSC/red rule against actual pace."""

import pandas as pd

from pitwall.cleaning import FLAG_COLUMNS, flag_laps, neutralised_periods
from pitwall.openf1 import (
    find_race_session,
    load_laps,
    load_pits,
    load_race_control,
    load_weather,
)

YEAR = 2024
RACES = [
    "Bahrain",
    "Saudi Arabia",
    "Australia",
    "Japan",
    "China",
    "Monaco",
    "Canada",
    "Spain",
    "Brazil",
]
THRESHOLDS = [1.0, 1.5, 2.0]
SLOW_RATIO = 1.15  # 15% off a driver's normal pace is unmistakably not racing


def pace_ratio(flagged: pd.DataFrame) -> pd.Series:
    # is_wet stays in the reference, otherwise an all-wet race has no normal laps at all.
    rules = [column for column in FLAG_COLUMNS if column != "is_wet"]
    normal = flagged[~flagged[rules].any(axis=1)]
    reference = normal.groupby("DriverNumber")["LapTimeSeconds"].median()
    return flagged["LapTimeSeconds"] / flagged["DriverNumber"].map(reference)


def report(country: str) -> dict:
    session_key = find_race_session(YEAR, country)
    laps, pits = load_laps(session_key), load_pits(session_key)
    race_control, weather = load_race_control(session_key), load_weather(session_key)
    flagged = flag_laps(laps, race_control, weather)
    assert len(flagged) == len(laps)

    flagged["ratio"] = pace_ratio(flagged)
    print(f"\n=== {country}: {len(flagged)} laps")
    periods = neutralised_periods(race_control, flagged["LapStart"].max())
    print("periods:", [(a.strftime("%H:%M:%S"), b.strftime("%H:%M:%S")) for a, b in periods])

    neutral = flagged[flagged["is_sc_vsc_red"]]
    by_lap = flagged.groupby("LapNumber").agg(
        flagged=("is_sc_vsc_red", "sum"), median_ratio=("ratio", "median")
    )
    if not neutral.empty:
        print(by_lap[by_lap["flagged"] > 0].round(3).T.to_string())

    other_rules = ["is_lap1", "is_inlap", "is_outlap", "is_sc_vsc_red"]
    unexplained = ~flagged[[*other_rules, "is_wet"]].any(axis=1)
    missed = flagged[(flagged["ratio"] > SLOW_RATIO) & unexplained]
    print(f"slow by >15% but not lap1/pit/neutralised/wet: {len(missed)}")
    if not missed.empty:
        columns = ["Driver", "LapNumber", "LapTimeSeconds", "ratio", "is_wet", "is_slow_outlier"]
        print(missed[columns].head(10).round(3).to_string(index=False))

    under = flagged.set_index(["DriverNumber", "LapNumber"])["is_sc_vsc_red"]
    keys = pd.MultiIndex.from_arrays([pits["driver_number"], pits["lap_number"]])
    pit_flags = under.reindex(keys, fill_value=False)
    print(f"pit rows: {len(pits)} kept, {int(pit_flags.sum())} under SC/VSC/red")

    row = {"Race": country, "Laps": len(flagged)}
    row |= {column: int(flagged[column].sum()) for column in FLAG_COLUMNS}
    row["Any flag"] = int(flagged[FLAG_COLUMNS].any(axis=1).sum())
    for threshold in THRESHOLDS:
        counts = flag_laps(laps, race_control, weather, slow_threshold=threshold)
        row[f"slow>{threshold}"] = int(counts["is_slow_outlier"].sum())
    return row


def main() -> None:
    pd.set_option("display.width", 220, "display.max_columns", 60)
    summary = pd.DataFrame([report(country) for country in RACES])
    print("\n", summary.to_string(index=False))


if __name__ == "__main__":
    main()
