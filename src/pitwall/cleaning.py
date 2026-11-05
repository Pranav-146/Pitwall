"""Flag laps that do not reflect normal racing pace. Nothing is ever dropped.

Each rule gets its own boolean column, so every model chooses what to exclude. Race
control and weather are matched to laps by time, not lap number: race control lap
numbers follow the leader, so they are wrong for lapped cars.
"""

import pandas as pd

FLAG_COLUMNS = [
    "is_lap1",
    "is_inlap",
    "is_outlap",
    "is_sc_vsc_red",
    "is_slow_outlier",
    "is_blue_flag",
    "is_wet",
]
WET_COMPOUNDS = {"INTERMEDIATE", "WET"}
SLOW_THRESHOLD_SECONDS = 1.5
ROLLING_WINDOW_LAPS = 5


def lap_intervals(laps: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    """Start and end time of each lap, filling the gaps OpenF1 leaves.

    Laps must be sorted by driver and lap number.
    """
    by_driver = laps.groupby("DriverNumber")["LapStart"]
    duration = pd.to_timedelta(laps["LapTimeSeconds"], unit="s")
    typical = pd.to_timedelta(laps["LapTimeSeconds"].median(), unit="s")

    end = by_driver.shift(-1).fillna(laps["LapStart"] + duration)
    end = end.fillna(laps["LapStart"] + typical)
    start = laps["LapStart"].fillna(end.groupby(laps["DriverNumber"]).shift(1))
    start = start.where(laps["LapNumber"] != 1, start.fillna(laps["LapStart"].min()))
    return start, end.fillna(start + typical)


def neutralised_periods(
    race_control: pd.DataFrame, race_end: pd.Timestamp
) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    """Time spans under SC, VSC or red flag. A VSC that becomes an SC is one span."""
    periods, opened, red = [], None, False
    for row in race_control.sort_values("date", kind="stable").itertuples():
        message = row.message
        is_red = row.flag == "RED"  # exact match: CHEQUERED contains "RED"
        if is_red or message in ("SAFETY CAR DEPLOYED", "VIRTUAL SAFETY CAR DEPLOYED"):
            opened = row.date if opened is None else opened
            red = red or is_red
        elif opened is not None:
            sc_over = message in ("SAFETY CAR IN THIS LAP", "VIRTUAL SAFETY CAR ENDING")
            if (sc_over and not red) or (red and message == "SESSION STARTED"):
                periods.append((opened, row.date))
                opened, red = None, False
    if opened is not None:  # the race finished under neutralisation
        periods.append((opened, race_end))
    return periods


def _during(times: pd.Series, start: pd.Series, end: pd.Series) -> pd.Series:
    """True for laps whose [start, end) contains at least one of the given times."""
    ordered = times.sort_values().to_numpy()
    first = ordered.searchsorted(start.to_numpy(), side="left")
    last = ordered.searchsorted(end.to_numpy(), side="left")
    return pd.Series(last > first, index=start.index)


def _slow_outliers(laps: pd.DataFrame, threshold: float) -> pd.Series:
    """Laps slower than the rolling median of their own stint by more than threshold."""
    excluded = laps[["is_lap1", "is_inlap", "is_outlap", "is_sc_vsc_red"]].any(axis=1)
    racing = laps[~excluded & laps["LapTimeSeconds"].notna()]
    median = racing.groupby(["DriverNumber", "Stint"])["LapTimeSeconds"].transform(
        lambda times: times.rolling(ROLLING_WINDOW_LAPS, center=True, min_periods=3).median()
    )
    slow = racing["LapTimeSeconds"] - median > threshold
    return slow.reindex(laps.index, fill_value=False)


def flag_laps(
    laps: pd.DataFrame,
    race_control: pd.DataFrame,
    weather: pd.DataFrame,
    slow_threshold: float = SLOW_THRESHOLD_SECONDS,
) -> pd.DataFrame:
    """Return laps plus one boolean column per rule, with every input row kept."""
    flagged = laps.sort_values(["DriverNumber", "LapNumber"], ignore_index=True)
    start, end = lap_intervals(flagged)

    flagged["is_lap1"] = flagged["LapNumber"] == 1
    flagged["is_inlap"] = flagged["PitIn"]
    # OpenF1 marks lap 1 as a pit-out lap for every car in some races, Canada 2024 included.
    flagged["is_outlap"] = flagged["PitOut"] & ~flagged["is_lap1"]

    neutralised = pd.Series(False, index=flagged.index)
    for period_start, period_end in neutralised_periods(race_control, end.max()):
        neutralised |= (start < period_end) & (end > period_start)
    lap_after = neutralised.groupby(flagged["DriverNumber"]).shift(1, fill_value=False)
    flagged["is_sc_vsc_red"] = neutralised | lap_after

    flagged["is_slow_outlier"] = _slow_outliers(flagged, slow_threshold)

    blue = race_control[(race_control["flag"] == "BLUE") & race_control["driver_number"].notna()]
    flagged["is_blue_flag"] = False
    for number, messages in blue.groupby("driver_number"):
        rows = flagged["DriverNumber"] == number
        flagged.loc[rows, "is_blue_flag"] = _during(messages["date"], start[rows], end[rows])

    rain = weather.loc[weather["rainfall"] > 0, "date"]
    flagged["is_wet"] = flagged["Compound"].isin(WET_COMPOUNDS) | _during(rain, start, end)
    return flagged
