from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Date, ForeignKey
from sqlalchemy.orm import relationship
from database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    admin_id = Column(Integer, unique=True, nullable=True)
    employee_id = Column(Integer, unique=True, nullable=True)
    name = Column(String(100))
    email = Column(String(100), unique=True, index=True)
    password_hash = Column(String(255))
    role = Column(Boolean, default=False)
    is_logged_in = Column(Boolean, default=False)  
    last_active = Column(DateTime, nullable=True)  
    
    attendance = relationship("Attendance", back_populates="user")
    leaves_requested = relationship("Leave", back_populates="user", foreign_keys="Leave.user_id")
    leaves_processed = relationship("Leave", back_populates="processed_by_user", foreign_keys="Leave.processed_by")
class Attendance(Base):
    __tablename__ = "attendance"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    date = Column(Date)
    check_in = Column(DateTime, nullable=True)
    check_out = Column(DateTime, nullable=True)
    
    user = relationship("User", back_populates="attendance")

class Leave(Base):
    __tablename__ = "leaves"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    from_date = Column(Date)
    to_date = Column(Date)
    reason = Column(String(255))
    status = Column(String(20), default="pending")  # pending, approved, rejected
    created_at = Column(DateTime, default=datetime.now)
    processed_by = Column(Integer, ForeignKey('users.id'), nullable=True)
    processed_at = Column(DateTime, nullable=True)
    
    user = relationship("User", back_populates="leaves_requested", foreign_keys=[user_id])
    processed_by_user = relationship("User", back_populates="leaves_processed", foreign_keys=[processed_by])