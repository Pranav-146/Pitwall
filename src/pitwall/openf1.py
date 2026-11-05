"""Race data from the public OpenF1 and Jolpica APIs, used while FastF1 needs an F1TV login.

Every raw pull is stored as parquet under data/raw, so a race only needs the APIs once.
Column names follow FastF1 (Driver, LapNumber, Stint, Compound, TyreLife, ...) so the
rest of the code does not care which source a table came from.
"""

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from pathlib import Path

import pandas as pd

from pitwall.data import REPO_ROOT

BASE_URL = "https://api.openf1.org/v1"
JOLPICA_URL = "https://api.jolpi.ca/ergast/f1"
RAW_DIR = REPO_ROOT / "data" / "raw"


def fetch_json(url: str, retries: int = 5):
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=60) as response:
                payload = json.load(response)
            time.sleep(0.4)  # stay under the public rate limits
            return payload
        except urllib.error.HTTPError as err:
            if err.code != 429 or attempt == retries - 1:
                raise
            time.sleep(2**attempt)


def cached_table(
    key: str, fetch: Callable[[], pd.DataFrame], raw_dir: Path = RAW_DIR
) -> pd.DataFrame:
    path = raw_dir / f"{key}.parquet"
    if path.exists():
        return pd.read_parquet(path)
    table = fetch()
    raw_dir.mkdir(parents=True, exist_ok=True)
    table.to_parquet(path, index=False)
    return table


def openf1_table(endpoint: str, **params) -> pd.DataFrame:
    def fetch() -> pd.DataFrame:
        url = f"{BASE_URL}/{endpoint}?{urllib.parse.urlencode(params)}"
        payload = fetch_json(url)
        if not isinstance(payload, list):  # OpenF1 answers {"detail": ...} when empty
            raise ValueError(f"No data from {url}: {payload}")
        return pd.DataFrame(payload)

    suffix = "_".join(f"{k}-{v}" for k, v in sorted(params.items()))
    return cached_table(f"openf1_{endpoint}_{suffix}".replace(" ", "-"), fetch)


def find_race_session(year: int, country: str) -> int:
    sessions = openf1_table("sessions", year=year, session_type="Race", country_name=country)
    races = sessions[sessions["session_name"] == "Race"]
    if len(races) != 1:
        raise ValueError(f"Expected one race for {country} {year}, found {len(races)}")
    return int(races["session_key"].iloc[0])


def load_results(year: int, round_number: int) -> pd.DataFrame:
    """Official classification from Jolpica, in finishing order."""

    def fetch() -> pd.DataFrame:
        url = f"{JOLPICA_URL}/{year}/{round_number}/results.json?limit=100"
        races = fetch_json(url)["MRData"]["RaceTable"]["Races"]
        if not races:
            raise ValueError(f"No results for {year} round {round_number}")
        return pd.json_normalize(races[0]["Results"])

    raw = cached_table(f"jolpica_results_{year}_{round_number}", fetch)
    results = pd.DataFrame(
        {
            "Position": raw["position"].astype(int),
            "DriverNumber": raw["number"].astype(int),
            "Driver": raw["Driver.code"],
            "DriverId": raw["Driver.driverId"],
            "Team": raw["Constructor.name"],
            "Status": raw["status"],
            "TotalTimeSeconds": pd.to_numeric(raw["Time.millis"]) / 1000,
        }
    )
    return results.sort_values("Position", ignore_index=True)


def load_jolpica_laps(year: int, round_number: int) -> pd.DataFrame:
    """Lap times from Jolpica, an independent check on OpenF1."""

    def fetch() -> pd.DataFrame:
        rows, offset = [], 0
        while True:
            url = f"{JOLPICA_URL}/{year}/{round_number}/laps.json?limit=100&offset={offset}"
            data = fetch_json(url)["MRData"]
            races = data["RaceTable"]["Races"]
            for lap in races[0]["Laps"] if races else []:
                for timing in lap["Timings"]:
                    rows.append({"lap": int(lap["number"]), **timing})
            offset += 100
            if offset >= int(data["total"]):
                return pd.DataFrame(rows)

    raw = cached_table(f"jolpica_laps_{year}_{round_number}", fetch)
    minutes, seconds = raw["time"].str.split(":", expand=True).T.values
    return pd.DataFrame(
        {
            "DriverId": raw["driverId"],
            "LapNumber": raw["lap"],
            "JolpicaSeconds": minutes.astype(int) * 60 + seconds.astype(float),
        }
    )


def load_jolpica_pits(year: int, round_number: int) -> pd.DataFrame:
    """Pit stop laps from Jolpica, an independent check on OpenF1 stints."""

    def fetch() -> pd.DataFrame:
        rows, offset = [], 0
        while True:
            url = f"{JOLPICA_URL}/{year}/{round_number}/pitstops.json?limit=100&offset={offset}"
            data = fetch_json(url)["MRData"]
            races = data["RaceTable"]["Races"]
            rows += races[0]["PitStops"] if races else []
            offset += 100
            if offset >= int(data["total"]):
                return pd.DataFrame(rows)

    raw = cached_table(f"jolpica_pitstops_{year}_{round_number}", fetch)
    return pd.DataFrame({"DriverId": raw["driverId"], "LapNumber": raw["lap"].astype(int)})


def load_stints(session_key: int) -> pd.DataFrame:
    return openf1_table("stints", session_key=session_key)


def load_pits(session_key: int) -> pd.DataFrame:
    return openf1_table("pit", session_key=session_key)


def load_race_control(session_key: int) -> pd.DataFrame:
    messages = openf1_table("race_control", session_key=session_key)
    return messages.assign(date=pd.to_datetime(messages["date"], format="ISO8601"))


def load_weather(session_key: int) -> pd.DataFrame:
    weather = openf1_table("weather", session_key=session_key)
    return weather.assign(date=pd.to_datetime(weather["date"], format="ISO8601"))


def load_laps(session_key: int) -> pd.DataFrame:
    """Every timed lap joined to its stint and pit data. Nothing is dropped."""
    laps = openf1_table("laps", session_key=session_key)
    stints = load_stints(session_key)
    pits = load_pits(session_key)
    drivers = openf1_table("drivers", session_key=session_key)

    # A retiring driver's last partial lap has no stint row, but they are on the same tyres.
    last_stints = stints.groupby("driver_number")["stint_number"].idxmax()
    last_laps = laps.groupby("driver_number")["lap_number"].max()
    stints = stints.copy()
    stints.loc[last_stints, "lap_end"] = (
        stints.loc[last_stints, "driver_number"]
        .map(last_laps)
        .combine(stints.loc[last_stints, "lap_end"], max)
    )

    joined = laps.merge(stints, on="driver_number", suffixes=("", "_stint"))
    joined = joined[joined["lap_number"].between(joined["lap_start"], joined["lap_end"])]
    if len(joined) != len(laps):
        raise ValueError(f"{len(laps)} laps became {len(joined)} after the stint join")

    pit_laps = set(zip(pits["driver_number"], pits["lap_number"]))
    keys = zip(joined["driver_number"], joined["lap_number"])
    joined = joined.assign(
        PitIn=[key in pit_laps for key in keys],
        TyreLife=joined["tyre_age_at_start"] + joined["lap_number"] - joined["lap_start"] + 1,
        LapStart=pd.to_datetime(joined["date_start"], format="ISO8601"),
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
    keep = [*columns.values(), "TyreLife", "PitIn", "LapStart"]
    return table[keep].sort_values(["DriverNumber", "LapNumber"], ignore_index=True)
