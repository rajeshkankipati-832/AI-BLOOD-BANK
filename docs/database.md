# Database notes

The application uses the `AI_Blood_Bank` MongoDB database by default. Set `MONGO_URI` and `MONGO_DB` to override these values. Existing collection names are retained; the application does not drop collections or remove records.

| Collection | Purpose | Main fields |
| --- | --- | --- |
| `users` | Accounts and donor profiles | `fullname`, `email`, hashed `password`, `role`, `donor`, contact and blood group fields |
| `blood_inventory` | Blood group unit counts | `blood_group`, `units`, update timestamps |
| `requests` | User-submitted blood requests | patient, blood group, units, requester ID, hospital, status, timestamps |
| `hospitals` | Hospital directory | name, location, phone, connected flag |
| `predictions` | Prediction demo audit records | blood group, synthetic estimate metadata, requester ID, timestamp |

`create_admin.py` inserts an administrator only when the supplied email is not already present. The tool does not modify existing accounts. Existing users with plaintext passwords are upgraded to a Werkzeug hash after their next successful login.

For a production rollout, back up the database first and add a unique index on normalized user email after checking for duplicates. This development app intentionally does not create indexes automatically, so it will not fail to start due to pre-existing duplicate email records.
