import cv2
import numpy as np
import os
import time
import pickle
from dotenv import load_dotenv

from sqlalchemy.future import select
from database import AsyncSessionLocal
from models import RegisteredFace, AttendanceLog

load_dotenv()

# Track last attendance log time for each face_id (in seconds)
ATTENDANCE_COOLDOWN = 60  # 1 minute cooldown
last_logged_time = {}

# --- Model Paths ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DETECTOR_MODEL = os.path.join(BASE_DIR, "models", "face_detection_yunet_2023mar.onnx")
RECOGNIZER_MODEL = os.path.join(BASE_DIR, "models", "face_recognition_sface_2021dec.onnx")

# --- Load YuNet Face Detector ---
face_detector = cv2.FaceDetectorYN.create(
    DETECTOR_MODEL,
    "",
    (320, 320),
    score_threshold=0.6,
    nms_threshold=0.3,
    top_k=5
)

# --- Load SFace Face Recognizer ---
face_recognizer = cv2.FaceRecognizerSF.create(RECOGNIZER_MODEL, "")

print("✅ YuNet + SFace models loaded.")


def get_face_feature(frame: np.ndarray, face: np.ndarray) -> np.ndarray:
    """Aligns face and returns a 128-d SFace embedding."""
    aligned = face_recognizer.alignCrop(frame, face)
    feature = face_recognizer.feature(aligned)
    return feature.flatten()


async def get_face_embeddings(frame: np.ndarray):
    """
    Detects faces using YuNet and returns locations + SFace embeddings.
    """
    h, w = frame.shape[:2]
    face_detector.setInputSize((w, h))

    _, faces = face_detector.detect(frame)

    face_locations = []
    face_encodings = []

    if faces is None:
        return face_locations, face_encodings

    for face in faces:
        x, y, fw, fh = int(face[0]), int(face[1]), int(face[2]), int(face[3])
        top = max(0, y)
        left = max(0, x)
        bottom = min(h, y + fh)
        right = min(w, x + fw)

        try:
            embedding = get_face_feature(frame, face)
            face_locations.append((top, right, bottom, left))
            face_encodings.append(embedding)
        except Exception as e:
            print(f"Embedding error: {e}")

    return face_locations, face_encodings


def draw_metadata(frame, face_locations, face_names):
    """Draws bounding boxes and name labels on the frame."""
    for (top, right, bottom, left), name in zip(face_locations, face_names):
        color = (0, 220, 80) if name != "Unknown" else (0, 60, 255)
        cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
        cv2.rectangle(frame, (left, bottom - 35), (right, bottom), color, cv2.FILLED)
        cv2.putText(frame, name, (left + 6, bottom - 6),
                    cv2.FONT_HERSHEY_DUPLEX, 0.8, (255, 255, 255), 1)
    return frame


async def match_face(current_encoding: np.ndarray):
    """
    Finds the best match for current_encoding in the database
    using SFace cosine similarity score.
    """
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(RegisteredFace))
        registered_faces = result.scalars().all()

        if not registered_faces:
            return None, "Unknown"

        matched_person = None
        best_score = -1.0
        THRESHOLD = 0.363  # SFace cosine threshold (recommended)

        for person in registered_faces:
            encoding = person.face_encoding
            if isinstance(encoding, bytes):
                try:
                    encoding = pickle.loads(encoding)
                except Exception:
                    pass

            if isinstance(encoding, np.ndarray):
                # Reshape for SFace scorer
                e1 = current_encoding.reshape(1, -1)
                e2 = encoding.reshape(1, -1)
                score = face_recognizer.match(e1, e2, cv2.FaceRecognizerSF_FR_COSINE)
                if score > best_score:
                    best_score = score
                    matched_person = person

        if matched_person is None or best_score < THRESHOLD:
            return None, "Unknown"

        current_time = time.time()
        last_time = last_logged_time.get(matched_person.id, 0)

        if current_time - last_time > ATTENDANCE_COOLDOWN:
            new_log = AttendanceLog(face_id=matched_person.id)
            session.add(new_log)
            await session.commit()
            last_logged_time[matched_person.id] = current_time
            print(f"📝 Attendance logged for {matched_person.name}")

        return matched_person.id, matched_person.name


async def register_new_face(name: str, role: str, encoding: np.ndarray):
    """Registers a new face in the database."""
    async with AsyncSessionLocal() as session:
        new_face = RegisteredFace(
            name=name,
            role=role,
            face_encoding=encoding
        )
        session.add(new_face)
        await session.commit()
        print(f"✅ {name} registered in Database!")
