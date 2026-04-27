import cv2
import requests
import base64
import time
import os
import numpy as np

# ================= CONFIGURATION =================
# 1. Aapka Railway Cloud URL (Bina '/' ke end mein)
CLOUD_URL = "https://universal-face-system-production.up.railway.app" 

# 2. CAMERA SOURCE: Set to 0 for Laptop Webcam, or URL for IP Camera
# Examples: 0 or "rtsp://admin:pass@192.168.1.5:554/live"
CAMERA_SOURCE = 0 

# 3. P2P / ADVANCED SETTINGS (If using P2P Cloud Cameras)
USE_P2P = False             # Set to True if connecting via P2P Cloud ID
P2P_UID = "UID_HERE"        # Camera UID/Cloud ID
P2P_USER = "admin"          # Camera Username
P2P_PASS = "admin123"       # Camera Password

# 4. SYSTEM SETTINGS
OWNER_ID = 1 
NODE_NAME = "Main_Entrance_Agent"
# =================================================

def run_sentinel_edge():
    print("\n" + "="*40)
    print("   SENTINEL AI - EDGE AGENT v1.1   ")
    print("="*40)
    
    # Check for face detection model
    model_path = "models/face_detection_yunet_2023mar.onnx"
    if not os.path.exists(model_path):
        print(f"ERROR: Model file not found at {model_path}")
        return

    # Initialize Face Detector
    detector = cv2.FaceDetectorYN.create(model_path, "", (320, 320), score_threshold=0.5, nms_threshold=0.3)
    
    source = CAMERA_SOURCE
    if USE_P2P:
        source = f"rtsp://{P2P_USER}:{P2P_PASS}@{P2P_UID}.p2p.cam/live"
        print(f"Connecting via P2P Cloud ID: {P2P_UID}")
    else:
        print(f"Connecting to Camera Source: {source}")
        
    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        print("FAILED: Could not open camera.")
        return

    # Track recognized faces to display labels
    recognized_faces = {} # {id: {"name": str, "expiry": float, "last_sync": float}}
    
    print("AGENT ONLINE: Monitoring stream...")
    
    try:
        while True:
            ret, frame = cap.read()
            if not ret: break

            h, w = frame.shape[:2]
            detector.setInputSize((w, h))
            _, faces = detector.detect(frame)

            current_time = time.time()

            if faces is not None:
                for i, face in enumerate(faces):
                    x, y, fw, fh = map(int, face[:4])
                    face_key = f"face_{i}" 
                    
                    # Draw subtle box
                    cv2.rectangle(frame, (x, y), (x+fw, y+fh), (0, 220, 80), 2)
                    
                    # Periodic Cloud Sync (Cooldown per face slot: 5s)
                    face_data = recognized_faces.get(face_key, {"name": "Scanning...", "expiry": 0, "last_sync": 0})
                    
                    if current_time - face_data["last_sync"] > 5.0:
                        # Extract & Crop
                        pad = 30
                        x1, y1 = max(0, x-pad), max(0, y-pad)
                        x2, y2 = min(w, x+fw+pad), min(h, y+fh+pad)
                        face_crop = frame[y1:y2, x1:x2]
                        
                        if face_crop.size > 0:
                            _, buffer = cv2.imencode('.jpg', face_crop, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
                            img_str = base64.b64encode(buffer).decode('utf-8')
                            
                            try:
                                payload = {"image_base64": img_str, "node_name": NODE_NAME, "owner_id": OWNER_ID}
                                response = requests.post(f"{CLOUD_URL}/api/recognize/crop", json=payload, timeout=3)
                                if response.ok:
                                    res_name = response.json().get('name', 'Unknown')
                                    recognized_faces[face_key] = {
                                        "name": res_name,
                                        "expiry": current_time + 4.0,
                                        "last_sync": current_time
                                    }
                                    print(f"Logged: {res_name}")
                            except:
                                recognized_faces[face_key] = face_data
                                recognized_faces[face_key]["last_sync"] = current_time

                    # Display label
                    display_data = recognized_faces.get(face_key)
                    if display_data and current_time < display_data["expiry"]:
                        label = display_data["name"]
                        cv2.putText(frame, label, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

            cv2.imshow("Sentinel Edge Agent", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    except KeyboardInterrupt:
        print("\nStopping Agent...")
    finally:
        cap.release()
        cv2.destroyAllWindows()
        print("Sentinel Edge Offline.")

if __name__ == "__main__":
    run_sentinel_edge()
