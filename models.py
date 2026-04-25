from sqlalchemy import Column, Integer, String, DateTime, Boolean
from pgvector.sqlalchemy import Vector
from datetime import datetime
from database import Base

class RegisteredFace(Base):
    __tablename__ = "registered_faces"
    
    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, nullable=False, index=True) # ID of the gym owner
    name = Column(String, nullable=False)
    role = Column(String, default="member")
    # SFace vector is exactly 128 dimensions
    face_encoding = Column(Vector(128), nullable=False) 
    image_path = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    is_active = Column(Boolean, default=True)
    is_blacklisted = Column(Boolean, default=False)
    subscription_expiry = Column(DateTime, nullable=True) # Date when membership ends
    plan_type = Column(String, default="monthly") # e.g., monthly, yearly, vip
    notes = Column(String, nullable=True)

class AttendanceLog(Base):
    __tablename__ = "attendance_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, nullable=False, index=True) # ID of the gym owner
    face_id = Column(Integer)
    timestamp = Column(DateTime, default=datetime.now)
    location = Column(String, default="Main Entrance")

class GymOwner(Base):
    __tablename__ = "gym_owners"
    
    id = Column(Integer, primary_key=True, index=True)
    gym_name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    mobile = Column(String, nullable=False)
    password = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.now)
