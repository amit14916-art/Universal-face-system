import asyncio
import sys
import cv2
import numpy as np
import pickle

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

from database import init_db, AsyncSessionLocal
from models import RegisteredFace
from sqlalchemy.future import select

# Import face service components (sync-safe)
from face_service import face_detector, get_face_feature


def capture_face_sync(name: str) -> np.ndarray | None:
    """
    Opens the webcam on the main thread (required for OpenCV GUI on Windows).
    Returns the captured face encoding, or None if cancelled.
    """
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("❌ Could not open webcam. Check that your camera is connected.")
        return None

    print(f"\n📷 Registering '{name}' — look at the camera.")
    print("   Press SPACE to capture | Press Q to cancel\n")

    captured_encoding = None

    while True:
        ret, frame = cap.read()
        if not ret:
            print("❌ Failed to read from webcam.")
            break

        h, w = frame.shape[:2]
        face_detector.setInputSize((w, h))
        _, faces = face_detector.detect(frame)

        display_frame = frame.copy()

        if faces is not None and len(faces) > 0:
            face = faces[0]
            x, y, fw, fh = int(face[0]), int(face[1]), int(face[2]), int(face[3])
            cv2.rectangle(display_frame, (x, y), (x + fw, y + fh), (0, 220, 80), 2)
            cv2.putText(display_frame, f"Face detected — SPACE to register as '{name}'",
                        (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 220, 80), 2)
        else:
            cv2.putText(display_frame, "No face detected — position your face in frame",
                        (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 60, 255), 2)

        cv2.imshow("Register Face — Universal Face System", display_frame)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            print("Registration cancelled.")
            break
        elif key == ord(' '):
            if faces is not None and len(faces) > 0:
                try:
                    captured_encoding = get_face_feature(frame, faces[0])
                    print(f"✅ Face captured for '{name}'!")
                    break
                except Exception as e:
                    print(f"⚠️ Embedding failed: {e}. Try again.")
            else:
                print("⚠️ No face detected at capture moment. Try again.")

    cap.release()
    cv2.destroyAllWindows()
    return captured_encoding


async def save_to_db(name: str, role: str, encoding: np.ndarray):
    """Saves the face encoding to the SQLite database."""
    await init_db()
    async with AsyncSessionLocal() as session:
        # Check if user already exists
        result = await session.execute(
            select(RegisteredFace).where(RegisteredFace.name == name)
        )
        existing = result.scalars().first()
        if existing:
            print(f"⚠️ '{name}' already exists! Delete first to re-register.")
            return

        new_face = RegisteredFace(name=name, role=role, face_encoding=[encoding])
        session.add(new_face)
        await session.commit()
        print(f"✅ '{name}' successfully registered in the database!")


if __name__ == "__main__":
    name = sys.argv[1] if len(sys.argv) > 1 else "Admin"
    role = sys.argv[2] if len(sys.argv) > 2 else "vip"

    # Step 1: Capture face on main thread (required for OpenCV GUI on Windows)
    encoding = capture_face_sync(name)

    # Step 2: Save to DB using asyncio
    if encoding is not None:
        if sys.platform == 'win32':
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        asyncio.run(save_to_db(name, role, encoding))
    else:
        print("No face registered.")
