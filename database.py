from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Replace with your actual MySQL credentials
SQLALCHEMY_DATABASE_URL = "mysql+pymysql://root:redhat@localhost/attendance_db"
#SQLALCHEMY_DATABASE_URL = "mysql+pymysql://root:redhat@host.docker.internal:3306/attendance_db"


engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    """
    Database dependency generator that yields a SQLAlchemy session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()