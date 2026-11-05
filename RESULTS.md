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
