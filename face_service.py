import cv2
import numpy as np
import os
import time
from datetime import datetime, timedelta
from dotenv import load_dotenv

from sqlalchemy.future import select
from sqlalchemy.orm.attributes import flag_modified
import mediapipe as mp

from database import DATABASE_URL, connect_args
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

engine_bg = create_async_engine(
    DATABASE_URL, 
    echo=False,
    connect_args=connect_args,
    pool_pre_ping=True,
    pool_recycle=60,
    pool_size=10,
    max_overflow=0
)
AsyncSessionLocalBG = sessionmaker(engine_bg, class_=AsyncSession, expire_on_commit=False)

from models import RegisteredFace, AttendanceLog

load_dotenv()

# --- INSTANT-BOOT ENTERPRISE INITIALIZATION ---
# Using CPU-Optimized models to remove Keras/Tensorflow hardware hangs
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = os.path.join(BASE_DIR, "models")

# SFace Extractor (128 Dimensions)
sface_path = os.path.join(MODELS_DIR, "face_recognition_sface_2021dec.onnx")
face_recognizer = cv2.FaceRecognizerSF.create(sface_path, "")
DIMENSION = 128

# FAISS is now retired. We use Pure Cloud pgvector Search.
last_visitor_created_at = 0

# Mediapipe Liveness (Blink Detection)
mp_face_mesh = mp.solutions.face_mesh
face_mesh_liveness = mp_face_mesh.FaceMesh(
    max_num_faces=1,
    refine_landmarks=True,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5
)
last_blink_time = 0
LIVENESS_WINDOW = 5.0

last_visitor_created_at = 0

def l2_normalize(x):
    if np.linalg.norm(x) == 0: return x
    return x / np.linalg.norm(x)

def calculate_ear(eye_landmarks):
    # Calculate Eye Aspect Ratio for blink detection
    v1 = np.linalg.norm(eye_landmarks[1] - eye_landmarks[5])
    v2 = np.linalg.norm(eye_landmarks[2] - eye_landmarks[4])
    h = np.linalg.norm(eye_landmarks[0] - eye_landmarks[3])
    if h == 0: return 0
    return (v1 + v2) / (2.0 * h)

def check_liveness(frame: np.ndarray) -> bool:
    global last_blink_time
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = face_mesh_liveness.process(rgb_frame)
    
    if results.multi_face_landmarks:
        for face_landmarks in results.multi_face_landmarks:
            h, w, _ = frame.shape
            landmarks = np.array([(lm.x * w, lm.y * h) for lm in face_landmarks.landmark])
            
            left_eye_indices = [362, 385, 387, 263, 373, 380]
            right_eye_indices = [33, 160, 158, 133, 153, 144]
            
            left_eye = landmarks[left_eye_indices]
            right_eye = landmarks[right_eye_indices]
            
            ear_left = calculate_ear(left_eye)
            ear_right = calculate_ear(right_eye)
            avg_ear = (ear_left + ear_right) / 2.0
            
            if avg_ear < 0.22:
                last_blink_time = time.time()
                
    if (time.time() - last_blink_time) < LIVENESS_WINDOW:
        return True
    return False

async def load_faiss_db():
    # FAISS is no longer needed for Pure Cloud Vision
    print("Cloud Vision Mode: FAISS sync deactivated.")
    return


def extract_face(frame: np.ndarray, enforce_liveness=False):
    """Fallback for manual API registration"""
    if enforce_liveness and not check_liveness(frame):
        return []
    
    # Needs a 112x112 face crop aligned for SFace... this is just for manual registration
    detector = cv2.FaceDetectorYN.create(os.path.join(MODELS_DIR, "face_detection_yunet_2023mar.onnx"), "", (frame.shape[1], frame.shape[0]))
    _, faces = detector.detect(frame)
    if faces is None: return []
    
    aligned_face = face_recognizer.alignCrop(frame, faces[0])
    feature = face_recognizer.feature(aligned_face)
    return [{"embedding": feature[0]}]

