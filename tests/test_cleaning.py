import pandas as pd

from pitwall.cleaning import FLAG_COLUMNS, INFO_COLUMNS, flag_laps, neutralised_periods

T0 = pd.Timestamp("2024-03-09T17:00:00+00:00")


def at(seconds: float) -> pd.Timestamp:
    return T0 + pd.to_timedelta(seconds, unit="s")


def make_laps(times, driver=1, compound="HARD", stints=None) -> pd.DataFrame:
    starts = [sum(times[:i]) for i in range(len(times))]
    return pd.DataFrame(
        {
            "DriverNumber": driver,
            "LapNumber": range(1, len(times) + 1),
            "LapTimeSeconds": times,
            "Stint": stints or [1] * len(times),
            "Compound": compound,
            "PitIn": False,
            "PitOut": False,
            "LapStart": [at(s) for s in starts],
        }
    )


def messages(*rows) -> pd.DataFrame:
    columns = ["date", "message", "flag", "driver_number"]
    return pd.DataFrame(rows, columns=columns)


NO_MESSAGES = messages()
DRY = pd.DataFrame({"date": [at(0)], "rainfall": [0]})


def test_every_lap_is_kept_and_every_flag_exists():
    laps = make_laps([90.0] * 8)
    flagged = flag_laps(laps, NO_MESSAGES, DRY)
    assert len(flagged) == len(laps)
    assert set(FLAG_COLUMNS) <= set(flagged.columns)


def test_chequered_flag_is_not_a_red_flag():
    race_control = messages((at(100), "CHEQUERED FLAG", "CHEQUERED", None))
    assert neutralised_periods(race_control, at(500)) == []


def test_vsc_turning_into_sc_is_one_period():
    race_control = messages(
        (at(100), "VIRTUAL SAFETY CAR DEPLOYED", None, None),
        (at(150), "SAFETY CAR DEPLOYED", None, None),
        (at(400), "SAFETY CAR IN THIS LAP", None, None),
    )
    assert neutralised_periods(race_control, at(900)) == [(at(100), at(400))]


def test_period_left_open_runs_to_race_end():
    race_control = messages((at(100), "VIRTUAL SAFETY CAR DEPLOYED", None, None))
    assert neutralised_periods(race_control, at(900)) == [(at(100), at(900))]


def test_red_flag_ends_when_session_restarts():
    race_control = messages(
        (at(100), "RED FLAG", "RED", None),
        (at(150), "SAFETY CAR IN THIS LAP", None, None),
        (at(300), "SESSION STARTED", None, None),
    )
    assert neutralised_periods(race_control, at(900)) == [(at(100), at(300))]


def test_sc_into_red_flag_is_one_period():
    race_control = messages(
        (at(100), "SAFETY CAR DEPLOYED", None, None),
        (at(200), "RED FLAG", "RED", None),
        (at(300), "SESSION STARTED", None, None),
        (at(500), "SAFETY CAR DEPLOYED", None, None),
        (at(600), "SAFETY CAR IN THIS LAP", None, None),
    )
    assert neutralised_periods(race_control, at(900)) == [(at(100), at(300)), (at(500), at(600))]


def test_lap_1_is_not_an_outlap():
    laps = make_laps([90.0] * 3)
    laps["PitOut"] = [True, False, True]
    assert flag_laps(laps, NO_MESSAGES, DRY)["is_outlap"].tolist() == [False, False, True]


def test_neutralised_laps_include_the_lap_after():
    race_control = messages(
        (at(100), "SAFETY CAR DEPLOYED", None, None),
        (at(110), "SAFETY CAR IN THIS LAP", None, None),
    )
    flagged = flag_laps(make_laps([90.0] * 5), race_control, DRY)
    assert flagged["is_sc_vsc_red"].tolist() == [False, True, True, False, False]


