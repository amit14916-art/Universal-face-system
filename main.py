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

import logging
logging.basicConfig(filename='sentinel.log', level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Sentinel")

def log_print(msg):
    print(msg)
    logger.info(msg)

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

_loop_thread = None

def run_async(coro):
    future = asyncio.run_coroutine_threadsafe(coro, _loop)
    return future.result()

# --- Multi-Camera Sentinel Architecture ---
shared_job_queue = queue.Queue(maxsize=100) # Increased to handle multiple faces simultaneously
track_identities = {} # Global map: track_id -> "Name"
global_nodes = {} # Global registry: node_name -> node_instance

class SentinelNode:
    def __init__(self, source_id, name="Node", rotation=None):
        self.source_id = source_id
        self.name = name
        self.rotation = rotation # None, cv2.ROTATE_90_CLOCKWISE, etc.
        self.running = False
        self.tracker = DeepSort(max_age=30, n_init=3, nms_max_overlap=1.0)
        self.cap = None
        self.last_frame = None # Store the latest processed frame for streaming
        self.fps = 0
        self.active_tracks = 0

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.cap: self.cap.release()

    def _run(self):
        log_print(f"[{self.name}] Initializing Stream: {self.source_id}")
        
        # Retry loop for robust connection (especially for IP cameras)
        max_retries = 5
        for i in range(max_retries):
            self.cap = cv2.VideoCapture(self.source_id)
            if self.cap.isOpened():
                log_print(f"[{self.name}] Successfully connected to stream.")
                break
            log_print(f"[{self.name}] Connection attempt {i+1} failed. Retrying...")
            time.sleep(2)

        if not self.cap or not self.cap.isOpened():
            log_print(f"[{self.name}] Error: Permanent failure reaching source {self.source_id}")
            return

        # Initialize local detector for thread safety
        detector_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "face_detection_yunet_2023mar.onnx")
        local_detector = cv2.FaceDetectorYN.create(detector_path, "", (320, 320), score_threshold=0.6, nms_threshold=0.3, top_k=15)

        # Performance Optimization: Frame skipping & Resizing
        frame_skip = 2 if "Phone" in self.name else 0 
        frame_count = 0
        start_time = time.time()

        while self.running:
            ret, frame = self.cap.read()
            if not ret: 
                time.sleep(0.1)
                continue
            
            frame_count += 1
            if frame_count % (frame_skip + 1) != 0:
                continue

            # Apply Rotation
            if self.rotation is not None:
                frame = cv2.rotate(frame, self.rotation)

            h, w = frame.shape[:2]
            
            # Sub-sampling for faster detection on high-res streams
            detect_frame = frame
            scale = 1.0
            if w > 800:
                scale = 640.0 / w
                detect_frame = cv2.resize(frame, (0,0), fx=scale, fy=scale)
            
            dh, dw = detect_frame.shape[:2]
            local_detector.setInputSize((dw, dh))
            _, faces = local_detector.detect(detect_frame)
            
            bbs = []
            if faces is not None:
                for face in faces:
                    # Rescale boxes back to original size
                    box = [int(face[0]/scale), int(face[1]/scale), int(face[2]/scale), int(face[3]/scale)]
                    confidence = float(face[-1])
                    bbs.append((box, confidence, 'face'))
            
            # Update Object Tracker
            tracks = self.tracker.update_tracks(bbs, frame=frame)
            
            self.active_tracks = len([t for t in tracks if t.is_confirmed()])
            
            for track in tracks:
                if not track.is_confirmed() or track.time_since_update > 1:
                    continue
                
                track_id = track.track_id
                node_track_id = f"{self.name}_{track_id}"
                
                ltrb = track.to_ltrb()
                l, t, r, b = map(int, ltrb)
                l, t, r, b = max(0, l), max(0, t), min(w, r), min(h, b)
                
                name = track_identities.get(node_track_id, "Scanning...")
                
                if name in ["Scanning...", "Blink to Verify", "Wait...", "Blurry...", "Aligning..."] and not shared_job_queue.full():
                    margin_w = int((r - l) * 0.2)
                    margin_h = int((b - t) * 0.2)
                    ml, mt = max(0, l - margin_w), max(0, t - margin_h)
                    mr, mb = min(w, r + margin_w), min(h, b + margin_h)
                    
                    crop = frame[mt:mb, ml:mr].copy()
                    if crop.size > 0:
                        track_identities[node_track_id] = "Detecting..."
                        shared_job_queue.put((node_track_id, crop, (ml, mt, mr-ml, mb-mt), frame.copy(), self.name))
                
                # Visuals
                color = (0, 60, 255) if "Visitor" in name or "BLACKLIST" in name else (0, 220, 80)
                if "Scanning" in name: color = (255, 200, 0)
                
                length = 20
                cv2.line(frame, (l, t), (l + length, t), color, 2)
                cv2.line(frame, (l, t), (l, t + length), color, 2)
                cv2.line(frame, (r, t), (r - length, t), color, 2)
                cv2.line(frame, (r, t), (r, t + length), color, 2)
                cv2.line(frame, (l, b), (l + length, b), color, 2)
                cv2.line(frame, (l, b), (l, b - length), color, 2)
                cv2.line(frame, (r, b), (r - length, b), color, 2)
                cv2.line(frame, (r, b), (r, b - length), color, 2)

                cv2.rectangle(frame, (l, b + 5), (r, b + 30), (20, 20, 20), -1)
                cv2.rectangle(frame, (l, b + 5), (r, b + 30), color, 1)
                cv2.putText(frame, f"{node_track_id}: {name}", (l + 5, b + 24), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)

            # Update FPS and Last Frame
            self.last_frame = frame.copy()
            elapsed = time.time() - start_time
            if elapsed > 1:
                self.fps = frame_count / elapsed
                frame_count = 0
                start_time = time.time()

        self.cap.release()

