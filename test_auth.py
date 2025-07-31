import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from main import app
from database import Base, get_db
import models
import auth

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="function")
def db_session():
    """Create a new database session for a test."""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session):
    """A TestClient that uses the override_get_db dependency."""
    yield TestClient(app)


@pytest.fixture(scope="function")
def test_admin(db_session):
    """Create a test admin user."""
    hashed_password = auth.get_password_hash("adminpass")
    admin = models.User(name="Admin User", email="admin@test.com", password_hash=hashed_password, role=True, admin_id=1)
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)
    return admin

@pytest.fixture(scope="function")
def test_employee(db_session):
    """Create a test employee user."""
    hashed_password = auth.get_password_hash("emppass")
    employee = models.User(name="Employee User", email="employee@test.com", password_hash=hashed_password, role=False, employee_id=1)
    db_session.add(employee)
    db_session.commit()
    db_session.refresh(employee)
    return employee