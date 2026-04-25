import cv2
import requests
import base64
import time
import os
import numpy as np

# ================= CONFIGURATION =================
# 1. Aapka Railway Cloud URL (Bina '/' ke end mein)
CLOUD_URL = "https://universal-face-system-production.up.railway.app" 

# 2. Aapke Phone ka Local IP (IP Webcam App se)
CAMERA_IP = "10.113.80.118:8080" 

# 3. Dashboard se milne wala Owner ID
OWNER_ID = 1 

# 4. Iss Camera ka naam (Logs mein dikhega)
NODE_NAME = "Main_Gym_Entrance"
# =================================================

def run_sentinel_edge():
    print("\n" + "="*40)
    print("   SENTINEL AI - EDGE AGENT v1.0   ")
    print("="*40)
    
    # Check for face detection model
    model_path = "models/face_detection_yunet_2023mar.onnx"
    if not os.path.exists(model_path):
        print(f"❌ ERROR: Model file not found at {model_path}")
        print("Please make sure the 'models' folder is in the same directory.")
        return

    # Initialize Local Face Detector (YuNet)
    # This runs on your laptop CPU - very fast!
    # Lowered threshold to 0.5 for better sensitivity in low light
    detector = cv2.FaceDetectorYN.create(model_path, "", (320, 320), score_threshold=0.5, nms_threshold=0.3)
    
    stream_url = f"http://{CAMERA_IP}/video"
    print(f"🔗 Connecting to Local Camera: {stream_url}")
    
    cap = cv2.VideoCapture(stream_url)
    if not cap.isOpened():
        print("❌ FAILED: Could not reach camera. Is the IP correct and Phone App running?")
        return

    print("✅ CONNECTED: Scanning for faces... (Press 'Q' to Stop)")
    
    last_detected_time = 0
    cooldown = 4 # Seconds to wait before sending the same person again

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("⚠️ Stream lost. Reconnecting in 3s...")
                time.sleep(3)
                cap = cv2.VideoCapture(stream_url)
                continue

            # Process Frame
            h, w = frame.shape[:2]
            # Ensure input size is multiple of 4 as required by some versions of YuNet
            detector.setInputSize((w, h))
            _, faces = detector.detect(frame)

            if faces is not None:
                print(f"DEBUG: Found {len(faces)} potential faces.")
                for face in faces:
                    # Capture time check (Bandwidth bachaane ke liye)
                    if time.time() - last_detected_time < cooldown:
                        continue

                    # Extract & Crop Face
                    x, y, fw, fh = map(int, face[:4])
                    # Add padding for better recognition
                    pad = 30
                    x1, y1 = max(0, x-pad), max(0, y-pad)
                    x2, y2 = min(w, x+fw+pad), min(h, y+fh+pad)
                    
                    face_crop = frame[y1:y2, x1:x2]
                    if face_crop.size == 0: continue

                    # Convert to Base64 (Tiny JPG)
                    _, buffer = cv2.imencode('.jpg', face_crop, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
                    img_str = base64.b64encode(buffer).decode('utf-8')

                    # Send to Railway Cloud
                    print(f"🚀 Face Detected! Syncing with Cloud Dashboard...")
                    try:
                        payload = {
                            "image_base64": img_str,
                            "node_name": NODE_NAME,
                            "owner_id": OWNER_ID
                        }
                        response = requests.post(f"{CLOUD_URL}/api/recognize/crop", json=payload, timeout=5)
                        
                        if response.ok:
                            result = response.json()
                            name = result.get('name', 'Unknown')
                            print(f"✅ SUCCESS: Logged {name} into Dashboard.")
                            last_detected_time = time.time()
                        else:
                            print(f"❌ CLOUD ERROR: {response.status_code}")
                    except Exception as e:
                        print(f"❌ SYNC FAILED: {e}")

            # Local Preview (Video laptop par hi rahega)
            # Boxes draw karein (Sirf laptop par dikhega)
            if faces is not None:
                for face in faces:
                    x, y, w_f, h_f = map(int, face[:4])
                    cv2.rectangle(frame, (x, y), (x+w_f, y+h_f), (0, 255, 0), 2)

            cv2.imshow("Sentinel Edge - Local Stream", frame)
            
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
