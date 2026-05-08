import cv2
import asyncio
import numpy as np
import sys
import threading
import queue
import time
import os
import base64
import concurrent.futures
from datetime import datetime

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
    DEEPSORT_AVAILABLE = True
except ImportError:
    DeepSort = None  # type: ignore[misc, assignment]
    DEEPSORT_AVAILABLE = False
    print("WARNING: DeepSort not found. Make sure you run via the Python 3.11 Virtual Environment (setup_enterprise.ps1)")

# Fallback simple centroid tracker when DeepSort unavailable
class SimpleCentroidTracker:
    """Fallback tracker using centroid matching"""
    def __init__(self, max_disappeared=30):
        self.next_object_id = 0
        self.objects = {}
        self.disappeared = {}
        self.max_disappeared = max_disappeared
    
    def register(self, centroid):
        self.objects[self.next_object_id] = centroid
        self.disappeared[self.next_object_id] = 0
        self.next_object_id += 1
    
    def deregister(self, object_id):
        del self.objects[object_id]
        del self.disappeared[object_id]
    
    def update(self, rects):
        """Update tracker with detected rectangles"""
        if len(rects) == 0:
            for object_id in list(self.disappeared.keys()):
                self.disappeared[object_id] += 1
                if self.disappeared[object_id] > self.max_disappeared:
                    self.deregister(object_id)
            return self.objects.copy()
        
        # Calculate centroids
        input_centroids = []
        for (startX, startY, endX, endY) in rects:
            cX = (startX + endX) // 2
            cY = (startY + endY) // 2
            input_centroids.append((cX, cY))
        
        if len(self.objects) == 0:
            for i in range(0, len(input_centroids)):
                self.register(input_centroids[i])
        
        return self.objects.copy()

# --- Tunables (env overrides for deployment) ---
JOB_QUEUE_MAXSIZE = int(os.environ.get("SENTINEL_JOB_QUEUE_MAX", "100"))
JOB_QUEUE_TIMEOUT = float(os.environ.get("SENTINEL_JOB_QUEUE_TIMEOUT", "0.5"))  # NEW: timeout for back-pressure
STREAM_CONNECT_RETRIES = int(os.environ.get("SENTINEL_STREAM_RETRIES", "10"))
STREAM_RETRY_DELAY_SEC = float(os.environ.get("SENTINEL_STREAM_RETRY_DELAY", "3"))
FAILED_READ_THRESHOLD = int(os.environ.get("SENTINEL_FAILED_READS", "50"))
READ_FAIL_SLEEP_SEC = float(os.environ.get("SENTINEL_READ_FAIL_SLEEP", "0.1"))
RECONNECT_SLEEP_SEC = float(os.environ.get("SENTINEL_RECONNECT_SLEEP", "2"))
ASYNC_OP_TIMEOUT_SEC = float(os.environ.get("SENTINEL_ASYNC_TIMEOUT", "30"))  # Reduced from 120 for better responsiveness
NODE_THREAD_JOIN_TIMEOUT = float(os.environ.get("SENTINEL_NODE_JOIN_TIMEOUT", "8"))
WORKER_THREAD_JOIN_TIMEOUT = float(os.environ.get("SENTINEL_WORKER_JOIN_TIMEOUT", "30"))
LOOP_THREAD_JOIN_TIMEOUT = float(os.environ.get("SENTINEL_LOOP_JOIN_TIMEOUT", "5"))
DETECT_MAX_WIDTH = int(os.environ.get("SENTINEL_DETECT_MAX_WIDTH", "800"))
DETECT_SCALE_WIDTH = float(os.environ.get("SENTINEL_DETECT_SCALE_WIDTH", "640"))
SHOW_LOCAL_UI = os.environ.get("SENTINEL_HEADLESS", "0").lower() not in ("1", "true", "yes")

# --- Background asyncio event loop ---
_loop = asyncio.new_event_loop()

def _start_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()

_loop_thread = None

def run_async(coro, timeout=ASYNC_OP_TIMEOUT_SEC):
    future = asyncio.run_coroutine_threadsafe(coro, _loop)
    return future.result(timeout=timeout)

# --- Multi-Camera Sentinel Architecture ---
shared_job_queue = queue.Queue(maxsize=JOB_QUEUE_MAXSIZE)
track_identities = {} # Global map: track_id -> "Name"
_identity_lock = threading.Lock()
global_nodes = {} # Global registry: node_name -> node_instance

