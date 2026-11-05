# Results log

Every metric, with date and setup.

## 2026-11-05: OpenF1 data check, 2024 Bahrain GP

Setup: OpenF1 session 9472 vs Jolpica round 1, `scripts/validate_openf1.py`, no cleaning.

| Metric | Value |
|---|---|
| Driver-laps matched between sources | 1129 / 1129 |
| Laps differing by more than 0.01s | 20 (all lap 1) |
| Lap 1 excess over Jolpica | 0.32-0.51s, mean 0.42s |
| Top 5 summed laps minus official race time | +0.41 to +0.48s |

## 2026-11-05: Tyre data verification, 4 races

Setup: OpenF1 stints and pit data vs Jolpica pit stops, `scripts/verify_tyres.py`.

| Race | Stops | Pit table matches | Stint ends match | Lap 1 excess, mean |
|---|---|---|---|---|
| Bahrain | 43 | 43 | 43 | +0.416s |
| Saudi Arabia | 19 | 19 | 19 | +0.437s |
| Canada | 42 | 42 | **1** | +0.445s |
| Spain | 42 | 42 | 42 | +0.423s |

## 2026-11-05: Lap flags, 9 races

Setup: `flag_laps` defaults (5-lap rolling median within stint, 1.5s threshold),
`scripts/report_flags.py`. Flags overlap, so columns don't sum to Any flag.

| Race | Laps | lap1 | in | out | SC/VSC/red | slow | blue | wet | Any flag |
|---|---|---|---|---|---|---|---|---|---|
| Bahrain | 1129 | 20 | 43 | 43 | 0 | 8 | 24 | 0 | 127 |
| Saudi Arabia | 902 | 20 | 19 | 19 | 72 | 13 | 7 | 0 | 118 |
| Australia | 998 | 19 | 36 | 36 | 68 | 18 | 25 | 0 | 183 |
| Japan | 908 | 20 | 54 | 54 | 36 | 16 | 19 | 0 | 155 |
| China | 1033 | 20 | 40 | 40 | 219 | 2 | 0 | 0 | 285 |
| Monaco | 1237 | 20 | 23 | 23 | 0 | 46 | 44 | 0 | 116 |
| Canada | 1272 | 20 | 42 | 42 | 196 | 75 | 8 | 832 | 993 |
| Spain | 1310 | 20 | 42 | 42 | 0 | 30 | 54 | 20 | 187 |
| Brazil | 1137 | 19 | 35 | 35 | 212 | 36 | 1 | 1137 | 1137 |

Monaco shows 0 for SC/VSC/red because its red flag came on lap 1 and timing restarts after
it. Those laps are covered by `is_lap1`.

### Slow outlier threshold sensitivity

| Race | > 1.0s | > 1.5s | > 2.0s |
|---|---|---|---|
| Bahrain | 22 | 8 | 3 |
| Saudi Arabia | 28 | 13 | 4 |
| Australia | 30 | 18 | 10 |
| Japan | 36 | 16 | 7 |
| China | 12 | 2 | 1 |
| Monaco | 68 | 46 | 35 |
| Canada | 110 | 75 | 47 |
| Spain | 49 | 30 | 12 |
| Brazil | 53 | 36 | 25 |

### SC/VSC/red validation

Median lap time on flagged laps as a multiple of each driver's normal pace.

| Race | Tests | Result |
|---|---|---|
| Saudi Arabia | SC | laps 7-9: 1.37x, 1.89x, 1.60x; restart lap 10: 1.04x |
| Australia | VSC, VSC to the flag | lap 17: 1.26x; laps 57-58: 1.29x, 1.38x |
| China | VSC becoming SC, second SC | laps 22-31: 1.13x to 1.48x; lap 32: 1.00x |
| Japan | Red flag on lap 1 | laps 2-3: 17.6x, 1.58x |
| Brazil | VSC, SC into red flag, SC | 3 periods; lap 33: 18.2x |

