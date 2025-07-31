from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
import models
from datetime import date, timedelta

def test_admin_dashboard(client: TestClient, test_admin: models.User):
    response = client.get(f"/admin/dashboard/{test_admin.id}")
    assert response.status_code == 200
    assert "Admin Dashboard" in response.text
    assert test_admin.name in response.text