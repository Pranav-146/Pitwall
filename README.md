# Pitwall

Data-driven F1 race strategy simulator. Work in progress, currently in Phase 0 (data
exploration). See [RESULTS.md](RESULTS.md) for metrics and [notes/](notes/) for data quirks.

## Setup

```
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/python -m pip install -e .
.venv/Scripts/python scripts/phase0_stint_pace.py
```

![Stint pace](figures/phase0_stint_pace_bahrain_2024.png)
