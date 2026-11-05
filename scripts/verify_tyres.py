"""Check OpenF1 tyre data for internal consistency before it feeds the Phase 1 model.

Per race: stints must tile each driver's laps, stint boundaries must line up with pit
laps, dry-race finishers must use two compounds, and tyre ages must be plausible.
"""

import pandas as pd

from pitwall.cleaning import WET_COMPOUNDS
from pitwall.openf1 import (
    find_race_session,
    load_jolpica_laps,
    load_jolpica_pits,
    load_laps,
    load_pits,
    load_results,
    load_stints,
    openf1_table,
)

YEAR = 2024
RACES = [("Bahrain", 1), ("Saudi Arabia", 2), ("Canada", 9), ("Spain", 10)]
MAX_SANE_START_AGE = 10


def is_finisher(status: str) -> bool:
    return status in ("Finished", "Lapped") or status.startswith("+")


def check_coverage(stints, raw_laps, names) -> list[str]:
    problems = []
    last_laps = raw_laps.groupby("driver_number")["lap_number"].max()
    for number, group in stints.sort_values("stint_number").groupby("driver_number"):
        name = names[number]
        if group["lap_start"].iloc[0] != 1:
            problems.append(f"{name}: first stint starts on lap {group['lap_start'].iloc[0]}")
        gaps = group["lap_start"].iloc[1:].to_numpy() - group["lap_end"].iloc[:-1].to_numpy()
        if (gaps != 1).any():
            problems.append(f"{name}: stints overlap or leave a gap: {gaps.tolist()}")
        if group["lap_end"].iloc[-1] != last_laps[number]:
            problems.append(
                f"{name}: last stint ends lap {group['lap_end'].iloc[-1]}, "
                f"timing ends lap {last_laps[number]}"
            )
    return problems


def check_pit_alignment(stints, pits, names) -> list[str]:
    problems = []
    for number, group in stints.sort_values("stint_number").groupby("driver_number"):
        name = names[number]
        boundaries = set(group["lap_end"].iloc[:-1])
        pit_laps = set(pits.loc[pits["driver_number"] == number, "lap_number"])
        for lap in sorted(boundaries - pit_laps):
            problems.append(f"{name}: stint ends lap {lap} with no pit stop")
        for lap in sorted(pit_laps - boundaries):
            problems.append(f"{name}: pit stop lap {lap} with no stint change")
    return problems


def check_out_laps(stints, raw_laps, names) -> list[str]:
    problems = []
    out_laps = raw_laps[raw_laps["is_pit_out_lap"].fillna(False).astype(bool)]
    out_keys = set(zip(out_laps["driver_number"], out_laps["lap_number"]))
    later = stints[stints["stint_number"] > 1]
    starts = set(zip(later["driver_number"], later["lap_start"]))
    for number, lap in sorted(starts - out_keys):
        problems.append(f"{names[number]}: stint starts lap {lap}, not marked as out-lap")
    for number, lap in sorted(out_keys - starts):
        problems.append(f"{names[number]}: out-lap on lap {lap} with no new stint")
    return problems


def check_compounds(stints, results, names) -> list[str]:
    finishers = results[results["Status"].map(is_finisher)]["DriverNumber"]
    used = stints.groupby("driver_number")["compound"].nunique()
    return [f"{names[n]}: finished on one compound" for n in finishers if used.get(n, 0) < 2]


def check_ages(stints, names) -> list[str]:
    problems = []
    for row in stints.itertuples():
        if row.tyre_age_at_start < 0:
            problems.append(f"{names[row.driver_number]}: negative age {row.tyre_age_at_start}")
        elif row.tyre_age_at_start > MAX_SANE_START_AGE:
            problems.append(
                f"{names[row.driver_number]} stint {row.stint_number}: "
                f"{row.compound} starts {row.tyre_age_at_start} laps old"
            )
    return problems


def check_against_jolpica(stints, pits, results, round_number) -> list[str]:
    reference = load_jolpica_pits(YEAR, round_number).merge(results, on="DriverId")
    expected = set(zip(reference["DriverNumber"], reference["LapNumber"]))
    pit_laps = set(zip(pits["driver_number"], pits["lap_number"]))
    ordered = stints.sort_values("stint_number")
    ends = ordered[ordered.duplicated("driver_number", keep="last")]
    stint_ends = set(zip(ends["driver_number"], ends["lap_end"]))
    print(
        f"Jolpica stops {len(expected)}: pit table matches {len(expected & pit_laps)}, "
        f"stint ends match {len(expected & stint_ends)}"
    )
    offsets = [
        lap - end
        for (number, lap), end in zip(
            sorted(expected),
            ends.sort_values(["driver_number", "lap_end"])["lap_end"],
        )
    ]
    print("Jolpica lap minus stint end:", pd.Series(offsets).value_counts().to_dict())
    return [f"stop not in pit table: {key}" for key in sorted(expected - pit_laps)]


def lap1_offset(laps, results, round_number) -> str:
    reference = load_jolpica_laps(YEAR, round_number).merge(results, on="DriverId")
    both = laps.merge(reference, on=["DriverNumber", "LapNumber"])
    lap1 = both[both["LapNumber"] == 1]
    excess = (lap1["LapTimeSeconds"] - lap1["JolpicaSeconds"]).dropna()
    return f"{excess.min():.3f} to {excess.max():.3f}s, mean {excess.mean():.3f}s, n={len(excess)}"


def verify(country: str, round_number: int) -> None:
    session_key = find_race_session(YEAR, country)
    stints, pits = load_stints(session_key), load_pits(session_key)
    raw_laps = openf1_table("laps", session_key=session_key)
    results = load_results(YEAR, round_number)
    names = dict(zip(results["DriverNumber"], results["Driver"]))

    dry = not stints["compound"].isin(WET_COMPOUNDS).any()
    print(f"\n=== {country} ({'dry' if dry else 'wet'}): {len(stints)} stints, {len(pits)} pit rows")
    print("compound stints:", stints["compound"].value_counts().to_dict())
    print("start ages:", stints["tyre_age_at_start"].value_counts().sort_index().to_dict())
    print("statuses:", results["Status"].value_counts().to_dict())
    laps = load_laps(session_key)
    print(f"load_laps rows: {len(laps)} of {len(raw_laps)}")
    print("lap 1 excess over Jolpica:", lap1_offset(laps, results, round_number))

    checks = {
        "coverage": check_coverage(stints, raw_laps, names),
        "pit alignment": check_pit_alignment(stints, pits, names),
        "out-laps": check_out_laps(stints, raw_laps, names),
        "two compounds (dry only)": check_compounds(stints, results, names) if dry else [],
        "Jolpica pit stops": check_against_jolpica(stints, pits, results, round_number),
        "tyre age": check_ages(stints, names),
    }
    for name, problems in checks.items():
        print(f"[{'ok' if not problems else len(problems)}] {name}")
        for problem in problems:
            print(f"    {problem}")


def main() -> None:
    pd.set_option("display.width", 200)
    for country, round_number in RACES:
        verify(country, round_number)


if __name__ == "__main__":
    main()