Laps over 15% slower than normal and not explained by lap 1, pits, neutralisation or rain:
0 in all 9 races. Rain laps are excluded from this check, so it says little about Canada
and nothing about Brazil, where every lap is `is_wet`. Saudi has no VSC or red flag, so those
paths were validated on the races above.

Pit rows kept under neutralisation: Saudi 14 of 19, China 18 of 40, Canada 21 of 42,
Brazil 32 of 35, Australia 4 of 36.

## 2026-11-05: Data quality audit, all 46 races of 2023-24

Setup: `scripts/audit_races.py`, full output in `notes/race_audit.csv`. Every stop checked
against Jolpica, every stint boundary against its stop. Only a boundary exactly one lap before
its stop is corrected, each one logged in `notes/stint_corrections.csv`. Anything else
quarantines the whole race.

| Metric | Value |
|---|---|
| Races audited | 46 |
| Pass | 34 |
| Corrected (off-by-one only) | 3 |
| Quarantined | 9 |
| Usable races | 37 |
| Usable laps | 41,377 |
| Pit table stops matching Jolpica | 1518 / 1518, over the 40 races with a pit table |
| Corrections | 131 (100 in usable races, 31 in quarantined Canada 2023) |

| Year | Round | Race | Status | Stops | Corrections | Quarantine reason |
|---|---|---|---|---|---|---|
| 2023 | 1 | Bahrain | quarantined | 50 | 0 | No OpenF1 pit table |
| 2023 | 2 | Saudi Arabian | quarantined | 24 | 0 | No OpenF1 pit table |
| 2023 | 3 | Australian | quarantined | 65 | 0 | No OpenF1 pit table |
| 2023 | 4 | Azerbaijan | quarantined | 23 | 0 | No OpenF1 pit table |
| 2023 | 5 | Miami | quarantined | 20 | 0 | No OpenF1 pit table |
| 2023 | 6 | Monaco | quarantined | 37 | 0 | No OpenF1 pit table |
| 2023 | 7 | Spanish | pass | 43 | 0 |  |
| 2023 | 8 | Canadian | quarantined | 33 | 31 | Car 22: stint break with no stop, and a stop with no stint break |
| 2023 | 9 | Austrian | pass | 63 | 0 |  |
| 2023 | 10 | British | pass | 24 | 0 |  |
| 2023 | 11 | Hungarian | pass | 36 | 0 |  |
| 2023 | 12 | Belgian | pass | 37 | 0 |  |
| 2023 | 13 | Dutch | pass | 101 | 0 |  |
| 2023 | 14 | Italian | pass | 25 | 0 |  |
| 2023 | 15 | Singapore | pass | 25 | 0 |  |
| 2023 | 16 | Japanese | pass | 43 | 0 |  |
| 2023 | 17 | Qatar | pass | 54 | 0 |  |
| 2023 | 18 | United States | pass | 36 | 0 |  |
| 2023 | 19 | Mexico City | pass | 38 | 0 |  |
| 2023 | 20 | São Paulo | pass | 67 | 0 |  |
| 2023 | 21 | Las Vegas | pass | 31 | 0 |  |
| 2023 | 22 | Abu Dhabi | pass | 37 | 0 |  |
| 2024 | 1 | Bahrain | pass | 43 | 0 |  |
| 2024 | 2 | Saudi Arabian | pass | 19 | 0 |  |
| 2024 | 3 | Australian | corrected | 36 | 36 |  |
| 2024 | 4 | Japanese | pass | 54 | 0 |  |
| 2024 | 5 | Chinese | pass | 40 | 0 |  |
| 2024 | 6 | Miami | pass | 28 | 0 |  |
| 2024 | 7 | Emilia Romagna | pass | 27 | 0 |  |
| 2024 | 8 | Monaco | corrected | 23 | 23 |  |
| 2024 | 9 | Canadian | corrected | 42 | 41 |  |
| 2024 | 10 | Spanish | pass | 42 | 0 |  |
| 2024 | 11 | Austrian | pass | 45 | 0 |  |
| 2024 | 12 | British | pass | 45 | 0 |  |
| 2024 | 13 | Hungarian | pass | 40 | 0 |  |
| 2024 | 14 | Belgian | quarantined | 34 | 0 | 4 cars: phantom stint on lap 45 of 44 |
| 2024 | 15 | Dutch | pass | 26 | 0 |  |
| 2024 | 16 | Italian | pass | 30 | 0 |  |
| 2024 | 17 | Azerbaijan | pass | 22 | 0 |  |
| 2024 | 18 | Singapore | pass | 23 | 0 |  |
| 2024 | 19 | United States | pass | 23 | 0 |  |
| 2024 | 20 | Mexico City | pass | 21 | 0 |  |
| 2024 | 21 | São Paulo | pass | 35 | 0 |  |
| 2024 | 22 | Las Vegas | pass | 39 | 0 |  |
| 2024 | 23 | Qatar | quarantined | 60 | 0 | 2 lap-1 retirements: UNKNOWN compound, phantom stint |
| 2024 | 24 | Abu Dhabi | pass | 28 | 0 |  |

