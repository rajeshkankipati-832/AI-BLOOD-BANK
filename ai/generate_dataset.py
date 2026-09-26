"""Generate explicitly synthetic records for demonstrating model training."""
from pathlib import Path
import numpy as np
import pandas as pd


def generate_dataset(output=None, rows=1200, seed=42):
    rng = np.random.default_rng(seed)
    months = rng.integers(1, 13, size=rows)
    group_index = rng.integers(0, 8, size=rows)
    # Generated quantities are simulated and must not be treated as clinical forecasts.
    seasonal = 1.0 + 0.25 * np.sin((months - 1) * (2 * np.pi / 12))
    group_factor = np.array([1.2, .35, 1.0, .3, .45, .12, 1.5, .25])[group_index]
    demand = rng.poisson(18 * seasonal * group_factor).clip(0, 80)
    frame = pd.DataFrame({"month": months, "blood_group_index": group_index, "demand_units": demand})
    if output:
        target = Path(output)
        target.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(target, index=False)
    return frame


if __name__ == "__main__":
    path = Path(__file__).resolve().parent / "data" / "synthetic_demand.csv"
    generate_dataset(path)
    print(f"Wrote synthetic demonstration data to {path}")
