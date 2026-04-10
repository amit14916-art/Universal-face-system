import cv2
import numpy as np
import os
import time
import pickle
from datetime import datetime
from dotenv import load_dotenv

from sqlalchemy.future import select
from database import AsyncSessionLocal
from models import RegisteredFace, AttendanceLog

load_dotenv()

# Cooldown to prevent duplicate logging/registering (in seconds)
ATTENDANCE_COOLDOWN = 60 
# New Visitor throttle (Don't create a second new visitor within 10 seconds)
NEW_VISITOR_THROTTLE = 10
last_visitor_created_at = 0

last_logged_time = {}

# --- Model Paths ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DETECTOR_MODEL = os.path.join(BASE_DIR, "models", "face_detection_yunet_2023mar.onnx")
RECOGNIZER_MODEL = os.path.join(BASE_DIR, "models", "face_recognition_sface_2021dec.onnx")

# --- Load YuNet Face Detector ---
face_detector = cv2.FaceDetectorYN.create(
    DETECTOR_MODEL, "", (320, 320),
    score_threshold=0.6, nms_threshold=0.3, top_k=5
)

# --- Load SFace Face Recognizer ---
face_recognizer = cv2.FaceRecognizerSF.create(RECOGNIZER_MODEL, "")

print("OK: Models loaded for High-Reliability Mode.")

def get_face_feature(frame: np.ndarray, face: np.ndarray) -> np.ndarray:
    aligned = face_recognizer.alignCrop(frame, face)
    feature = face_recognizer.feature(aligned)
    return feature.flatten()

async def get_face_embeddings(frame: np.ndarray):
    h, w = frame.shape[:2]
    face_detector.setInputSize((w, h))
    _, faces = face_detector.detect(frame)
    
    face_locations, face_encodings = [], []
    if faces is None: return [], [], []

    for face in faces:
        x, y, fw, fh = map(int, face[:4])
        face_locations.append((max(0, y), min(w, x + fw), min(h, y + fh), max(0, x)))
        try:
            face_encodings.append(get_face_feature(frame, face))
        except: pass
    return face_locations, face_encodings, faces

def draw_metadata(frame, face_locations, face_names):
    """Draws bounding boxes and name labels on the frame."""
    for (top, right, bottom, left), name in zip(face_locations, face_names):
        color = (0, 220, 80) if "Visitor" not in name else (0, 60, 255)
        cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
        cv2.rectangle(frame, (left, bottom - 35), (right, bottom), color, cv2.FILLED)
        cv2.putText(frame, name, (left + 6, bottom - 6),
                    cv2.FONT_HERSHEY_DUPLEX, 0.8, (255, 255, 255), 1)
    return frame

async def match_face(current_encoding: np.ndarray, frame: np.ndarray = None, face_coords: np.ndarray = None):
    global last_visitor_created_at
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(RegisteredFace))
        all_registered = result.scalars().all()

        best_score = -1.0
        best_match = None
        
        # --- TOLERANT MATCHING ---
        # We use a very low threshold (0.20) to catch returning visitors in poor lighting.
        MATCH_THRESHOLD = 0.20 

        for person in all_registered:
            db_enc = person.face_encoding
            
            # Smart decoding
            if isinstance(db_enc, bytes):
                try: db_enc = pickle.loads(db_enc)
                except: pass
            
            if not isinstance(db_enc, np.ndarray): continue

            # Cosine match
            s = face_recognizer.match(current_encoding.reshape(1, -1), db_enc.reshape(1, -1), cv2.FaceRecognizerSF_FR_COSINE)
            if s > best_score:
                best_score = s
                best_match = person

        current_time_val = time.time()
        
        # DECISION: MATCH OR NEW?
        if best_match is not None and best_score >= MATCH_THRESHOLD:
            # RECOGNIZED
            print(f"--> [MATCH] {best_match.name} (Score: {best_score:.3f})")
            matched_person = best_match
        else:
            # CHECK THROTTLE: Don't create visitors too fast
            if (current_time_val - last_visitor_created_at) < NEW_VISITOR_THROTTLE:
                print(f"--> [WAIT] Skipping new registration (Cooling down...) Best Score: {best_score:.3f}")
                return None, "Wait"

            # NEW FACE CAPTURE
            v_id = int(current_time_val * 1000)
            v_name = f"Visitor_{v_id}"
            img = await save_face_image(v_id, frame, face_coords) if frame is not None else None

            matched_person = RegisteredFace(
                name=v_name, role="visitor", face_encoding=current_encoding, image_path=img
            )
            session.add(matched_person)
            await session.flush()
            last_visitor_created_at = current_time_val
            print(f"--> [NEW] Registering {v_name} (Best score was only {best_score:.3f})")

        # LOGGING
        last_log = last_logged_time.get(matched_person.id, 0)
        if (current_time_val - last_log) > ATTENDANCE_COOLDOWN:
            session.add(AttendanceLog(face_id=matched_person.id, timestamp=datetime.now()))
            last_logged_time[matched_person.id] = current_time_val
            print(f"--> [LOG] Access verified for {matched_person.name}")
        
        await session.commit()
        return matched_person.id, matched_person.name

async def save_face_image(id_val, frame, face_coords):
    try:
        x, y, w, h = map(int, face_coords[:4])
        pad = int(h * 0.3)
        y1, y2 = max(0, y - pad), min(frame.shape[0], y + h + pad)
        x1, x2 = max(0, x - pad), min(frame.shape[1], x + w + pad)
        face_img = frame[y1:y2, x1:x2]
        if face_img.size == 0: return None
        rel = f"static/faces/{id_val}.jpg"
        abs_p = os.path.join(BASE_DIR, rel)
        os.makedirs(os.path.dirname(abs_p), exist_ok=True)
        cv2.imwrite(abs_p, face_img)
        return rel
    except: return None
