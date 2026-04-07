import cv2
import face_recognition
import numpy as np
import io
import os
from google.cloud import vision
from dotenv import load_dotenv

from sqlalchemy.future import select
from database import AsyncSessionLocal
from models import RegisteredFace, AttendanceLog

load_dotenv()

# Google Cloud Vision Client Setup
# Ensure your 'service_account.json' is in the project folder
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = 'service_account.json'
client = vision.ImageAnnotatorClient()

async def get_face_embeddings(frame):
    """
    Antigravity Logic: 
    1. Google Vision se pucho face hai ya nahi (Detection).
    2. face_recognition se 128-d encoding nikalo (Identification).
    """
    # RGB mein convert karo (face_recognition requires RGB)
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    
    # 2. Face Encoding (Actual ID)
    face_locations = face_recognition.face_locations(rgb_frame)
    face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)
    
    return face_locations, face_encodings

def draw_metadata(frame, face_locations, face_names):
    """Frame par box aur naam banane ke liye"""
    for (top, right, bottom, left), name in zip(face_locations, face_names):
        cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)
        cv2.rectangle(frame, (left, bottom - 35), (right, bottom), (0, 255, 0), cv2.FILLED)
        cv2.putText(frame, name, (left + 6, bottom - 6), cv2.FONT_HERSHEY_DUPLEX, 0.8, (255, 255, 255), 1)
    return frame

async def match_face(current_encoding):
    """
    DB se saare registered chehre nikal kar current face se match karta hai.
    """
    async with AsyncSessionLocal() as session:
        # 1. DB se saare faces lao
        result = await session.execute(select(RegisteredFace))
        registered_faces = result.scalars().all()
        
        if not registered_faces:
            return None, "Unknown"

        # 2. Known Encodings ki list taiyar karo
        known_encodings = [f.face_encoding for f in registered_faces]
        
        # 3. Match check karo (Tolerence 0.6 standard hai)
        matches = face_recognition.compare_faces(known_encodings, current_encoding, tolerance=0.6)
        
        if True in matches:
            first_match_index = matches.index(True)
            matched_person = registered_faces[first_match_index]
            
            # Attendance Log daal do (Background task ki tarah)
            new_log = AttendanceLog(face_id=matched_person.id)
            session.add(new_log)
            await session.commit()
            
            return matched_person.id, matched_person.name
            
        return None, "Unknown"

async def register_new_face(name, role, encoding):
    """Naya banda register karne ke liye"""
    async with AsyncSessionLocal() as session:
        new_face = RegisteredFace(
            name=name,
            role=role,
            face_encoding=encoding
        )
        session.add(new_face)
        await session.commit()
        print(f"✅ {name} registered in Database!")
