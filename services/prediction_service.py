"""Prediction orchestration for the clearly labeled synthetic-data model."""
from ai.predict import predict_demand


def predict_group_demand(request_records, blood_group):
    return predict_demand(request_records, blood_group)
