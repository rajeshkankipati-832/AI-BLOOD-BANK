"""Input validation and feature preparation for the demo model."""
import pandas as pd


def prepare_training_data(frame):
    required = {"month", "blood_group_index", "demand_units"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"Dataset is missing columns: {', '.join(sorted(missing))}")
    clean = frame.loc[:, sorted(required)].dropna().copy()
    clean = clean[(clean.month.between(1, 12)) & (clean.blood_group_index.between(0, 7))]
    if clean.empty:
        raise ValueError("Dataset contains no usable rows")
    x = clean[["month", "blood_group_index"]].astype(int)
    y = clean["demand_units"].clip(lower=0).astype(int)
    return x, y