class SentinelNode:
    def __init__(self, source_id, name="Node", owner_id=None, rotation=None, use_p2p=False, p2p_uid="", p2p_user="admin", p2p_pass=""):
        self.source_id = source_id
        self.name = name
        self.owner_id = owner_id
        self.rotation = rotation 
        self.use_p2p = use_p2p
        self.p2p_uid = p2p_uid
        self.p2p_user = p2p_user
        self.p2p_pass = p2p_pass
        self.use_onvif = False
        self.onvif_port = 80
        self.onvif_user = "admin"
        self.onvif_pass = ""
        self.running = False
        self.status = "Initializing"
        self.tracker = (
            DeepSort(max_age=30, n_init=3, nms_max_overlap=1.0)
            if DEEPSORT_AVAILABLE
            else SimpleCentroidTracker()  # Fallback if DeepSort not available
        )
        self.cap = None
        self._frame_lock = threading.RLock()  # NEW: Thread lock for frame access
        self.last_frame = None # Store the latest processed frame for streaming
        self.fps = 0
        self.active_tracks = 0

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def stop(self):
        """Signal the capture thread to exit; release happens in _run to avoid races."""
        self.running = False
        self.status = "Offline"

    def _run(self):
        try:
            self._run_impl()
        except Exception as e:
            log_print(f"[{self.name}] Fatal error in capture loop: {e}")
            self.status = "Failed"
            self.running = False
        finally:
            if self.cap is not None:
                self.cap.release()
                self.cap = None

    def _run_impl(self):
        source = self.source_id
        if self.use_p2p and self.p2p_uid:
            source = f"rtsp://{self.p2p_user}:{self.p2p_pass}@{self.p2p_uid}.p2p.cam/live"
            log_print(f"INFO: [{self.name}] Connecting via P2P Cloud ID: {self.p2p_uid}")
        else:
            log_print(f"INFO: [{self.name}] Initializing Stream: {source}")
        
        # Retry loop for robust connection (especially for IP cameras)
        max_retries = STREAM_CONNECT_RETRIES
        connected = False
        self.status = "Connecting"
        for i in range(max_retries):
            # Exponential backoff: delay starts at STREAM_RETRY_DELAY_SEC and grows
            current_delay = min(30, STREAM_RETRY_DELAY_SEC * (2 ** i))
            log_print(f"INFO: [{self.name}] Connection attempt {i+1}/{max_retries} (Next retry in {current_delay if i > 0 else 0}s)...")
            
            if self.cap is not None:
                self.cap.release()
                self.cap = None
            
            self.cap = cv2.VideoCapture(source)
            
            if self.cap.isOpened():
                ret, frame = self.cap.read()
                if ret:
                    log_print(f"SUCCESS: [{self.name}] Stream connected and frame captured.")
                    connected = True
                    break
                else:
                    log_print(f"WARNING: [{self.name}] Connected but stream empty.")
            
            if i < max_retries - 1:
                log_print(f"ERROR: [{self.name}] Attempt {i+1} failed. Retrying in {current_delay}s...")
                time.sleep(current_delay)

        if not connected:
            log_print(f"FATAL: [{self.name}] Could not open stream {source}. Check URL/Network.")
            self.status = "Failed"
            self.running = False
            return

        if self.tracker is None:
            log_print(f"FATAL: [{self.name}] DeepSort is not available; cannot track faces.")
            self.status = "Failed"
            self.running = False
            return
        
        self.status = "Online"
        log_print(f"INFO: [{self.name}] Stream Active. Resolution: {self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)}x{self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)}")

        # Initialize local detector for thread safety
        detector_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "face_detection_yunet_2023mar.onnx")
        local_detector = cv2.FaceDetectorYN.create(detector_path, "", (320, 320), score_threshold=0.6, nms_threshold=0.3, top_k=50)

        # Performance Optimization: Frame skipping & Resizing
        frame_skip = 2 if "Phone" in self.name else 0 
        frame_count = 0
        start_time = time.time()

        failed_frames = 0
        while self.running:
            ret, frame = self.cap.read()
            if not ret: 
                failed_frames += 1
                if failed_frames > FAILED_READ_THRESHOLD:
                    log_print(f"[{self.name}] Connection lost. Attempting auto-reconnect...")
                    self.cap.release()
                    self.cap = None
                    time.sleep(RECONNECT_SLEEP_SEC)
                    self.cap = cv2.VideoCapture(source)
                    failed_frames = 0
                else:
                    time.sleep(READ_FAIL_SLEEP_SEC)
                continue
            
            failed_frames = 0
            
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
            if w > DETECT_MAX_WIDTH:
                scale = DETECT_SCALE_WIDTH / w
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
                
                with _identity_lock:
                    name = track_identities.get(node_track_id, "Scanning...")
                
                if name in ["Scanning...", "Blink to Verify", "Wait...", "Blurry...", "Aligning..."]:
                    margin_w = int((r - l) * 0.2)
                    margin_h = int((b - t) * 0.2)
                    ml, mt = max(0, l - margin_w), max(0, t - margin_h)
                    mr, mb = min(w, r + margin_w), min(h, b + margin_h)
                    
                    crop = frame[mt:mb, ml:mr].copy()
                    if crop.size > 0:
                        with _identity_lock:
                            track_identities[node_track_id] = "Detecting..."
                        
                        # NEW: Add job with back-pressure (timeout if queue full)
                        try:
                            shared_job_queue.put(
                                (node_track_id, crop, (ml, mt, mr - ml, mb - mt), (h, w), self.name, self.owner_id),
                                timeout=JOB_QUEUE_TIMEOUT
                            )
                        except queue.Full:
                            log_print(f"[{self.name}] Job queue full, dropping frame to maintain stream FPS")
                            # Try to drop oldest job and add new one
                            try:
                                old_job = shared_job_queue.get_nowait()
                                log_print(f"[{self.name}] Dropped track {old_job[0]} to make room")
                                shared_job_queue.put(
                                    (node_track_id, crop, (ml, mt, mr - ml, mb - mt), (h, w), self.name, self.owner_id),
                                    block=False
                                )
                            except (queue.Empty, queue.Full):
                                pass  # Queue handling race condition
                
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
            with self._frame_lock:  # Acquire lock before writing
                self.last_frame = frame.copy()
            elapsed = time.time() - start_time
            if elapsed > 1:
                self.fps = frame_count / elapsed
                frame_count = 0
                start_time = time.time()

