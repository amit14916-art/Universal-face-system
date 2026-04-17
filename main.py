import cv2
import asyncio
import numpy as np
import sys
import threading
import queue
import time
import os

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

from database import init_db
import face_service

try:
    from deep_sort_realtime.deepsort_tracker import DeepSort
except ImportError:
    print("WARNING: DeepSort not found. Make sure you run via the Python 3.11 Virtual Environment (setup_enterprise.ps1)")

# --- Background asyncio event loop ---
_loop = asyncio.new_event_loop()

def _start_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()

_loop_thread = threading.Thread(target=_start_loop, args=(_loop,), daemon=True)
_loop_thread.start()

def run_async(coro):
    future = asyncio.run_coroutine_threadsafe(coro, _loop)
    return future.result()

# --- SOTA Background Threading ---
job_queue = queue.Queue(maxsize=10)
track_identities = {} # map: track_id -> "Name"

def processing_worker():
    """Identifies tracks in the background using DeepFace + FAISS + Liveness."""
    while True:
        job = job_queue.get()
        if job is None: break
        track_id, crop_img, bbox, full_frame = job
        try:
            face_id, name = run_async(face_service.process_tracker_crop(crop_img, bbox, full_frame))
            track_identities[track_id] = name
        except Exception as e:
            track_identities[track_id] = "Scanning..."

_worker_thread = threading.Thread(target=processing_worker, daemon=True)
_worker_thread.start()

# Fast Native Detector for 60FPS Tracking Base
detector_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "face_detection_yunet_2023mar.onnx")
face_detector = cv2.FaceDetectorYN.create(detector_path, "", (320, 320), score_threshold=0.6, nms_threshold=0.3, top_k=15)

def capture_loop():
    print("Initializing Enterprise Tracker...")
    tracker = DeepSort(max_age=30, n_init=3, nms_max_overlap=1.0)
    
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Error: Could not open webcam.")
        return

    print("Started Enterprise System. Press 'Q' to quit.")

    try:
        while True:
            ret, frame = cap.read()
            if not ret: continue
            
            h, w = frame.shape[:2]
            face_detector.setInputSize((w, h))
            _, faces = face_detector.detect(frame)
            
            bbs = []
            if faces is not None:
                for face in faces:
                    box = [int(face[0]), int(face[1]), int(face[2]), int(face[3])]
                    confidence = float(face[-1])
                    bbs.append((box, confidence, 'face'))
            
            # Update Object Tracker (Zero lag)
            tracks = tracker.update_tracks(bbs, frame=frame)
            
            for track in tracks:
                if not track.is_confirmed() or track.time_since_update > 1:
                    continue
                
                track_id = track.track_id
                ltrb = track.to_ltrb()
                l, t, r, b = map(int, ltrb)
                
                # Keep bounds valid
                l = max(0, l); t = max(0, t); r = min(w, r); b = min(h, b)
                
                name = track_identities.get(track_id, "Scanning...")
                
                # If unknown/scanning, send to background AI worker
                if name in ["Scanning...", "Blink to Verify", "Aligning...", "Too far", "Wait...", "Blurry..."] and not job_queue.full():
                    crop = frame[t:b, l:r].copy()
                    if crop.size > 0:
                        track_identities[track_id] = "Detecting..."
                        job_queue.put((track_id, crop, (l, t, r-l, b-t), frame.copy()))
                
                # Draw Premium Sentinel Overlay
                color = (0, 60, 255) if "Visitor" in name or "SPOOF" in name else (0, 220, 80)
                if name == "Scanning...": color = (255, 200, 0)
                
                # Sophisticated corner-only box
                length = 20
                cv2.line(frame, (l, t), (l + length, t), color, 2)
                cv2.line(frame, (l, t), (l, t + length), color, 2)
                cv2.line(frame, (r, t), (r - length, t), color, 2)
                cv2.line(frame, (r, t), (r, t + length), color, 2)
                cv2.line(frame, (l, b), (l + length, b), color, 2)
                cv2.line(frame, (l, b), (l, b - length), color, 2)
                cv2.line(frame, (r, b), (r - length, b), color, 2)
                cv2.line(frame, (r, b), (r, b - length), color, 2)

                # Glassy text plate
                cv2.rectangle(frame, (l, b + 5), (r, b + 30), (20, 20, 20), -1)
                cv2.rectangle(frame, (l, b + 5), (r, b + 30), color, 1)
                cv2.putText(frame, f"ID-{track_id}: {name}", (l + 5, b + 24), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)


            cv2.imshow("Enterprise Sentinel Node", frame)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
                
    except KeyboardInterrupt:
        pass
    finally:
        cap.release()
        cv2.destroyAllWindows()
        job_queue.put(None)
        _loop.call_soon_threadsafe(_loop.stop)

if __name__ == "__main__":
    run_async(init_db())
    run_async(face_service.load_faiss_db())
    capture_loop()
