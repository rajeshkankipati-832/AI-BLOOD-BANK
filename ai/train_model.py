"""Train and save a model from generated demonstration data."""
from pathlib import Path
import joblib
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error
from sklearn.model_selection import train_test_split

from ai.generate_dataset import generate_dataset
from ai.preprocessing import prepare_training_data

MODEL_PATH = Path(__file__).resolve().parent / "model" / "demand_model.joblib"


def train_model(output=MODEL_PATH):
    x, y = prepare_training_data(generate_dataset())
    x_train, x_test, y_train, y_test = train_test_split(x, y, test_size=.2, random_state=42)
    model = RandomForestRegressor(n_estimators=120, random_state=42, min_samples_leaf=3)
    model.fit(x_train, y_train)
    metrics = {"mae": float(mean_absolute_error(y_test, model.predict(x_test))),
               "training_rows": len(x_train), "test_rows": len(x_test), "synthetic": True}
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"model": model, "metrics": metrics}, output)
    return metrics


if __name__ == "__main__":
    print(train_model())