async def process_single_crop(crop_img, location, owner_id, db):
    """Bridge for the Edge Agent to process individual face crops."""
    try:
        ch, cw = crop_img.shape[:2]
        face_id, name = await face_service.process_tracker_crop(
            crop_img,
            [0, 0, cw, ch],
            None,
            location,
            owner_id,
            frame_shape=(ch, cw),
        )
        return face_id, name, 0.99
    except Exception as e:
        log_print(f"Edge Crop Error: {e}")
        return None, "Error", 0.0

def get_telemetry():
    """Returns real-time performance metrics for all nodes."""
    return {
        name: {
            "fps": round(node.fps, 1),
            "active_tracks": node.active_tracks,
            "status": node.status,
            "source": str(node.source_id),
            "live_detections": getattr(node, 'live_detections', [])
        } for name, node in global_nodes.items()
    }

def processing_worker():
    """Shared background worker for all Sentinel nodes."""
    while True:
        job = shared_job_queue.get()
        if job is None: break
        track_id, crop_img, bbox, frame_shape, location, owner_id = job
        try:
            face_id, name = run_async(
                face_service.process_tracker_crop(
                    crop_img, bbox, None, location, owner_id, frame_shape=frame_shape
                )
            )
            with _identity_lock:
                track_identities[track_id] = name
            
            # Store live crop for dashboard autocapture
            if name not in ["Scanning...", "Wait...", "Blurry...", "Aligning...", "Too far", "Error"]:
                _, buffer = cv2.imencode('.jpg', crop_img)
                b64 = "data:image/jpeg;base64," + base64.b64encode(buffer).decode('utf-8')
                
                if location in global_nodes:
                    node = global_nodes[location]
                    if not hasattr(node, 'live_detections'):
                        node.live_detections = []
                    
                    # Prevent spamming the same track ID
                    if not any(d['id'] == track_id for d in node.live_detections):
                        node.live_detections.insert(0, {
                            "id": track_id, 
                            "name": name, 
                            "img": b64, 
                            "time": datetime.now().isoformat()
                        })
                        node.live_detections = node.live_detections[:5] # Keep last 5
                        
        except concurrent.futures.TimeoutError:
            log_print(f"Worker async timeout for track {track_id}")
            with _identity_lock:
                track_identities[track_id] = "Scanning..."
        except Exception as e:
            log_print(f"Worker Error: {e}")
            with _identity_lock:
                track_identities[track_id] = "Scanning..."

# Spawn a thread pool to handle faces in parallel - Reduced for cloud stability
NUM_WORKERS = 2
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
    if not DEEPSORT_AVAILABLE:
        log_print("FATAL: DeepSort is required to run the Sentinel engine. Install dependencies and retry.")
        sys.exit(1)

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
            if SHOW_LOCAL_UI:
                for name, node in global_nodes.items():
                    if node.last_frame is not None:
                        cv2.imshow(f"Sentinel AI: {name}", node.last_frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
            time.sleep(0.03)
    except KeyboardInterrupt:
        pass
    finally:
        if SHOW_LOCAL_UI:
            cv2.destroyAllWindows()
        for n in global_nodes.values():
            n.stop()
        for n in global_nodes.values():
            th = getattr(n, "thread", None)
            if th is not None and th.is_alive():
                th.join(timeout=NODE_THREAD_JOIN_TIMEOUT)
        for _ in range(NUM_WORKERS):
            shared_job_queue.put(None)
        for wt in _worker_threads:
            if wt.is_alive():
                wt.join(timeout=WORKER_THREAD_JOIN_TIMEOUT)
        _loop.call_soon_threadsafe(_loop.stop)
        if _loop_thread is not None and _loop_thread.is_alive():
            _loop_thread.join(timeout=LOOP_THREAD_JOIN_TIMEOUT)

