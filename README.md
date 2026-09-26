# AI Blood Bank

## Overview

AI Blood Bank is a small Flask application for coordinating blood inventory, donor registrations, hospital listings, and blood requests. It uses MongoDB for application data and includes a machine-learning demand demo trained with generated synthetic data.

## Problem and objectives

Blood requests and stock information can be difficult to coordinate across a community. This project demonstrates a single web interface for recording stock, submitting requests, registering donors, and reviewing request status. Its objectives are to provide role-based workflows, preserve existing MongoDB records, and demonstrate a reproducible ML pipeline without presenting synthetic predictions as medical advice.

## Features

- Signup, login, logout, hashed passwords, CSRF protection, and legacy plaintext-password upgrade on successful login.
- User dashboard, inventory viewing, personal request history, request submission, donor registration, hospital directory, and prediction demo.
- Administrator dashboard, user role management, donor directory, inventory CRUD, hospital CRUD, and request approval/rejection.
- Approval checks available units and atomically decrements the matching stock document, preventing negative stock and repeat deductions.
- Friendly 400, 403, 404, database-unavailable, and 500 error pages.
- Read-only `/health` endpoint for MongoDB connectivity.

## Technology

Python 3.11+, Flask, Jinja, Bootstrap 5, PyMongo, MongoDB, pandas, NumPy, scikit-learn, and pytest. Workflow tests use `mongomock` as an isolated test database; they do not alter a developer's MongoDB records.

## Structure

```text
app.py                  Flask app factory and application routes
config.py               Environment configuration
mongodb.py              MongoDB client factory
database/               Optional non-destructive index setup
create_admin.py         Interactive administrator setup
services/               Authentication, inventory, and prediction services
routes/                 Health blueprint
ai/                     Synthetic data, preprocessing, model training/prediction
templates/              Responsive Jinja pages and shared partials
static/css/              Application styling
tests/                   AI and Flask workflow tests
docs/                    Architecture, database, and testing notes
```

The existing `app.py` stays the Flask entry point. Route handlers remain together there to preserve the original entry point and avoid a broad routing rewrite; reusable authentication, stock-decision, and prediction logic lives in services. MongoDB creation is isolated in `mongodb.py`.

## Setup

Install Python 3.11 or newer and run MongoDB locally, or set `MONGO_URI` to an available MongoDB server. From PowerShell at the repository root:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env` and set a unique, long `SECRET_KEY`. The defaults for a local MongoDB are `MONGO_URI=mongodb://127.0.0.1:27017` and `MONGO_DB=AI_Blood_Bank`. `.env` is ignored by Git and must not be committed.

## Create an administrator and start

```powershell
python create_admin.py
python app.py
```

Create the recommended non-unique query indexes once, after confirming MongoDB is available:

```powershell
python -m database.ensure_indexes
```

This command only creates indexes. It does not seed, reset, or delete application data. The email index is intentionally non-unique so existing duplicate records cannot prevent setup; signup still checks for an existing email.

The administrator utility prompts for an email and password, stores a password hash, and does not replace an existing account. No default/demo credentials are shipped. Open <http://127.0.0.1:5000> and create regular accounts through the signup page.

## User workflow

Create an account, sign in, review inventory, submit a blood request, check its status, register donor information, browse hospitals, and optionally run the synthetic demand demo. Users see only their own requests and cannot edit inventory or administer the system.

## Administrator workflow

Create/sign in with the administrator account, review the admin dashboard, manage users and donors, add/edit/delete inventory and hospitals, review requests, and approve or reject pending requests. Approval is refused when requested units exceed stock.

## AI/ML methodology

`ai.generate_dataset` creates a deterministic simulated dataset; `ai.preprocessing` validates and prepares its features; `ai.train_model` trains a Random Forest regressor and reports held-out mean absolute error; `ai.predict` loads the saved model and estimates a selected group's demand for the current month. The Flask page stores the demo result in `predictions`.

The repository contains no real, representative demand dataset. These outputs are for demonstrating a pipeline only. They are not validated for operational inventory planning, patient care, or diagnosis. Do not infer real-world performance from the synthetic test split.

Train manually with:

```powershell
python -m ai.train_model
```

The generated model and optional CSV are local artifacts and are ignored by Git; the app trains the model on first prediction if it is absent.

## Testing

```powershell
python -m pytest -q
python test_mongodb.py
```

The automated workflow tests use an in-memory Mongo-compatible fixture. `test_mongodb.py` and `/health` check the configured real MongoDB server. See [testing notes](docs/testing.md).

## Screenshots

No screenshots are checked into the repository. Capture genuine screenshots after running the application: home, signup/login, user dashboard, inventory, request history, donor registration, hospitals, admin dashboard, user/donor management, inventory CRUD, request review, prediction form/result, MongoDB collections, server startup, and test output.

## Limitations and future scope

This is a local educational project, not a production blood-bank system. The prediction model uses synthetic data; there is no external hospital integration, verified user identity, email/SMS notification, or deployment hardening. Bootstrap assets load from a CDN. Future work could evaluate a consented real dataset, add audit history and notifications, integrate approved hospital systems, and deploy behind a production WSGI server with secure cookies and monitored backups.

For design details, see [architecture](docs/architecture.md), [database notes](docs/database.md), and [testing](docs/testing.md).
