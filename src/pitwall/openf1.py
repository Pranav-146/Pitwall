"""Race data from the public OpenF1 API, used while FastF1 needs an F1TV login.

Column names follow FastF1 (Driver, LapNumber, Stint, Compound, TyreLife, ...)
so the rest of the code does not care which source a table came from.
"""

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd

from pitwall.data import REPO_ROOT

BASE_URL = "https://api.openf1.org/v1"
JOLPICA_URL = "https://api.jolpi.ca/ergast/f1"
CACHE_DIR = REPO_ROOT / "data" / "http_cache"


def get_json(url: str, cache_key: str, cache_dir: Path = CACHE_DIR, retries: int = 5):
    path = cache_dir / f"{cache_key}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))

    for attempt in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=60) as response:
                payload = json.load(response)
            break
        except urllib.error.HTTPError as err:
            if err.code != 429 or attempt == retries - 1:
                raise
            time.sleep(2**attempt)

    cache_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    time.sleep(0.4)  # stay under the public rate limits
    return payload


def _openf1(endpoint: str, **params) -> pd.DataFrame:
    query = urllib.parse.urlencode(params)
    key = f"openf1_{endpoint}_" + "_".join(f"{k}-{v}" for k, v in sorted(params.items()))
    return pd.DataFrame(get_json(f"{BASE_URL}/{endpoint}?{query}", key.replace(" ", "-")))


def find_race_session(year: int, country: str) -> int:
    sessions = _openf1("sessions", year=year, session_type="Race", country_name=country)
    races = sessions[sessions["session_name"] == "Race"]
    if len(races) != 1:
        raise ValueError(f"Expected one race for {country} {year}, found {len(races)}")
    return int(races["session_key"].iloc[0])


def load_results(year: int, round_number: int) -> pd.DataFrame:
    """Official classification from Jolpica, in finishing order."""
    url = f"{JOLPICA_URL}/{year}/{round_number}/results.json?limit=100"
    payload = get_json(url, f"jolpica_results_{year}_{round_number}")
    races = payload["MRData"]["RaceTable"]["Races"]
    if not races:
        raise ValueError(f"No results for {year} round {round_number}")
    rows = [
        {
            "Position": int(r["position"]),
            "DriverNumber": int(r["number"]),
            "Driver": r["Driver"]["code"],
            "DriverId": r["Driver"]["driverId"],
            "Team": r["Constructor"]["name"],
            "Status": r["status"],
            "TotalTimeSeconds": int(r["Time"]["millis"]) / 1000 if "Time" in r else None,
        }
        for r in races[0]["Results"]
    ]
    return pd.DataFrame(rows).sort_values("Position", ignore_index=True)


def load_laps(session_key: int) -> pd.DataFrame:
    """Every timed lap joined to its stint and pit data. Nothing is dropped."""
    laps = _openf1("laps", session_key=session_key)
    stints = _openf1("stints", session_key=session_key)
    pits = _openf1("pit", session_key=session_key)
    drivers = _openf1("drivers", session_key=session_key)

    joined = laps.merge(stints, on="driver_number", suffixes=("", "_stint"))
    joined = joined[joined["lap_number"].between(joined["lap_start"], joined["lap_end"])]
    if len(joined) != len(laps):
        raise ValueError(f"{len(laps)} laps became {len(joined)} after the stint join")

    pit_laps = set(zip(pits["driver_number"], pits["lap_number"]))
    keys = zip(joined["driver_number"], joined["lap_number"])
    joined = joined.assign(
        PitIn=[key in pit_laps for key in keys],
        TyreLife=joined["tyre_age_at_start"] + joined["lap_number"] - joined["lap_start"] + 1,
    ).merge(drivers[["driver_number", "name_acronym", "team_name"]], on="driver_number")

    columns = {
        "name_acronym": "Driver",
        "driver_number": "DriverNumber",
        "team_name": "Team",
        "lap_number": "LapNumber",
        "lap_duration": "LapTimeSeconds",
        "stint_number": "Stint",
        "compound": "Compound",
        "is_pit_out_lap": "PitOut",
    }
    table = joined.rename(columns=columns)
    keep = [*columns.values(), "TyreLife", "PitIn"]
    return table[keep].sort_values(["DriverNumber", "LapNumber"], ignore_index=True)
