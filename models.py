from sqlalchemy import Column, Integer, String, PickleType, DateTime, Boolean
from datetime import datetime
from database import Base

class RegisteredFace(Base):
    __tablename__ = "registered_faces"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    role = Column(String, default="member") # 'staff', 'vip', 'gym_member'
    # 128-d vector yahan PickleType mein save hoga
    face_encoding = Column(PickleType, nullable=False) 
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)

class AttendanceLog(Base):
    __tablename__ = "attendance_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    face_id = Column(Integer) # RegisteredFace.id se link hoga
    timestamp = Column(DateTime, default=datetime.utcnow)
    location = Column(String, default="Main Entrance")
