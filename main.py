import cv2
import asyncio
import numpy as np
import sys
import threading

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

from database import init_db
import face_service

# --- Background asyncio event loop (for DB calls) ---
_loop = asyncio.new_event_loop()

def _start_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()

_loop_thread = threading.Thread(target=_start_loop, args=(_loop,), daemon=True)
_loop_thread.start()


def run_async(coro):
    """Submit an async coroutine to the background event loop and wait for result."""
    future = asyncio.run_coroutine_threadsafe(coro, _loop)
    return future.result()


def process_frame(frame: np.ndarray):
    """
    Runs face detection and matching synchronously by dispatching
    async DB calls to the background event loop.
    """
    face_locations, face_encodings = run_async(face_service.get_face_embeddings(frame))

    if not face_encodings:
        return frame

    face_names = []
    for encoding in face_encodings:
        face_id, name = run_async(face_service.match_face(encoding))
        if face_id is not None:
            print(f"✅ Access Granted: {name}")
        else:
            print("❌ Access Denied: Unknown Face")
        face_names.append(name)

    frame = face_service.draw_metadata(frame, face_locations, face_names)
    return frame


def capture_loop():
    """Main webcam loop — runs on the main thread (required for OpenCV GUI on Windows)."""
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("❌ Error: Could not open webcam.")
        return

    print("✅ Started face recognition. Press 'Q' to quit.")

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("❌ Failed to capture frame.")
                break

            frame = process_frame(frame)
            cv2.imshow("Universal Face System", frame)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                print("Quitting...")
                break
    except KeyboardInterrupt:
        pass
    finally:
        cap.release()
        cv2.destroyAllWindows()
        _loop.call_soon_threadsafe(_loop.stop)


if __name__ == "__main__":
    # Initialize database first (synchronously from background loop)
    run_async(init_db())
    # Run webcam on main thread
    capture_loop()
