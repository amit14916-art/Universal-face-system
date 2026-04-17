from sqlalchemy import Column, Integer, String, DateTime, Boolean
from pgvector.sqlalchemy import Vector
from datetime import datetime
from database import Base

class RegisteredFace(Base):
    __tablename__ = "registered_faces"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    role = Column(String, default="member")
    # SFace vector is exactly 128 dimensions
    face_encoding = Column(Vector(128), nullable=False) 
    image_path = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    is_active = Column(Boolean, default=True)
    is_blacklisted = Column(Boolean, default=False)
    notes = Column(String, nullable=True)

class AttendanceLog(Base):
    __tablename__ = "attendance_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    face_id = Column(Integer)
    timestamp = Column(DateTime, default=datetime.now)
    location = Column(String, default="Main Entrance")
