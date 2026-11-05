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
