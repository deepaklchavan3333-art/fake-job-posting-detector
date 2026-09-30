def test_health_reports_model_status(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert "model_ready" in response.get_json()


def test_registration_hashes_password_and_rejects_duplicate(registered_client):
    from database import get_db
    with registered_client.application.app_context():
        user = get_db().execute("SELECT * FROM users WHERE email = ?", ("person@example.com",)).fetchone()
        assert user["password_hash"] != "correct-horse-battery"
    duplicate = registered_client.post("/api/auth/register", json={"email": "person@example.com", "password": "correct-horse-battery"})
    assert duplicate.status_code == 409


def test_prediction_rejects_empty_listing(client):
    response = client.post("/api/predict", json={})
    assert response.status_code == 400


def test_guest_prediction_is_not_written_to_private_history(client, monkeypatch):
    import routes.prediction_routes as route_module
    from database import get_db
    monkeypatch.setattr(route_module, "predict", lambda _record: {"prediction": "REAL", "fake_probability": .12, "confidence": .88, "risk_level": "LOW", "explanations": [], "notice": "Test"})
    response = client.post("/api/predict", json={"title": "Engineer"})
    assert response.status_code == 200
    assert response.get_json()["id"] is None
    with client.application.app_context():
        assert get_db().execute("SELECT COUNT(*) FROM predictions").fetchone()[0] == 0


def test_prediction_is_saved_and_private_to_account(registered_client, monkeypatch):
    import routes.prediction_routes as route_module
    monkeypatch.setattr(route_module, "predict", lambda _record: {"prediction": "FAKE", "fake_probability": .91, "confidence": .91, "risk_level": "HIGH", "explanations": ["Test indicator"], "notice": "Test"})
    response = registered_client.post("/api/predict", json={"title": "Remote assistant", "description": "Job details"})
    assert response.status_code == 200
    assert response.get_json()["fake_percent"] == 91
    assert registered_client.get("/api/history").get_json()[0]["prediction"] == "FAKE"


def test_history_requires_sign_in(client):
    response = client.get("/api/history")
    assert response.status_code == 401
