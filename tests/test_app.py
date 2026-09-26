"""Flask flow tests use an isolated in-memory MongoDB-compatible database."""
import pytest

mongomock = pytest.importorskip("mongomock")
pymongo = pytest.importorskip("pymongo")

from app import create_app


@pytest.fixture
def client():
    db = mongomock.MongoClient()["test_blood_bank"]
    app = create_app({"TESTING": True, "SECRET_KEY": "test-only-secret", "CSRF_ENABLED": False}, db)
    return app.test_client(), db


def test_auth_and_user_request_isolation(client):
    web, db = client
    assert web.get("/dashboard").status_code == 302
    response = web.post("/signup", data={"fullname": "Test User", "email": "test@example.test",
        "phone": "", "blood_group": "O+", "age": 25, "gender": "", "password": "strongpass1"})
    assert response.status_code == 302
    assert db.users.find_one({"email": "test@example.test"})["password"] != "strongpass1"
    assert web.post("/signup", data={"fullname": "Another User", "email": "test@example.test",
        "blood_group": "O+", "age": 25, "password": "strongpass2"}).status_code == 409
    assert web.post("/login", data={"email": "test@example.test", "password": "strongpass1"}).status_code == 302
    assert web.get("/inventory").status_code == 200
    assert web.post("/request_blood", data={"patient_name": "Patient", "blood_group": "O+",
        "units": 1, "hospital": "Clinic"}).status_code == 302
    assert len(list(db.requests.find({"requested_by_id": {"$exists": True}}))) == 1
    assert web.get("/logout").status_code == 302


def test_normal_user_cannot_edit_stock(client):
    web, db = client
    db.users.insert_one({"fullname": "Member", "email": "member@example.test", "password": "memberpass"})
    web.post("/login", data={"email": "member@example.test", "password": "memberpass"})
    assert web.post("/add_blood", data={"blood_group": "O+", "units": 10}).status_code == 403


def test_missing_record_renders_404(client):
    web, _ = client
    assert web.get("/some-missing-page").status_code == 404


def login_as(client, db, role="admin"):
    web, _ = client
    from werkzeug.security import generate_password_hash
    db.users.insert_one({"fullname": "Administrator", "email": "admin@example.test",
        "password": generate_password_hash("admin-password"), "role": role, "donor": False})
    web.post("/login", data={"email": "admin@example.test", "password": "admin-password"})
    return web


def test_admin_approval_deducts_stock_once(client):
    _, db = client
    web = login_as(client, db)
    stock_id = db.blood_inventory.insert_one({"blood_group": "O+", "units": 5}).inserted_id
    request_id = db.requests.insert_one({"blood_group": "O+", "units": 3, "status": "Pending"}).inserted_id
    assert web.post(f"/approve_request/{request_id}").status_code == 302
    assert db.blood_inventory.find_one({"_id": stock_id})["units"] == 2
    assert web.post(f"/approve_request/{request_id}").status_code == 302
    assert db.blood_inventory.find_one({"_id": stock_id})["units"] == 2


def test_approval_refuses_to_make_stock_negative(client):
    _, db = client
    web = login_as(client, db)
    stock_id = db.blood_inventory.insert_one({"blood_group": "A+", "units": 1}).inserted_id
    request_id = db.requests.insert_one({"blood_group": "A+", "units": 2, "status": "Pending"}).inserted_id
    assert web.post(f"/approve_request/{request_id}").status_code == 302
    assert db.blood_inventory.find_one({"_id": stock_id})["units"] == 1
    assert db.requests.find_one({"_id": request_id})["status"] == "Pending"