async def process_tracker_crop(crop_img: np.ndarray, bbox, full_frame: np.ndarray, location: str = "Unknown"):
    """Processes tracked face using Cloud-Native pgvector Search with Enhanced Re-ID and Location tracking."""
    global last_visitor_created_at
    
    # 0. Early Quality Filtering (Before doing expensive math)
    _, _, box_w, box_h = bbox
    fh, fw = full_frame.shape[:2]
    
    # Reject tiny faces (less than 5% of screen width)
    if box_w < fw * 0.05 or box_h < fh * 0.05: 
        return None, "Too far"

    # Reject heavily blurred faces
    gray = cv2.cvtColor(crop_img, cv2.COLOR_BGR2GRAY)
    fm = cv2.Laplacian(gray, cv2.CV_64F).var()
    if fm < 40.0: 
        return None, "Blurry..."

    # 1. Align and Extract Feature
    h, w = crop_img.shape[:2]
    
    import threading
    if not hasattr(threading.current_thread(), "face_detector"):
        threading.current_thread().face_detector = cv2.FaceDetectorYN.create(
            os.path.join(MODELS_DIR, "face_detection_yunet_2023mar.onnx"), "", (w, h), score_threshold=0.3
        )
    detector = threading.current_thread().face_detector
    detector.setInputSize((w, h))
    
    _, faces = detector.detect(crop_img)
    
    if faces is None:
        # DO NOT process unaligned faces, they will ruin accuracy!
        return None, "Aligning..."
        
    aligned_face = face_recognizer.alignCrop(crop_img, faces[0])
    feature = face_recognizer.feature(aligned_face)
    
    raw_emb = np.array(feature[0], dtype=np.float32)
    embedding = l2_normalize(raw_emb).tolist() 
    
        # 2. PURE CLOUD SEARCH (Re-ID Logic)
    async with AsyncSessionLocalBG() as session:
        query = select(RegisteredFace).where(
            RegisteredFace.face_encoding.l2_distance(embedding) < 1.40,
            RegisteredFace.is_active == True
        ).order_by(RegisteredFace.face_encoding.l2_distance(embedding)).limit(1)
        
        result = await session.execute(query)
        p = result.scalars().first()
        
        # In-Memory Cache to prevent Cloud DB spam for the exact same person
        if not hasattr(process_tracker_crop, "local_cache"):
            process_tracker_crop.local_cache = {}

        if p:
            if p.is_blacklisted:
                return p.id, f"BLACKLIST: {p.name}"
            
            current_time = time.time()
            if p.id in process_tracker_crop.local_cache and (current_time - process_tracker_crop.local_cache[p.id]) < 86400:
                # Already logged in the last 24 hours, skip database hit!
                return p.id, p.name

            # Prevent Duplicate Logging (Cool-down: 24 hours per person)
            log_check = await session.execute(
                select(AttendanceLog).where(
                    AttendanceLog.face_id == p.id,
                    AttendanceLog.timestamp > datetime.now() - timedelta(hours=24)
                ).limit(1)
            )
            if not log_check.scalars().first():
                session.add(AttendanceLog(face_id=p.id, timestamp=datetime.now(), location=location))
                await session.commit()
            
            process_tracker_crop.local_cache[p.id] = current_time
            return p.id, p.name

    # 3. Create New Visitor (If face is good quality but unknown)
    current_time_val = time.time()
    if (current_time_val - last_visitor_created_at) < 15: 
        return None, "Wait..."

    # 4. Create New Visitor
    v_id = int(current_time_val * 1000)
    v_name = f"Visitor_{v_id}"
    img_path = await save_face_image(v_id, crop_img)

    async with AsyncSessionLocalBG() as session:
        new_person = RegisteredFace(
            name=v_name, role="visitor", face_encoding=embedding, image_path=img_path
        )
        session.add(new_person)
        await session.flush()
        
        session.add(AttendanceLog(face_id=new_person.id, timestamp=datetime.now(), location=location))
        await session.commit()
        last_visitor_created_at = current_time_val
        
        return new_person.id, v_name


async def save_face_image(id_val, crop_img):
    try:
        rel = f"static/faces/{id_val}.jpg"
        abs_p = os.path.join(BASE_DIR, rel)
        os.makedirs(os.path.dirname(abs_p), exist_ok=True)
        cv2.imwrite(abs_p, crop_img)
        return rel
    except: return None