def get_telemetry():
    """Returns real-time performance metrics for all nodes."""
    return {
        name: {
            "fps": round(node.fps, 1),
            "active_tracks": node.active_tracks,
            "status": "Online" if node.running else "Offline",
            "source": str(node.source_id)
        } for name, node in global_nodes.items()
    }

def processing_worker():
    """Shared background worker for all Sentinel nodes."""
    while True:
        job = shared_job_queue.get()
        if job is None: break
        track_id, crop_img, bbox, full_frame, location = job
        try:
            face_id, name = run_async(face_service.process_tracker_crop(crop_img, bbox, full_frame, location))
            track_identities[track_id] = name
        except Exception as e:
            log_print(f"Worker Error: {e}")
            track_identities[track_id] = "Scanning..."

# Spawn a thread pool to handle up to 10 faces in parallel
NUM_WORKERS = 10
_worker_threads = []

def start_background_workers():
    global _loop_thread, _worker_threads
    
    if _loop_thread is None or not _loop_thread.is_alive():
        _loop_thread = threading.Thread(target=_start_loop, args=(_loop,), daemon=True)
        _loop_thread.start()
        
    if not _worker_threads:
        for _ in range(NUM_WORKERS):
            t = threading.Thread(target=processing_worker, daemon=True)
            t.start()
            _worker_threads.append(t)

# --- Entry Point ---
if __name__ == "__main__":
    start_background_workers()
    run_async(init_db())
    run_async(face_service.load_faiss_db())
    
    sources = [
        {"id": 0, "name": "Main_Hub", "rotation": None}
    ]
    
    for src in sources:
        node = SentinelNode(src["id"], src["name"], rotation=src["rotation"])
        node.start()
        global_nodes[src["name"]] = node

    log_print("Sentinel Engine Online. MJPEG Streams ready for API connection.")
    
    try:
        while any(n.running for n in global_nodes.values()):
            # We no longer need cv2.imshow here as frames are exposed via global_nodes
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        for n in global_nodes.values(): n.stop()
        for _ in range(NUM_WORKERS):
            shared_job_queue.put(None)
        _loop.call_soon_threadsafe(_loop.stop)