def test_slow_outlier_threshold_is_a_parameter():
    times = [90.0, 90.0, 90.0, 91.2, 90.0, 90.0, 90.0]
    assert flag_laps(make_laps(times), NO_MESSAGES, DRY, 1.0)["is_slow_outlier"].sum() == 1
    assert flag_laps(make_laps(times), NO_MESSAGES, DRY, 1.5)["is_slow_outlier"].sum() == 0


def test_rolling_median_does_not_cross_stints():
    # Stint 2 is 5s slower. Across stints, its first laps would look like outliers.
    times = [90.0] * 5 + [95.0] * 5
    laps = make_laps(times, stints=[1] * 5 + [2] * 5)
    assert not flag_laps(laps, NO_MESSAGES, DRY)["is_slow_outlier"].any()


def test_fast_laps_are_not_flagged():
    times = [90.0, 90.0, 90.0, 85.0, 90.0, 90.0, 90.0]
    assert not flag_laps(make_laps(times), NO_MESSAGES, DRY)["is_slow_outlier"].any()


def test_slow_outlier_ignores_neutralised_laps():
    times = [90.0, 90.0, 90.0, 130.0, 90.0, 90.0, 90.0]
    race_control = messages(
        (at(280), "SAFETY CAR DEPLOYED", None, None),
        (at(285), "SAFETY CAR IN THIS LAP", None, None),
    )
    flagged = flag_laps(make_laps(times), race_control, DRY)
    assert flagged["is_sc_vsc_red"].iloc[3]
    assert not flagged["is_slow_outlier"].any()


def test_blue_flag_matches_by_time_for_that_driver_only():
    laps = pd.concat([make_laps([90.0] * 3, driver=1), make_laps([90.0] * 3, driver=2)])
    race_control = messages((at(100), "WAVED BLUE FLAG FOR CAR 2", "BLUE", 2.0))
    flagged = flag_laps(laps, race_control, DRY)
    hits = flagged[flagged["is_blue_flag"]]
    assert hits[["DriverNumber", "LapNumber"]].values.tolist() == [[2, 2]]


def test_is_wet_comes_from_compound_only():
    inters = make_laps([90.0] * 3, compound="INTERMEDIATE")
    assert flag_laps(inters, NO_MESSAGES, DRY)["is_wet"].all()
    rain = pd.DataFrame({"date": [at(100), at(160)], "rainfall": [1, 1]})
    assert not flag_laps(make_laps([90.0] * 3), NO_MESSAGES, rain)["is_wet"].any()


def test_single_rain_sample_is_not_reported():
    rain = pd.DataFrame({"date": [at(40), at(100), at(160)], "rainfall": [0, 1, 0]})
    flagged = flag_laps(make_laps([90.0] * 3), NO_MESSAGES, rain)
    assert not flagged["is_rain_reported"].any()


def test_two_consecutive_rain_samples_are_reported():
    rain = pd.DataFrame({"date": [at(40), at(100), at(190)], "rainfall": [0, 1, 1]})
    flagged = flag_laps(make_laps([90.0] * 3), NO_MESSAGES, rain)
    assert flagged["is_rain_reported"].tolist() == [False, True, True]


def test_rain_samples_are_paired_in_time_order():
    rain = pd.DataFrame({"date": [at(190), at(40), at(100)], "rainfall": [1, 0, 1]})
    flagged = flag_laps(make_laps([90.0] * 3), NO_MESSAGES, rain)
    assert flagged["is_rain_reported"].tolist() == [False, True, True]


def test_rain_reported_is_not_an_exclusion_flag():
    assert "is_rain_reported" in INFO_COLUMNS
    assert "is_rain_reported" not in FLAG_COLUMNS


def test_lap_with_missing_timing_is_kept():
    laps = make_laps([90.0] * 4)
    laps.loc[0, "LapStart"] = pd.NaT
    laps.loc[2, "LapTimeSeconds"] = float("nan")
    flagged = flag_laps(laps, NO_MESSAGES, DRY)
    assert len(flagged) == 4
    assert not flagged["is_slow_outlier"].iloc[2]
