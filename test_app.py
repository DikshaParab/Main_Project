import unittest
from datetime import datetime, date
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database import Base, get_db
from main import app
import models

# Setup test database
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Dependency override
def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)

class TestAttendanceSystem(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Create all tables
        Base.metadata.create_all(bind=engine)

    @classmethod
    def tearDownClass(cls):
        # Drop all tables
        Base.metadata.drop_all(bind=engine)

    def setUp(self):
        # Clear data between tests
        db = TestingSessionLocal()
        try:
            for table in reversed(Base.metadata.sorted_tables):
                db.execute(table.delete())
            db.commit()
        finally:
            db.close()

    # Authentication Tests
    def test_register_first_admin(self):
        response = client.post("/register", data={
            "name": "Admin User",
            "email": "admin@example.com",
            "password": "admin123"
        }, follow_redirects=False)
        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.headers["location"], "/login")

    def test_login_success(self):
        # First register admin
        client.post("/register", data={
            "name": "Admin User",
            "email": "admin@example.com",
            "password": "admin123"
        })
        
        # Test login
        response = client.post("/login", data={
            "email": "admin@example.com",
            "password": "admin123"
        }, follow_redirects=False)
        self.assertEqual(response.status_code, 303)
        self.assertIn("/admin/dashboard/", response.headers["location"])

    # Admin Function Tests
    def test_admin_dashboard(self):
        # Register and login as admin
        client.post("/register", data={
            "name": "Admin User",
            "email": "admin@example.com",
            "password": "admin123"
        })
        login_response = client.post("/login", data={
            "email": "admin@example.com",
            "password": "admin123"
        }, follow_redirects=False)
        admin_id = login_response.headers["location"].split("/")[-1]
        
        response = client.get(f"/admin/dashboard/{admin_id}")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Admin Dashboard", response.text)

    # Employee Function Tests
    def test_employee_punch_in_out(self):
        # Register admin and add employee
        client.post("/register", data={
            "name": "Admin User",
            "email": "admin@example.com",
            "password": "admin123"
        })
        client.post("/login", data={
            "email": "admin@example.com",
            "password": "admin123"
        })
        client.post(
            "/admin/add-employee/1",
            data={
                "name": "Employee One",
                "email": "employee@example.com",
                "password": "emp123",
                "role": "0"
            }
        )
        
        # Login as employee
        login_response = client.post("/login", data={
            "email": "employee@example.com",
            "password": "emp123"
        }, follow_redirects=False)
        employee_id = login_response.headers["location"].split("/")[-1]
        
        # Punch in
        punch_in_response = client.post(f"/employee/punch-in/{employee_id}")
        self.assertEqual(punch_in_response.status_code, 200, 303)
        
        # Punch out
        punch_out_response = client.post(f"/employee/punch-out/{employee_id}")
        self.assertEqual(punch_out_response.status_code, 200, 303)

