import pandas as pd
import pytest

from pitwall import quality
from pitwall.openf1 import MissingTable
from pitwall.quality import (
    QuarantinedRace,
    RaceAudit,
    audit_race,
    check_compounds,
    check_pits_against_jolpica,
    check_stints_tile_laps,
    compound_pace_gaps,
    load_model_laps,
    pace_order_verdict,
)
from pitwall.stints import snap_stints_to_pits


def make_stints(*rows) -> pd.DataFrame:
    columns = ["driver_number", "stint_number", "lap_start", "lap_end", "compound"]
    return pd.DataFrame(rows, columns=columns)


def make_pits(*rows) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=["driver_number", "lap_number"])


def spans(stints: pd.DataFrame) -> list[tuple[int, int]]:
    return list(zip(stints["lap_start"], stints["lap_end"]))


def test_aligned_stints_are_left_alone():
    stints = make_stints((1, 1, 1, 20, "SOFT"), (1, 2, 21, 50, "HARD"))
    repair = snap_stints_to_pits(stints, make_pits((1, 20)))
    assert spans(repair.stints) == [(1, 20), (21, 50)]
    assert repair.corrections == [] and repair.problems == []


def test_boundary_one_lap_early_is_corrected_and_logged():
    stints = make_stints((1, 1, 1, 19, "SOFT"), (1, 2, 20, 50, "HARD"))
    repair = snap_stints_to_pits(stints, make_pits((1, 20)))
    assert spans(repair.stints) == [(1, 20), (21, 50)]
    assert repair.corrections == [
        {"driver_number": 1, "stint_number": 1, "old_lap_end": 19, "new_lap_end": 20}
    ]
    assert repair.problems == []


def test_each_stop_is_judged_on_its_own():
    # Russell, Canada 2024: two boundaries a lap early, one already right.
    stints = make_stints(
        (63, 1, 1, 24, "INTERMEDIATE"),
        (63, 2, 25, 45, "INTERMEDIATE"),
        (63, 3, 46, 53, "HARD"),
        (63, 4, 54, 70, "MEDIUM"),
    )
    repair = snap_stints_to_pits(stints, make_pits((63, 25), (63, 45), (63, 54)))
    assert spans(repair.stints) == [(1, 25), (26, 45), (46, 54), (55, 70)]
    assert len(repair.corrections) == 2


def test_pit_stop_on_lap_1_is_corrected():
    stints = make_stints((1, 1, 1, 0, "MEDIUM"), (1, 2, 1, 50, "HARD"))
    repair = snap_stints_to_pits(stints, make_pits((1, 1)))
    assert spans(repair.stints) == [(1, 1), (2, 50)]


def test_boundary_two_laps_off_is_not_patched():
    stints = make_stints((1, 1, 1, 18, "SOFT"), (1, 2, 19, 50, "HARD"))
    repair = snap_stints_to_pits(stints, make_pits((1, 20)))
    assert spans(repair.stints) == [(1, 18), (19, 50)]
    assert repair.corrections == []
    assert len(repair.problems) == 1


def test_boundary_one_lap_late_is_not_patched():
    stints = make_stints((1, 1, 1, 21, "SOFT"), (1, 2, 22, 50, "HARD"))
    repair = snap_stints_to_pits(stints, make_pits((1, 20)))
    assert spans(repair.stints) == [(1, 21), (22, 50)]
    assert len(repair.problems) == 1


def test_stop_with_no_stint_change_is_a_problem():
    # Tsunoda, Canada 2023: the lap 34 stop has no boundary, and lap 2 has no stop.
    stints = make_stints(
        (22, 1, 1, 0, "MEDIUM"), (22, 2, 1, 2, "HARD"), (22, 3, 3, 70, "HARD")
    )
    repair = snap_stints_to_pits(stints, make_pits((22, 1), (22, 34)))
    assert repair.corrections == []
    assert len(repair.problems) == 1


def test_stint_change_with_no_stop_is_a_problem():
    stints = make_stints((1, 1, 1, 20, "SOFT"), (1, 2, 21, 50, "HARD"))
    assert len(snap_stints_to_pits(stints, make_pits()).problems) == 1


def test_one_bad_driver_does_not_stop_others_being_repaired():
    stints = make_stints(
        (1, 1, 1, 19, "SOFT"),
        (1, 2, 20, 50, "HARD"),
        (2, 1, 1, 10, "SOFT"),
        (2, 2, 11, 50, "HARD"),
    )
    repair = snap_stints_to_pits(stints, make_pits((1, 20), (2, 30)))
    assert len(repair.corrections) == 1
    assert len(repair.problems) == 1


