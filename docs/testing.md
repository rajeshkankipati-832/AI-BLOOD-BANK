# Testing

Run `python -m pytest -q` after installing `requirements.txt`. The Flask workflow tests use `mongomock`, an isolated in-memory MongoDB-compatible fixture; they do not connect to the configured database. Prediction tests check input validation, deterministic data generation, preprocessing, and output labeling. The current suite reports 15 passing tests.

`python test_mongodb.py` performs a read-only ping against the configured MongoDB server. It reports a failing exit code when the database is unavailable. During this update, the configured MongoDB responded to the ping, the Flask development server started, and `/`, `/login`, `/signup`, and `/health` returned HTTP 200. The route smoke test also rendered authenticated user/admin pages against the real database without inserting or deleting app records. Manual presentation flows can be exercised with one administrator created through `python create_admin.py` and a normal account created from the signup form.

Do not use the synthetic AI demo as evidence of production forecasting accuracy. No real request history dataset is included in this repository.
