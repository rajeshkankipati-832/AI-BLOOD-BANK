# Application architecture

## User and inventory workflows

```text
Browser (Jinja templates, CSS, Bootstrap)
                 |
       Flask route handlers
                 |
  Services (auth, stock decisions, prediction)
                 |
      MongoDB client factory
                 |
      Existing collections
```

`app.py` remains the Flask entry point and owns the original user/admin route handlers. The `/health` endpoint is a separate blueprint in `routes/health_routes.py`. Authentication and legacy hash migration live in `services/auth_service.py`; stock review logic is in `services/inventory_service.py`; model orchestration is in `services/prediction_service.py`. `mongodb.py` creates clients, and optional non-unique indexes are created explicitly with `python -m database.ensure_indexes`. Jinja templates render the records. Existing collection names and data are retained.

## Prediction demonstration

```text
Prediction form -> Flask prediction handler -> prediction service
      -> synthetic data generator/preprocessing -> trained scikit-learn model
      -> labeled estimate -> predictions collection
```

Training data is generated deterministically from a simulation and is not observed blood bank data. The estimate is marked as a demonstration, not a validated operational or clinical forecast. Training metrics are measured on a held-out synthetic split.

## Security boundaries

Normal users can read inventory, submit requests, see their own request history, and edit their own donor profile. Administrator routes control stock, request decisions, user roles, donors, and hospitals. Password hashes use Werkzeug's password hashing functions; old plaintext values are upgraded after a valid login. Session secret, MongoDB URI, and database name are configured through environment variables.