## 2026-11-05: Compound pace ordering, 2023-24

Fresh-tyre check: `compound_pace_gaps`, laps with TyreLife up to 8, within-driver medians, 3s
total fuel effect, a pair needs 3 drivers. Same-lap check: `scripts/compound_pace_same_lap.py`,
lap_time ~ driver + lap + compound + age per compound, 95% bootstrap over drivers, flagged only
if the whole interval is backwards. Swap test: SOFT and HARD labels exchanged across the race.

| Check | Races tested | Flagged | Swapped labels flagged |
|---|---|---|---|
| Fresh-tyre, fuel corrected | 38 | 24 | 20 of 38 |
| Same-lap regression | 39 | 1 (Qatar 2023) | 6 of 39 |

Fresh-tyre flags are not label errors. In 18 of the 24 flagged races the swapped labels pass
the check, so wrong labels look better than real ones. Fresh mediums sit about 19% into a
race on average and fresh hards 41%, so the check mostly measures when each tyre ran. 16 races stay flagged
at fuel effects of 2, 3 and 4s; 31 are flagged at one or more of them. Bahrain 2024 is flagged
despite its stops and compounds being checked.

The same-lap check removes that bias but has little power, so its 38 passes prove little.
Pooled over races, same-lap gaps have the right sign but are small:

| Pair | Races | Median gap | Share positive |
|---|---|---|---|
| Soft faster than medium | 21 | +0.03s | 52% |
| Medium faster than hard | 35 | +0.12s | 66% |
| Soft faster than hard | 19 | +0.10s | 63% |

Neither check verifies compound labels race by race.

## 2026-11-05: Wetness flags split, 9 races

`is_wet` is inter/wet compound only. `is_rain_reported` needs 2 consecutive rain samples and is
informational. Replaces the `is_wet` column in the 9-race table above, and that table's Canada
and Australia and Monaco rows predate the stint correction.

| Race | Laps | is_wet | is_rain_reported | Any flag |
|---|---|---|---|---|
| Spain 2024 | 1310 | 0 (was 20) | 0 | 167 (was 187) |
| Canada 2024 | 1272 | 846 (was 832) | 342 | 992 (was 993) |
| Brazil 2024 | 1137 | 1137 | 848 | 1137 |

Canada has 827 inter/wet laps on raw stints and 846 after correction, since in-laps get their
own tyres back. Other flag counts in the 9 races did not change.

Rain-reported laps on slicks stay in the dry model by default: 451 in usable races (British
2024 193, Dutch 2023 150, Belgian 2023 105, Canadian 2024 3).
