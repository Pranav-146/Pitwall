import urllib.error

import pandas as pd
import pytest

from pitwall import openf1
from pitwall.openf1 import MissingTable, load_laps, openf1_table, race_calendar


def fake_calendar(monkeypatch, sessions: list[dict], schedule: list[dict]) -> None:
    monkeypatch.setattr(openf1, "openf1_table", lambda *_, **__: pd.DataFrame(sessions))
    monkeypatch.setattr(openf1, "cached_table", lambda *_: pd.DataFrame(schedule))


def session(key: int, date: str, cancelled: bool = False) -> dict:
    return {"session_key": key, "date_start": date, "is_cancelled": cancelled}


def race(number: str, name: str, date: str) -> dict:
    return {"round": number, "raceName": name, "date": date}


def test_cancelled_race_is_dropped_from_the_calendar(monkeypatch):
    fake_calendar(
        monkeypatch,
        [
            session(1, "2023-05-07T19:30:00+00:00"),
            session(2, "2023-05-21T13:00:00+00:00", cancelled=True),
            session(3, "2023-05-28T13:00:00+00:00"),
        ],
        [race("5", "Miami Grand Prix", "2023-05-07"), race("6", "Monaco Grand Prix", "2023-05-28")],
    )
    calendar = race_calendar(2023)
    assert calendar["SessionKey"].tolist() == [1, 3]
    assert calendar["Round"].tolist() == [5, 6]
    assert calendar["Race"].tolist() == ["Miami", "Monaco"]


def test_calendar_allows_a_one_day_date_difference(monkeypatch):
    fake_calendar(
        monkeypatch,
        [session(1, "2024-11-24T06:00:00+00:00")],
        [race("22", "Las Vegas Grand Prix", "2024-11-23")],
    )
    assert race_calendar(2024)["SessionKey"].tolist() == [1]


def test_calendars_that_disagree_fail_loudly(monkeypatch):
    fake_calendar(
        monkeypatch,
        [session(1, "2024-11-24T06:00:00+00:00")],
        [race("22", "Las Vegas Grand Prix", "2024-10-01")],
    )
    with pytest.raises(ValueError, match="disagree"):
        race_calendar(2024)


def test_calendars_of_different_length_fail_loudly(monkeypatch):
    fake_calendar(
        monkeypatch,
        [session(1, "2024-03-02T15:00:00+00:00")],
        [race("1", "Bahrain Grand Prix", "2024-03-02"), race("2", "Saudi Grand Prix", "2024-03-09")],
    )
    with pytest.raises(ValueError, match="1 OpenF1 races, 2 on Jolpica"):
        race_calendar(2024)


def test_404_means_the_table_is_missing_and_is_not_cached(monkeypatch, tmp_path):
    def not_found(url):
        raise urllib.error.HTTPError(url, 404, "Not Found", None, None)

    monkeypatch.setattr(openf1, "fetch_json", not_found)
    monkeypatch.setattr(openf1, "RAW_DIR", tmp_path)
    monkeypatch.setattr(
        openf1, "cached_table", lambda key, fetch, raw_dir=tmp_path: fetch()
    )
    with pytest.raises(MissingTable):
        openf1_table("pit", session_key=1)
    assert list(tmp_path.iterdir()) == []


def test_transient_errors_are_retried(monkeypatch):
    calls = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self, *_):
            return b"[1]"

    def flaky(url, timeout):
        calls.append(url)
        if len(calls) == 1:
            raise TimeoutError("timed out")
        return Response()

    monkeypatch.setattr(openf1.urllib.request, "urlopen", flaky)
    monkeypatch.setattr(openf1.time, "sleep", lambda _: None)
    assert openf1.fetch_json("http://example.test") == [1]
    assert len(calls) == 2


def test_load_laps_uses_corrected_stints(monkeypatch):
    tables = {
        "laps": pd.DataFrame(
            {
                "driver_number": [1, 1, 1],
                "lap_number": [1, 2, 3],
                "lap_duration": [90.0, 91.0, 89.0],
                "is_pit_out_lap": [False, False, True],
                "date_start": ["2024-03-02T15:00:00+00:00"] * 3,
            }
        ),
        "drivers": pd.DataFrame(
            {"driver_number": [1], "name_acronym": ["VER"], "team_name": ["Red Bull"]}
        ),
    }
    stints = pd.DataFrame(
        {
            "driver_number": [1, 1],
            "stint_number": [1, 2],
            "lap_start": [1, 2],
            "lap_end": [1, 3],
            "compound": ["SOFT", "HARD"],
            "tyre_age_at_start": [0, 0],
        }
    )
    pits = pd.DataFrame({"driver_number": [1], "lap_number": [2]})
    monkeypatch.setattr(openf1, "openf1_table", lambda endpoint, **_: tables[endpoint])
    monkeypatch.setattr(openf1, "load_stints", lambda _: stints)
    monkeypatch.setattr(openf1, "load_pits", lambda _: pits)

    laps = load_laps(1)
    assert laps["Compound"].tolist() == ["SOFT", "SOFT", "HARD"]
    assert laps["TyreLife"].tolist() == [1, 2, 1]
    assert laps["PitIn"].tolist() == [False, True, False]
