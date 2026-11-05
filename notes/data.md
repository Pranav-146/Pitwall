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

Every raw pull from both APIs is stored as parquet in `data/raw/` (gitignored), so a race
only needs the APIs once.

## Fields in `load_laps`

| Column | Notes |
|---|---|
| Driver, DriverNumber, Team | from OpenF1 `drivers` |
| LapNumber | 1-based |
| LapTimeSeconds | OpenF1 `lap_duration`; lap 1 runs long, see below. Null on some laps |
| LapStart | UTC; null on some lap 1s |
| Stint, Compound | from OpenF1 `stints`, boundaries checked against `pit` by `snap_stints_to_pits` |
| TyreLife | `tyre_age_at_start + laps into stint`, so a new tyre reads 1 on its first lap |
| PitIn | lap number appears in OpenF1 `pit` |
| PitOut | OpenF1 `is_pit_out_lap`, raw |

## Quirks

- **Lap 1 runs about +0.4s long against Jolpica, for every driver.** Every other lap agrees
  within 0.01s. Means: Bahrain +0.416s, Saudi +0.437s, Canada +0.445s, Spain +0.423s.
  Range across the four races: +0.230 to +0.561s. Summed laps overshoot official race time
  by a similar amount.
- **No track status field.** SC/VSC/red come from `race_control` messages.
- **`race_control` lap numbers follow the leader**, so they can be wrong for lapped cars.
  Flags are matched to laps by timestamp instead.
- **`CHEQUERED` contains "RED"**, so red flags must match `flag == "RED"` exactly.
- **A red flag ends at `SESSION STARTED`**, not at a green flag. Monaco, Japan and Brazil
  2024 have no green flag message at the restart.
- **A VSC can have no end message**: it may become an SC (China) or run to the flag
  (Australia, Baku). `neutralised_periods` handles both.
- **Lap timestamps break around lap 1 red flags.** In Japan, lap 1 `date_start` is after
  lap 2, and lap 2 lasts 1711s. In Monaco, lap 1 starts at the restart. As a result, lap 1
  pit rows in Japan aren't matched to the red flag, though `is_lap1` covers those laps and
  the pit rows are kept.
- **Retiring drivers' final partial lap has no lap time and no stint row.** `load_laps`
  extends their last stint to cover it, since they are still on those tyres.
- **`is_pit_out_lap` is true on lap 1 for all 20 cars in Canada.** `is_outlap` ignores lap 1.
- **`race_control` and `weather` are per session.** Filtering by `driver_number` returns
  "No results found", which looks like missing data but isn't.
- **`pit` has `lane_duration`, but stationary time (`stop_duration`) can be null.**
- **Compound names are relative.** SOFT means a different Pirelli compound at different
  tracks, which matters for the cross-race model in Phase 1.
- **Sector 1 and speed trap fields are often null.**
- **OpenF1 has no `pit` table for 2023 rounds 1-6.** It answers 404 "No results found".
- **OpenF1 lists the cancelled 2023 Imola race**, with `is_cancelled` set. `race_calendar`
  drops it and joins to Jolpica rounds by order, because Las Vegas 2024 is dated a day apart.
- **`stints` can run past the race.** Belgium 2024 has a lap 45 stint for 4 cars in a 44-lap
  race. Qatar 2024 has an `UNKNOWN` first stint and a phantom second for 2 lap-1 retirements.

## Tyre data verification

`scripts/audit_races.py` now runs this on every race, and `load_model_laps` refuses a race
that fails. Results are in `RESULTS.md` and `race_audit.csv`. The table below is the original
4-race check of raw data, from `scripts/verify_tyres.py`. Pit laps are compared against Jolpica,
an independent source. Saudi was required for its safety car, Spain is a dry race with all three compounds,
and Canada exercises the wet path.

| Check | Bahrain | Saudi | Spain | Canada |
|---|---|---|---|---|
| OpenF1 pit laps match Jolpica | 43/43 | 19/19 | 42/42 | 42/42 |
| OpenF1 stint ends match Jolpica | 43/43 | 19/19 | 42/42 | **1/42** |
| Stint boundaries match pit laps | ok | ok | ok | **82 mismatches** |
| Stint starts match out-laps | ok | ok | ok | **102 mismatches** |
| Every finisher used 2+ compounds | ok | ok | ok | wet, not required |
| Start ages sane (0 to 10 laps) | 0-3 | 0-6 | 0-3 | 0-1 |
| Stints cover every lap | ok | 2 retirements | ok | 5 retirements |

### Mismatch log

- **One lap early stints:** Canada 2023 (31 stops), Australia 2024 (36), Monaco 2024 (23),
  Canada 2024 (41). `pit` agrees with Jolpica on all of them, so `stints` is the wrong table.
  The in-lap got the next stint's compound and TyreLife reset a lap early. Corrected in
  `load_laps`, and every correction is in `stint_corrections.csv`. Canada 2024's 82 and 102
  counts above are this one fault counted from both sides, plus lap 1 in the out-lap check.
- **Canada 2023:** Tsunoda has a stint break on lap 2 with no stop, and a lap 34 stop with no
  stint break. Not the known pattern, so the race is quarantined.
- **Saudi 2024:** GAS and STR have a final partial lap outside any stint.
- **Canada 2024:** SAR, PER, LEC, ALB and SAI have the same retirement gap.
- **Spain 2024:** a single `rainfall=1` weather sample at 13:06:38 in a race run entirely on
  slicks. `is_rain_reported` now needs 2 consecutive samples, so this no longer flags any lap.
- **Bahrain 2024:** a [race report](https://lastwordonsports.com/motorsports/?p=18819) has
  Sargeant stopping first on lap 12. OpenF1 has Hulkenberg on lap 1 and Sargeant on lap 10,
  and Jolpica matches OpenF1 on all 43 stops, so the report looks wrong.

### What this does not prove

Jolpica confirms when tyres changed, not which tyres went on. Compound labels are covered by
the two-compound rule in dry races, plus the Bahrain race report. The pace-order checks can't
verify them race by race (see `RESULTS.md`). Used-set ages aren't part of the audit: across all 2659
stints none is negative and 11 start over 10 laps old, 5 of them inters at Dutch 2023. The oldest
is Leclerc on a 25-lap hard at Spain 2023, which is unverified. An error on a single stint would
pass everything here.
