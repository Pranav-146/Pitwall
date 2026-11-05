"""Audit every race before it can reach a model.

A race must pass independent checks against Jolpica. Failing races are quarantined with a
reason and never patched: the only correction allowed is the one in `pitwall.stints`.
"""

from dataclasses import dataclass, field

import pandas as pd

from pitwall.cleaning import FLAG_COLUMNS, WET_COMPOUNDS, flag_laps
from pitwall.openf1 import (
    MissingTable,
    load_jolpica_pits,
    load_laps,
    load_pits,
    load_race_control,
    load_results,
    load_stints,
    load_weather,
    race_calendar,
)
from pitwall.stints import snap_stints_to_pits

KNOWN_COMPOUNDS = {"SOFT", "MEDIUM", "HARD", *WET_COMPOUNDS}
COMPOUND_PAIRS = [("SOFT", "MEDIUM"), ("MEDIUM", "HARD"), ("SOFT", "HARD")]
FUEL_EFFECT_SECONDS = 3.0  # rough: about 100kg at 0.03s per kg, gone by the flag
FRESH_MAX_TYRE_LIFE = 8
MIN_PAIRED_DRIVERS = 3


class QuarantinedRace(Exception):
    """This race failed its audit and must not be used for modelling."""


@dataclass
class RaceAudit:
    year: int
    round_number: int
    race: str
    session_key: int
    stops: int = 0
    corrections: list[dict] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)

    @property
    def status(self) -> str:
        if self.reasons:
            return "quarantined"
        return "corrected" if self.corrections else "pass"


def is_finisher(status: str) -> bool:
    return status in ("Finished", "Lapped") or status.startswith("+")


def check_pits_against_jolpica(pits: pd.DataFrame, expected: set[tuple[int, int]]) -> list[str]:
    actual = set(zip(pits["driver_number"].tolist(), pits["lap_number"].tolist()))
    reasons = []
    if expected - actual:
        reasons.append(f"Jolpica stops missing from pit table: {sorted(expected - actual)}")
    if actual - expected:
        reasons.append(f"pit table stops missing from Jolpica: {sorted(actual - expected)}")
    return reasons


def check_stints_tile_laps(stints: pd.DataFrame) -> list[str]:
    reasons = []
    for number, group in stints.groupby("driver_number"):
        starts, ends = group["lap_start"].to_numpy(), group["lap_end"].to_numpy()
        if starts[0] != 1 or (starts[1:] != ends[:-1] + 1).any() or (starts > ends).any():
            spans = list(zip(starts.tolist(), ends.tolist()))
            reasons.append(f"car {number}: stints don't tile laps: {spans}")
    return reasons


def check_compounds(stints: pd.DataFrame, results: pd.DataFrame) -> list[str]:
    unknown = stints[~stints["compound"].isin(KNOWN_COMPOUNDS)]
    if not unknown.empty:
        labels = unknown["compound"].value_counts(dropna=False).to_dict()
        return [f"unknown compound labels: {labels}"]
    if stints["compound"].isin(WET_COMPOUNDS).any():
        return []
    used = stints.groupby("driver_number")["compound"].nunique()
    finishers = results.loc[results["Status"].map(is_finisher), "DriverNumber"]
    return [f"car {n}: finished a dry race on one compound" for n in finishers if used.get(n, 0) < 2]


def audit_race(year: int, round_number: int, race: str, session_key: int) -> RaceAudit:
    audit = RaceAudit(year, round_number, race, session_key)
    results = load_results(year, round_number)
    stops = load_jolpica_pits(year, round_number).merge(results, on="DriverId")
    expected = set(zip(stops["DriverNumber"].tolist(), stops["LapNumber"].tolist()))
    audit.stops = len(expected)

    stints = load_stints(session_key)
    try:
        pits = load_pits(session_key)
    except MissingTable:
        audit.reasons.append("no OpenF1 pit table")
        return audit

    audit.reasons += check_pits_against_jolpica(pits, expected)
    repair = snap_stints_to_pits(stints, pits)
    audit.corrections = repair.corrections
    audit.reasons += repair.problems
    if not repair.problems:
        audit.reasons += check_stints_tile_laps(repair.stints)
    audit.reasons += check_compounds(repair.stints, results)
    return audit


def audit_season(year: int) -> list[RaceAudit]:
    return [
        audit_race(year, row.Round, row.Race, row.SessionKey)
        for row in race_calendar(year).itertuples()
    ]


def flag_race(session_key: int) -> pd.DataFrame:
    return flag_laps(
        load_laps(session_key), load_race_control(session_key), load_weather(session_key)
    )


def load_model_laps(year: int, round_number: int) -> pd.DataFrame:
    """Flagged laps for modelling. Raises QuarantinedRace if the race failed its audit."""
    calendar = race_calendar(year).set_index("Round")
    race, session_key = calendar.loc[round_number, ["Race", "SessionKey"]]
    audit = audit_race(year, round_number, race, int(session_key))
    if audit.status == "quarantined":
        raise QuarantinedRace(f"{year} {race}: {'; '.join(audit.reasons)}")
    return flag_race(audit.session_key)


def compound_pace_gaps(
    flagged: pd.DataFrame, fuel_effect: float = FUEL_EFFECT_SECONDS
) -> pd.DataFrame:
    """Fresh-tyre pace gap for each compound pair, compared within each driver.

    A positive gap means the softer compound was faster, as it should be. Comparing within
    a driver takes the car out. Laps on rain-reported track are left out too.
    """
    excluded = flagged[[*FLAG_COLUMNS, "is_rain_reported"]].any(axis=1)
    fresh = flagged["TyreLife"] <= FRESH_MAX_TYRE_LIFE
    clean = flagged[~excluded & fresh & flagged["LapTimeSeconds"].notna()]
    total_laps = flagged["LapNumber"].max()
    remaining = (total_laps - clean["LapNumber"]) / total_laps
    corrected = clean["LapTimeSeconds"] - fuel_effect * remaining
    pace = corrected.groupby([clean["DriverNumber"], clean["Compound"]]).median().unstack()

    rows = []
    for softer, harder in COMPOUND_PAIRS:
        gaps = pd.Series(dtype=float)
        if softer in pace and harder in pace:
            gaps = (pace[harder] - pace[softer]).dropna()
        rows.append(
            {"Pair": f"{softer}<{harder}", "Drivers": len(gaps), "GapSeconds": gaps.median()}
        )
    return pd.DataFrame(rows)


def pace_order_verdict(gaps: pd.DataFrame) -> str:
    """'broken' if any pair with enough drivers runs backwards, else 'ok' or 'untestable'."""
    testable = gaps[gaps["Drivers"] >= MIN_PAIRED_DRIVERS]
    if testable.empty:
        return "untestable"
    return "broken" if (testable["GapSeconds"] < 0).any() else "ok"
