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
    webhook_url = Column(String, nullable=True) # WhatsApp/Telegram Webhook
    whatsapp_enabled = Column(Boolean, default=False)
    whatsapp_number = Column(String, nullable=True)
    whatsapp_api_key = Column(String, nullable=True)
    whatsapp_provider = Column(String, default="callmebot") # callmebot, ultramsg, twilio
    telegram_enabled = Column(Boolean, default=False)
    telegram_token = Column(String, nullable=True)
    telegram_chat_id = Column(String, nullable=True)
    gmail_enabled = Column(Boolean, default=False)
    alert_email = Column(String, nullable=True)
    notify_on_entry = Column(Boolean, default=True)
    notify_on_expiry = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)

class CameraNode(Base):
    __tablename__ = "camera_nodes"
    
    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, nullable=False, index=True)
    name = Column(String, nullable=False)
    url = Column(String, nullable=False)
    use_p2p = Column(Boolean, default=False)
    p2p_uid = Column(String, nullable=True)
    p2p_user = Column(String, nullable=True)
    p2p_pass = Column(String, nullable=True)
    use_onvif = Column(Boolean, default=False)
    onvif_port = Column(Integer, default=80)
    onvif_user = Column(String, nullable=True)
    onvif_pass = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
