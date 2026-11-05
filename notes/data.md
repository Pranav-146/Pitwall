# Data notes

## Sources (as of 2026-11-05)

| Source | Used for | Access |
|---|---|---|
| OpenF1 | laps, stints, pit stops, weather, race control | public, no login |
| Jolpica (Ergast successor) | official results, independent lap times | public, no login |
| FastF1 3.9.2 | intended primary source, currently unusable | needs active F1TV subscription |

**FastF1 is blocked.** `livetiming.formula1.com` returns 401 without a token, and FastF1's
sign-in needs an active F1TV subscription. Its mirror fallback 404s for 2024 Bahrain.
FastF1 still logs "Finished loading data for 20 drivers" after every endpoint fails, so
`pitwall.data.load_race` touches `session.laps` to fail loudly.

`pitwall.openf1.load_laps` returns FastF1-style column names to keep a later swap cheap.

## Fields in `load_laps`

| Column | Notes |
|---|---|
| Driver, DriverNumber, Team | from OpenF1 `drivers` |
| LapNumber | 1-based |
| LapTimeSeconds | OpenF1 `lap_duration`; lap 1 runs long, see below |
| Stint, Compound | from OpenF1 `stints`, joined on lap range |
| TyreLife | `tyre_age_at_start + laps into stint`, so a new tyre reads 1 on its first lap |
| PitIn | lap number appears in OpenF1 `pit` |
| PitOut | OpenF1 `is_pit_out_lap` |

## Quirks, measured on 2024 Bahrain

- **Lap 1 is 0.32-0.51s longer than Jolpica for all 20 drivers (mean 0.42s).** Every other
  lap agrees within 0.01s. Summed laps overshoot official race time by a similar amount.
- **No track status field.** SC/VSC must be derived from `race_control`. This race had no
  SC, VSC or red flag, so that logic can't be tested here.
- **`race_control` and `weather` are per session.** Filtering by `driver_number` returns
  "No results found", which looks like missing data but isn't.
- **`pit` has `lane_duration`, but stationary time (`stop_duration`) can be null.**
- **Tyre age only takes a few values:** stint 1 is 0 or 3 here. Treat used-set ages as
  approximate until checked elsewhere.
- **Compound names are relative.** SOFT means a different Pirelli compound at different
  tracks, which matters for the cross-race model in Phase 1.
- **Sector 1 is null on 2 laps; speed traps are often null** (`i1_speed` 300, `st_speed` 170).

## Tyre data verification

Jolpica has no tyre data, so the lap time match says nothing about compounds.
A [2024 race report](https://lastwordonsports.com/motorsports/?p=18819) agrees with OpenF1
that all 20 started on soft, half on used sets, Hulkenberg on a fresh set, Red Bull took
softs at the second stop, and Sainz finished on hards.

Not verified: most per-driver sequences, exact used-set ages, and any race but this one.
One conflict: the report has Sargeant stopping first on lap 12, while OpenF1 has Hulkenberg
on lap 1, then Stroll and Zhou on lap 9, and Sargeant on lap 10.