def test_input_stints_are_not_modified():
    stints = make_stints((1, 1, 1, 19, "SOFT"), (1, 2, 20, 50, "HARD"))
    snap_stints_to_pits(stints, make_pits((1, 20)))
    assert spans(stints) == [(1, 19), (20, 50)]


def test_pit_table_must_match_jolpica_both_ways():
    pits = make_pits((1, 20), (2, 30))
    assert check_pits_against_jolpica(pits, {(1, 20), (2, 30)}) == []
    assert len(check_pits_against_jolpica(pits, {(1, 20)})) == 1
    assert len(check_pits_against_jolpica(pits, {(1, 20), (2, 30), (3, 40)})) == 1


def test_stints_must_tile_laps():
    good = make_stints((1, 1, 1, 20, "SOFT"), (1, 2, 21, 50, "HARD"))
    gap = make_stints((1, 1, 1, 20, "SOFT"), (1, 2, 23, 50, "HARD"))
    assert check_stints_tile_laps(good) == []
    assert len(check_stints_tile_laps(gap)) == 1


RESULTS = pd.DataFrame({"DriverNumber": [1, 2], "Status": ["Finished", "Engine"]})


def test_dry_finisher_needs_two_compounds():
    stints = make_stints(
        (1, 1, 1, 20, "HARD"), (1, 2, 21, 50, "HARD"), (2, 1, 1, 9, "HARD")
    )
    assert check_compounds(stints, RESULTS) == ["car 1: finished a dry race on one compound"]


def test_wet_race_is_exempt_from_two_compounds():
    stints = make_stints((1, 1, 1, 20, "INTERMEDIATE"), (1, 2, 21, 50, "INTERMEDIATE"))
    assert check_compounds(stints, RESULTS) == []


def test_unknown_compound_fails():
    stints = make_stints((1, 1, 1, 20, "UNKNOWN"), (1, 2, 21, 50, "HARD"))
    assert "unknown compound" in check_compounds(stints, RESULTS)[0]


@pytest.fixture
def fake_race(monkeypatch):
    """A one-driver race: stints a lap early, pit table and Jolpica agreeing on lap 20."""
    stints = make_stints(
        (1, 1, 1, 19, "SOFT"), (1, 2, 20, 50, "HARD")
    )
    monkeypatch.setattr(
        quality,
        "load_results",
        lambda *_: pd.DataFrame(
            {"DriverNumber": [1], "DriverId": ["max"], "Status": ["Finished"]}
        ),
    )
    monkeypatch.setattr(
        quality,
        "load_jolpica_pits",
        lambda *_: pd.DataFrame({"DriverId": ["max"], "LapNumber": [20]}),
    )
    monkeypatch.setattr(quality, "load_stints", lambda _: stints)
    monkeypatch.setattr(quality, "load_pits", lambda _: make_pits((1, 20)))
    monkeypatch.setattr(
        quality,
        "race_calendar",
        lambda _: pd.DataFrame({"Round": [1], "Race": ["Test"], "SessionKey": [99]}),
    )
    monkeypatch.setattr(quality, "flag_race", lambda key: f"laps for {key}")


def test_off_by_one_race_is_corrected_not_quarantined(fake_race):
    audit = audit_race(2024, 1, "Test", 99)
    assert audit.status == "corrected"
    assert audit.stops == 1
    assert len(audit.corrections) == 1


def test_missing_pit_table_quarantines(fake_race, monkeypatch):
    def missing(_):
        raise MissingTable("no pit table")

    monkeypatch.setattr(quality, "load_pits", missing)
    audit = audit_race(2024, 1, "Test", 99)
    assert audit.status == "quarantined"
    assert audit.reasons == ["no OpenF1 pit table"]


def test_jolpica_disagreement_quarantines(fake_race, monkeypatch):
    monkeypatch.setattr(
        quality,
        "load_jolpica_pits",
        lambda *_: pd.DataFrame({"DriverId": ["max"], "LapNumber": [25]}),
    )
    assert audit_race(2024, 1, "Test", 99).status == "quarantined"


def test_clean_race_passes():
    assert RaceAudit(2024, 1, "Test", 99).status == "pass"


