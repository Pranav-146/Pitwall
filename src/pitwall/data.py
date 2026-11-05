"""Loading F1 session data through FastF1, with the on-disk cache always on."""

from pathlib import Path

import fastf1
from fastf1.core import Session

REPO_ROOT = Path(__file__).resolve().parents[2]
CACHE_DIR = REPO_ROOT / "data" / "fastf1_cache"


def enable_cache(cache_dir: Path = CACHE_DIR) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    fastf1.Cache.configure(cache_dir=str(cache_dir))


def load_race(year: int, event: str | int, telemetry: bool = False) -> Session:
    """Load a race session. Telemetry is off by default: it is slow and big."""
    enable_cache()
    session = fastf1.get_session(year, event, "R")
    session.load(laps=True, telemetry=telemetry, weather=True, messages=True)
    # FastF1 logs "Finished loading" even when every endpoint failed.
    session.laps  # raises DataNotLoadedError if nothing actually arrived
    return session
