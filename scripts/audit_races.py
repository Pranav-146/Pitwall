"""Audit every 2023-24 race and write the results to notes/.

Per race: pit stops vs Jolpica, stint boundaries vs pit stops, compound labels, and whether
fresh-tyre pace runs soft < medium < hard. The pace check is then tested on deliberately
swapped labels, because a check that can't fail proves nothing.
"""

import pandas as pd

from pitwall.data import REPO_ROOT
from pitwall.openf1 import MissingTable
from pitwall.quality import audit_season, compound_pace_gaps, flag_race, pace_order_verdict

YEARS = [2023, 2024]
FUEL_EFFECTS = [2.0, 3.0, 4.0]
SWAP = {"SOFT": "HARD", "HARD": "SOFT"}


def pace_check(session_key: int) -> dict:
    try:
        flagged = flag_race(session_key)
    except MissingTable:
        return {"Pace order": "not tested", "Pace gaps": ""}

    gaps = compound_pace_gaps(flagged)
    verdicts = [
        pace_order_verdict(compound_pace_gaps(flagged, fuel_effect=effect))
        for effect in FUEL_EFFECTS
    ]
    swapped = flagged.assign(Compound=flagged["Compound"].replace(SWAP))
    row = {
        "Pace order": pace_order_verdict(gaps),
        "Pace gaps": "; ".join(
            f"{r.Pair} {r.GapSeconds:+.2f}s (n={r.Drivers})"
            for r in gaps.itertuples()
            if r.Drivers
        ),
        "Broken at fuel 2/3/4s": sum(verdict == "broken" for verdict in verdicts),
        "Swap caught": pace_order_verdict(compound_pace_gaps(swapped)),
        "Laps": len(flagged),
        "Wet laps": int(flagged["is_wet"].sum()),
        "Rain reported laps": int(flagged["is_rain_reported"].sum()),
        "Rain on slicks": int((flagged["is_rain_reported"] & ~flagged["is_wet"]).sum()),
    }
    return row


def main() -> None:
    pd.set_option("display.width", 240, "display.max_rows", 100, "display.max_colwidth", 90)
    pd.set_option("display.max_columns", 30)
    rows, corrections = [], []
    for year in YEARS:
        for audit in audit_season(year):
            rows.append(
                {
                    "Year": audit.year,
                    "Round": audit.round_number,
                    "Race": audit.race,
                    "SessionKey": audit.session_key,
                    "Status": audit.status,
                    "Stops": audit.stops,
                    "Corrections": len(audit.corrections),
                    "Reasons": " | ".join(audit.reasons),
                    **pace_check(audit.session_key),
                }
            )
            corrections += [
                {"Year": audit.year, "Round": audit.round_number, "Race": audit.race, **fix}
                for fix in audit.corrections
            ]

    table = pd.DataFrame(rows)
    table.to_csv(REPO_ROOT / "notes" / "race_audit.csv", index=False)
    pd.DataFrame(corrections).to_csv(REPO_ROOT / "notes" / "stint_corrections.csv", index=False)

    print(table.drop(columns=["SessionKey", "Reasons", "Pace gaps"]).to_string(index=False))
    print("\nstatus:", table["Status"].value_counts().to_dict())
    print("pace order:", table["Pace order"].value_counts().to_dict())
    print("corrections:", len(corrections))
    print("\nquarantined:")
    quarantined = table[table["Status"] == "quarantined"]
    print(quarantined[["Year", "Race", "Reasons"]].to_string(index=False))
    print("\npace order broken:")
    broken = table[table["Pace order"] == "broken"]
    print(broken[["Year", "Race", "Status", "Wet laps", "Pace gaps"]].to_string(index=False))


if __name__ == "__main__":
    main()
