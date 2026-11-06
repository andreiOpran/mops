from fastapi.testclient import TestClient

from app.main import app, get_database_check

client = TestClient(app)


def test_health_reports_database_ok():
    app.dependency_overrides[get_database_check] = lambda: lambda: True
    try:
        response = client.get("/api/health")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


def test_health_reports_database_unavailable():
    app.dependency_overrides[get_database_check] = lambda: lambda: False
    try:
        response = client.get("/api/health")
    finally:
        app.dependency_overrides.clear()

    assert response.json() == {"status": "ok", "database": "unavailable"}
