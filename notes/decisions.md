# Decisions

## 2026-11-05: OpenF1 + Jolpica as a stopgap for FastF1

FastF1 now needs a paid F1TV subscription. OpenF1 covers what Phase 0 needs without a
login, and lap times check out against Jolpica. Confirmed as the data source on 2026-11-05.
Raw pulls are cached as parquet so we don't depend on the APIs staying open.

## 2026-11-05: Colour compounds red / yellow / blue

Hard is conventionally white, which vanishes on a light background, and grey failed the
palette chroma check. Marker shape also encodes compound, so colour isn't the only cue.

## 2026-11-05: One boolean column per cleaning rule

`flag_laps` adds `is_lap1`, `is_inlap`, `is_outlap`, `is_sc_vsc_red`, `is_slow_outlier`,
`is_blue_flag` and `is_wet`. There is no single drop flag and no row is removed, so each model
picks its own exclusions. Pit data is never filtered, so stops under SC/VSC stay in it.

- `is_sc_vsc_red` covers laps overlapping a neutralised period, plus the lap after.
- `is_slow_outlier` compares a lap to the 5-lap rolling median of its own stint, using only
  laps not already flagged as lap 1, pit or neutralised. The threshold defaults to 1.5s.
- Fast outliers are kept, and there is no 107% rule.