def test_quarantined_race_cannot_reach_a_model(fake_race, monkeypatch):
    monkeypatch.setattr(quality, "load_pits", lambda _: make_pits((1, 40)))
    with pytest.raises(QuarantinedRace, match="2024 Test"):
        load_model_laps(2024, 1)


def test_passing_race_reaches_a_model(fake_race):
    assert load_model_laps(2024, 1) == "laps for 99"


def fresh_laps(pace: dict[int, dict[str, float]], total_laps: int = 60) -> pd.DataFrame:
    """Two clean laps per driver per compound, at the same point in the race."""
    rows = []
    for driver, compounds in pace.items():
        for compound, seconds in compounds.items():
            for lap in (30, 31):
                rows.append(
                    {
                        "DriverNumber": driver,
                        "LapNumber": lap,
                        "Compound": compound,
                        "TyreLife": 3,
                        "LapTimeSeconds": seconds,
                    }
                )
    rows.append({**rows[-1], "LapNumber": total_laps, "TyreLife": 40})
    laps = pd.DataFrame(rows)
    for column in [*quality.FLAG_COLUMNS, "is_rain_reported"]:
        laps[column] = False
    return laps


def test_pace_gap_is_positive_when_softer_is_faster():
    laps = fresh_laps({n: {"SOFT": 90.0, "MEDIUM": 90.5, "HARD": 91.0} for n in (1, 2, 3)})
    gaps = compound_pace_gaps(laps).set_index("Pair")
    assert gaps.loc["SOFT<MEDIUM", "GapSeconds"] == pytest.approx(0.5)
    assert gaps.loc["SOFT<HARD", "GapSeconds"] == pytest.approx(1.0)
    assert pace_order_verdict(compound_pace_gaps(laps)) == "ok"


def test_swapped_labels_break_the_pace_order():
    laps = fresh_laps({n: {"HARD": 90.0, "MEDIUM": 90.5, "SOFT": 91.0} for n in (1, 2, 3)})
    assert pace_order_verdict(compound_pace_gaps(laps)) == "broken"


def test_pace_is_compared_within_each_driver():
    # A fast car on hards and a slow car on softs must not look like hards being quicker.
    laps = fresh_laps(
        {
            1: {"SOFT": 88.0, "HARD": 89.0},
            2: {"SOFT": 90.0, "HARD": 91.0},
            3: {"SOFT": 92.0, "HARD": 93.0},
            4: {"HARD": 80.0},
            5: {"SOFT": 99.0},
        }
    )
    gaps = compound_pace_gaps(laps).set_index("Pair")
    assert gaps.loc["SOFT<HARD", "Drivers"] == 3
    assert gaps.loc["SOFT<HARD", "GapSeconds"] == pytest.approx(1.0)


def test_fuel_correction_removes_the_heavy_car_penalty():
    # Same underlying pace, but softs ran at lap 10 with more fuel on board.
    laps = fresh_laps({n: {"HARD": 90.0} for n in (1, 2, 3)})
    softs = laps[laps["LapNumber"] < 60].assign(
        Compound="SOFT", LapNumber=lambda d: d["LapNumber"] - 20, LapTimeSeconds=91.0
    )
    both = pd.concat([laps, softs], ignore_index=True)
    assert pace_order_verdict(compound_pace_gaps(both, fuel_effect=0.0)) == "broken"
    gap = compound_pace_gaps(both, fuel_effect=3.0).set_index("Pair").loc["SOFT<HARD", "GapSeconds"]
    assert gap == pytest.approx(0.0)


def test_too_few_drivers_is_untestable():
    laps = fresh_laps({1: {"SOFT": 90.0, "HARD": 89.0}, 2: {"SOFT": 90.0, "HARD": 89.0}})
    assert pace_order_verdict(compound_pace_gaps(laps)) == "untestable"


def test_flagged_and_old_tyre_laps_are_ignored():
    laps = fresh_laps({n: {"SOFT": 90.0, "HARD": 91.0} for n in (1, 2, 3)})
    noise = laps.assign(LapTimeSeconds=200.0, is_blue_flag=True)
    worn = laps.assign(LapTimeSeconds=200.0, TyreLife=30)
    rainy = laps.assign(LapTimeSeconds=200.0, is_rain_reported=True)
    both = pd.concat([laps, noise, worn, rainy], ignore_index=True)
    gaps = compound_pace_gaps(both).set_index("Pair")
    assert gaps.loc["SOFT<HARD", "GapSeconds"] == pytest.approx(1.0)