def test_admin_hospital_crud_and_user_management(client):
    _, db = client
    web = login_as(client, db)
    assert web.post("/add_hospital", data={"name": "City Hospital", "location": "Center", "phone": "123"}).status_code == 302
    hospital = db.hospitals.find_one({"name": "City Hospital"})
    assert hospital["location"] == "Center"
    assert web.post(f"/edit_hospital/{hospital['_id']}", data={"name": "City Hospital 2"}).status_code == 302
    assert db.hospitals.find_one({"_id": hospital["_id"]})["name"] == "City Hospital 2"
    assert web.post(f"/delete_hospital/{hospital['_id']}").status_code == 302
    user_id = db.users.insert_one({"fullname": "Member", "email": "member@example.test", "role": "user"}).inserted_id
    assert web.post(f"/admin/users/{user_id}/role", data={"role": "admin"}).status_code == 302
    assert db.users.find_one({"_id": user_id})["role"] == "admin"


def test_admin_inventory_crud_and_invalid_object_id(client):
    _, db = client
    web = login_as(client, db)
    assert web.post("/add_blood", data={"blood_group": "B+", "units": 4}).status_code == 302
    record = db.blood_inventory.find_one({"blood_group": "B+"})
    assert web.post(f"/edit_blood/{record['_id']}", data={"blood_group": "B+", "units": 7}).status_code == 302
    assert db.blood_inventory.find_one({"_id": record["_id"]})["units"] == 7
    assert web.post(f"/delete_blood/{record['_id']}").status_code == 302
    assert web.get("/edit_blood/not-an-object-id").status_code == 404


def test_user_cannot_access_admin_or_see_other_users_requests(client):
    web, db = client
    db.users.insert_one({"fullname": "Member", "email": "member@example.test", "password": "memberpass", "role": "user"})
    web.post("/login", data={"email": "member@example.test", "password": "memberpass"})
    with web.session_transaction() as state:
        own_user_id = state["user_id"]
    db.requests.insert_one({"patient_name": "Mine", "requested_by_id": own_user_id})
    db.requests.insert_one({"patient_name": "Private", "requested_by_id": "someone-else"})
    assert web.get("/admin/dashboard").status_code == 403
    response = web.get("/view_requests")
    assert response.status_code == 200
    assert b"Private" not in response.data
    assert web.get("/donors").status_code == 200


def test_request_details_are_limited_to_owner_or_admin(client):
    web, db = client
    db.users.insert_one({"fullname": "Member", "email": "member@example.test", "password": "memberpass", "role": "user"})
    web.post("/login", data={"email": "member@example.test", "password": "memberpass"})
    request_id = db.requests.insert_one({"patient_name": "Private", "requested_by_id": "someone-else"}).inserted_id
    assert web.get(f"/request_details/{request_id}").status_code == 403
    with web.session_transaction() as state:
        own_user_id = state["user_id"]
    own_id = db.requests.insert_one({"patient_name": "Mine", "requested_by_id": own_user_id}).inserted_id
    assert web.get(f"/request_details/{own_id}").status_code == 200


def test_admin_can_view_and_remove_donor_status(client):
    _, db = client
    web = login_as(client, db)
    donor_id = db.users.insert_one({"fullname": "Donor", "email": "donor@example.test", "donor": True,
        "blood_group": "A+", "phone": "555"}).inserted_id
    assert web.get("/admin/donors").status_code == 200
    assert web.get(f"/admin/donors/{donor_id}").status_code == 200
    assert web.post(f"/admin/donors/{donor_id}/remove").status_code == 302
    assert db.users.find_one({"_id": donor_id})["donor"] is False


def test_csrf_tokens_are_required_for_state_changes(client):
    web, _ = client
    app = web.application
    app.config["CSRF_ENABLED"] = True
    response = web.post("/signup", data={"email": "forged@example.test"})
    assert response.status_code == 400


def test_user_prediction_stores_labeled_demo_record(client):
    web, db = client
    db.users.insert_one({"fullname": "Member", "email": "member@example.test", "password": "memberpass", "role": "user"})
    web.post("/login", data={"email": "member@example.test", "password": "memberpass"})
    response = web.post("/prediction", data={"blood_group": "O+"})
    assert response.status_code == 200
    assert b"synthetic" in response.data
    assert db.predictions.count_documents({"blood_group": "O+"}) == 1
