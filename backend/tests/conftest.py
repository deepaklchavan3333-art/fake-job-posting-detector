import pytest

import app as app_module
import database.db as db_module
from database.schema import init_db


@pytest.fixture
def client(tmp_path, monkeypatch):
    database_file = tmp_path / "clearhire-test.sqlite3"
    monkeypatch.setattr(db_module, "DATABASE_PATH", database_file)
    app_module.app.config.update(TESTING=True, SECRET_KEY="pytest-secret", SESSION_COOKIE_SECURE=False)
    with app_module.app.app_context():
        init_db()
    with app_module.app.test_client() as test_client:
        yield test_client


@pytest.fixture
def registered_client(client):
    response = client.post("/api/auth/register", json={"email": "person@example.com", "password": "correct-horse-battery"})
    assert response.status_code == 201
    return client
