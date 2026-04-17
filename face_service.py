import cv2
import numpy as np
import os
import time
from datetime import datetime
from dotenv import load_dotenv

from sqlalchemy.future import select
from sqlalchemy.orm.attributes import flag_modified
import mediapipe as mp

from database import AsyncSessionLocal
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

async def process_tracker_crop(crop_img: np.ndarray, bbox, full_frame: np.ndarray):
    """Processes tracked face using Cloud-Native pgvector Search."""
    global last_visitor_created_at
    
    # We must run YuNet inside the crop to find landmarks for alignCrop
    h, w = crop_img.shape[:2]
    detector = cv2.FaceDetectorYN.create(os.path.join(MODELS_DIR, "face_detection_yunet_2023mar.onnx"), "", (w, h))
    _, faces = detector.detect(crop_img)
    if faces is None: return None, "Aligning..."
    
    aligned_face = face_recognizer.alignCrop(crop_img, faces[0])
    feature = face_recognizer.feature(aligned_face)
    embedding = feature[0].tolist() # Convert to list for pgvector compatibility
    
    # PURE CLOUD SEARCH using pgvector L2 Distance (<->)
    async with AsyncSessionLocal() as session:
        from sqlalchemy import text
        # Threshold: 0.6 L2 distance is roughly equivalent to our 0.36 similarity
        query = select(RegisteredFace).where(
            RegisteredFace.face_encoding.l2_distance(embedding) < 0.6,
            RegisteredFace.is_active == True,
            RegisteredFace.is_blacklisted == False
        ).order_by(RegisteredFace.face_encoding.l2_distance(embedding)).limit(1)
        
        result = await session.execute(query)
        p = result.scalars().first()
        
        if p:
            # Found match in cloud
            return p.id, p.name


    current_time_val = time.time()
    _, _, box_w, box_h = bbox
    h, w = full_frame.shape[:2]
    
    # Dynamic Scaling: Must be at least 5% of the frame width
    if box_w < w * 0.05 or box_h < h * 0.05: return None, "Too far"
    if (current_time_val - last_visitor_created_at) < 2: return None, "Wait..."

    # Laplacian Variance Focus Analysis (Blur Check) - discard moving/blurry faces
    gray = cv2.cvtColor(crop_img, cv2.COLOR_BGR2GRAY)
    fm = cv2.Laplacian(gray, cv2.CV_64F).var()
    if fm < 85.0: return None, "Blurry..."

    v_id = int(current_time_val * 1000)
    v_name = f"Visitor_{v_id}"
    img_path = await save_face_image(v_id, crop_img)

    async with AsyncSessionLocal() as session:
        new_person = RegisteredFace(
            name=v_name, role="visitor", face_encoding=embedding, image_path=img_path
        )
        session.add(new_person)
        await session.flush()
        
        session.add(AttendanceLog(face_id=new_person.id, timestamp=datetime.now()))
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
