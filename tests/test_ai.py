from datetime import datetime, timezone

import pandas as pd
import pytest

from ai.preprocessing import prepare_training_data
from ai.generate_dataset import generate_dataset
from ai.predict import predict_demand


def test_generated_dataset_is_reproducible_and_preprocessable():
    first = generate_dataset(rows=100, seed=9)
    second = generate_dataset(rows=100, seed=9)
    pd.testing.assert_frame_equal(first, second)
    x, y = prepare_training_data(first)
    assert len(x) == len(y) == 100
    assert set(x.columns) == {"month", "blood_group_index"}


def test_preprocessing_rejects_missing_columns():
    with pytest.raises(ValueError, match="missing columns"):
        prepare_training_data(pd.DataFrame({"month": [1]}))


def test_prediction_returns_labeled_demo_result(tmp_path, monkeypatch):
    import ai.predict as prediction
    monkeypatch.setattr(prediction, "MODEL_PATH", tmp_path / "model.joblib")
    result = predict_demand([{"created_at": datetime(2026, 9, 1, tzinfo=timezone.utc)}], "O+",
                            now=datetime(2026, 9, 26, tzinfo=timezone.utc))
    assert result["estimated_units"] >= 0
    assert result["observed_requests_this_month"] == 1
    assert result["model_basis"] == "synthetic demonstration data"


def test_prediction_rejects_unknown_blood_group():
    with pytest.raises(ValueError, match="Unsupported"):
        predict_demand([], "XX")
