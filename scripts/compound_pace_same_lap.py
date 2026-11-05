"""Compare compounds on the same lap, to test whether the fresh-tyre pace check can be trusted.

Fresh mediums mostly run early and fresh hards late, so `compound_pace_gaps` mixes tyre pace
with fuel and track evolution. Here each race gets lap_time ~ driver + lap + compound + age
per compound: lap effects absorb fuel and track, with no fuel constant. Intervals bootstrap
over drivers. A race is flagged only if a gap is backwards with its whole interval below 0.
"""

import numpy as np
import pandas as pd

from pitwall.cleaning import FLAG_COLUMNS
from pitwall.data import REPO_ROOT
from pitwall.openf1 import MissingTable, race_calendar
from pitwall.quality import COMPOUND_PAIRS, MIN_PAIRED_DRIVERS, flag_race

YEARS = [2023, 2024]
DRY_COMPOUNDS = ["SOFT", "MEDIUM", "HARD"]
SWAP = {"SOFT": "HARD", "HARD": "SOFT"}
BOOTSTRAP_DRAWS = 200


def design_matrix(flagged: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    excluded = flagged[[*FLAG_COLUMNS, "is_rain_reported"]].any(axis=1)
    usable = ~excluded & flagged["LapTimeSeconds"].notna()
    laps = flagged[usable & flagged["Compound"].isin(DRY_COMPOUNDS)]
    drivers = laps.groupby("Compound")["DriverNumber"].nunique()
    compounds = [c for c in DRY_COMPOUNDS if drivers.get(c, 0) >= MIN_PAIRED_DRIVERS]
    laps = laps[laps["Compound"].isin(compounds)]

    tyres = {}
    for compound in compounds:
        on_compound = (laps["Compound"] == compound).astype(float)
        if compound != compounds[-1]:
            tyres[f"compound_{compound}"] = on_compound
        tyres[f"age_{compound}"] = on_compound * (laps["TyreLife"] - 1)
    columns = [
        pd.get_dummies(laps["DriverNumber"], dtype=float),
        pd.get_dummies(laps["LapNumber"], dtype=float, drop_first=True),
        pd.DataFrame(tyres, index=laps.index),
    ]
    design = pd.concat(columns, axis=1)
    design.columns = design.columns.astype(str)
    return laps, design, compounds


def pair_gaps(beta: np.ndarray, names: list[str], compounds: list[str]) -> dict[str, float]:
    effect = {
        compound: beta[names.index(f"compound_{compound}")]
        if f"compound_{compound}" in names
        else 0.0
        for compound in compounds
    }
    return {
        f"{softer}<{harder}": effect[harder] - effect[softer]
        for softer, harder in COMPOUND_PAIRS
        if softer in effect and harder in effect
    }


def same_lap_gaps(flagged: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame | None:
    laps, design, compounds = design_matrix(flagged)
    if len(compounds) < 2:
        return None
    names = list(design.columns)
    x, y = design.to_numpy(), laps["LapTimeSeconds"].to_numpy()
    point = pair_gaps(np.linalg.lstsq(x, y, rcond=None)[0], names, compounds)

    numbers = laps["DriverNumber"].reset_index(drop=True)
    unique = numbers.unique()
    draws = []
    for _ in range(BOOTSTRAP_DRAWS):
        counts = pd.Series(rng.choice(unique, len(unique))).value_counts()
        weight = np.sqrt(numbers.map(counts).fillna(0).to_numpy())
        beta = np.linalg.lstsq(x * weight[:, None], y * weight, rcond=None)[0]
        draws.append(pair_gaps(beta, names, compounds))
    draws = pd.DataFrame(draws)
    return pd.DataFrame(
        {
            "Gap": point,
            "Low": draws.quantile(0.025),
            "High": draws.quantile(0.975),
        }
    )


def verdict(gaps: pd.DataFrame | None) -> str:
    if gaps is None:
        return "untestable"
    return "broken" if (gaps["High"] < 0).any() else "ok"


def main() -> None:
    rng = np.random.default_rng(0)
    rows, pooled = [], []
    for year in YEARS:
        for race in race_calendar(year).itertuples():
            try:
                flagged = flag_race(race.SessionKey)
            except MissingTable:
                continue
            gaps = same_lap_gaps(flagged, rng)
            swapped = flagged.assign(Compound=flagged["Compound"].replace(SWAP))
            rows.append(
                {
                    "Year": year,
                    "Round": race.Round,
                    "Race": race.Race,
                    "Same lap": verdict(gaps),
                    "Swap": verdict(same_lap_gaps(swapped, rng)),
                    "Gaps": ""
                    if gaps is None
                    else "; ".join(
                        f"{pair} {row.Gap:+.2f} [{row.Low:+.2f}, {row.High:+.2f}]"
                        for pair, row in gaps.iterrows()
                    ),
                }
            )
            if gaps is not None:
                pooled.append(gaps["Gap"].rename(f"{year} {race.Race}"))

    table = pd.DataFrame(rows)
    table.to_csv(REPO_ROOT / "notes" / "compound_pace_same_lap.csv", index=False)
    print("same lap:", table["Same lap"].value_counts().to_dict())
    print("swap:", table["Swap"].value_counts().to_dict())
    print(table.loc[table["Same lap"] == "broken", ["Year", "Race", "Gaps"]].to_string(index=False))

    by_pair = pd.DataFrame(pooled)
    summary = pd.DataFrame(
        {
            "Races": by_pair.count(),
            "Median gap": by_pair.median(),
            "Share positive": (by_pair > 0).sum() / by_pair.count(),
        }
    )
    print(summary.round(2).to_string())


if __name__ == "__main__":
    main()
