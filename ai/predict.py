"""Prediction helpers for clearly labeled synthetic demo forecasts."""
from datetime import datetime, timezone
from pathlib import Path
import joblib
import pandas as pd

from config import Config
from ai.train_model import MODEL_PATH, train_model


def _model_bundle():
    if not MODEL_PATH.exists():
        train_model(output=MODEL_PATH)
    return joblib.load(MODEL_PATH)


def predict_demand(request_records, blood_group, now=None):
    if blood_group not in Config.BLOOD_GROUPS:
        raise ValueError("Unsupported blood group")
    now = now or datetime.now(timezone.utc)
    group_index = Config.BLOOD_GROUPS.index(blood_group)
    bundle = _model_bundle()
    estimate = max(0, int(round(bundle["model"].predict(pd.DataFrame(
        [{"month": now.month, "blood_group_index": group_index}]))[0])))
    month_count = sum(1 for record in request_records
                      if isinstance(record.get("created_at"), datetime)
                      and record["created_at"].year == now.year and record["created_at"].month == now.month)
    return {"estimated_units": estimate, "observed_requests_this_month": month_count,
            "model_mae": round(bundle["metrics"]["mae"], 2), "model_basis": "synthetic demonstration data",
            "notice": "Educational demo only; not a validated operational or clinical forecast."}
