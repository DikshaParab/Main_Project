from pydantic import BaseModel, EmailStr
from datetime import datetime, date
from typing import Optional, List

# User Schemas
class UserBase(BaseModel):
    email: EmailStr
    name: str

class UserCreate(UserBase):
    password: str

class User(UserBase):
    id: int
    role: bool
    admin_id: Optional[int] = None
    employee_id: Optional[int] = None

    class Config:
        orm_mode = True
        from_attributes = True  # For Pydantic v2 compatibility

# Attendance Schemas
class AttendanceBase(BaseModel):
    date: date

class AttendanceCreate(AttendanceBase):
    pass

class Attendance(AttendanceBase):
    id: int
    user_id: int
    check_in: Optional[datetime] = None
    check_out: Optional[datetime] = None
    user: Optional[User] = None

    class Config:
        orm_mode = True
        from_attributes = True

# Leave Schemas
class LeaveBase(BaseModel):
    from_date: date
    to_date: date
    reason: str

class LeaveCreate(LeaveBase):
    pass

class Leave(LeaveBase):
    id: int
    user_id: int
    status: str = "pending"
    created_at: datetime
    processed_by: Optional[int] = None
    processed_at: Optional[datetime] = None
    user: Optional[User] = None
    processed_by_user: Optional[User] = None

    class Config:
        orm_mode = True
        from_attributes = True

class LeaveUpdate(BaseModel):
    status: str
    processed_by: Optional[int] = None