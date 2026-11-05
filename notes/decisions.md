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

## 2026-11-05: Quarantine failing races, correct only the off-by-one

Every race goes through `audit_race`, and `load_model_laps` raises `QuarantinedRace` if it
fails. Stops must match Jolpica exactly. Each stint boundary is compared to its own stop: a gap
of 0 is fine, a gap of exactly 1 is corrected and logged, anything else fails the whole race.
Races without a pit table are quarantined, even where `stints` alone match Jolpica.

## 2026-11-05: Compound pace checks flag, they don't quarantine

The fresh-tyre check was specified to flag races for a decision on an F1TV cross-check. It
stays as specified, and `scripts/compound_pace_same_lap.py` was added because its flags turned
out to be timing bias. Neither gates modelling.

## 2026-11-05: Split wetness into two flags

`is_wet` is inter/wet compound only and is meant for dry-model exclusion. `is_rain_reported`
needs 2 consecutive rain samples, is listed in `INFO_COLUMNS` and isn't excluded by default.
