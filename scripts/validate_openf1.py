"""Cross-check OpenF1 lap data against Jolpica, an independent source."""

from pitwall.openf1 import find_race_session, load_jolpica_laps, load_laps, load_results

YEAR, COUNTRY, ROUND = 2024, "Bahrain", 1


def main() -> None:
    results = load_results(YEAR, ROUND)
    laps = load_laps(find_race_session(YEAR, COUNTRY))
    print(results[["Position", "Driver", "Team", "Status", "TotalTimeSeconds"]].head(6))

    reference = load_jolpica_laps(YEAR, ROUND).merge(results[["DriverId", "DriverNumber"]], on="DriverId")
    both = laps.merge(reference, on=["DriverNumber", "LapNumber"], how="outer", indicator=True)
    print("\nrow match:", both["_merge"].value_counts().to_dict())

    matched = both[both["_merge"] == "both"].copy()
    matched["AbsDiff"] = (matched["LapTimeSeconds"] - matched["JolpicaSeconds"]).abs()
    print("\nabs lap time diff (s):\n", matched["AbsDiff"].describe())
    print("\nlaps off by >0.01s:", (matched["AbsDiff"] > 0.01).sum())
    print(matched.nlargest(8, "AbsDiff")[["Driver", "LapNumber", "LapTimeSeconds", "JolpicaSeconds"]])

    totals = laps.groupby("DriverNumber")["LapTimeSeconds"].sum().rename("SumOfLaps")
    check = results.merge(totals, on="DriverNumber").head(5)
    check["Delta"] = check["SumOfLaps"] - check["TotalTimeSeconds"]
    print("\n", check[["Driver", "TotalTimeSeconds", "SumOfLaps", "Delta"]])

    print("\ncompounds by stint:\n", laps.groupby(["Compound", "Stint"])["Driver"].nunique())
    print("\nstarting compound:\n", laps[laps["LapNumber"] == 1]["Compound"].value_counts())
    print("\nnull counts:\n", laps.isna().sum()[lambda s: s > 0])
    print("\nPitIn laps:", laps["PitIn"].sum(), " PitOut laps:", laps["PitOut"].sum())
    normal = laps[~laps["PitIn"] & ~laps["PitOut"]]
    print(
        "median in / out / other (s):",
        laps.loc[laps["PitIn"], "LapTimeSeconds"].median(),
        laps.loc[laps["PitOut"], "LapTimeSeconds"].median(),
        normal["LapTimeSeconds"].median(),
    )


if __name__ == "__main__":
    main()
