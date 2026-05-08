import cv2
import mediapipe as mp
import numpy as np
import os
import time

# --- CONFIGURATION ---
INPUT_VIDEO = "premium_raw.mp4"  # Aapki raw video file
OUTPUT_VIDEO = "premium_demo.mp4"
EXERCISE_TYPE = "Squats"  # Options: Squats, Pushups, Bicep Curls

# Initialize MediaPipe
mp_pose = mp.solutions.pose
mp_face_detection = mp.solutions.face_detection
pose = mp_pose.Pose(static_image_mode=False, model_complexity=1, min_detection_confidence=0.5)
face_detection = mp_face_detection.FaceDetection(model_selection=1, min_detection_confidence=0.5)
mp_drawing = mp.solutions.drawing_utils

def calculate_angle(a, b, c):
    a = np.array(a)
    b = np.array(b)
    c = np.array(c)
    radians = np.math.atan2(c[1]-b[1], c[0]-b[0]) - np.math.atan2(a[1]-b[1], a[0]-b[0])
    angle = np.abs(radians*180.0/np.pi)
    if angle > 180.0: angle = 360-angle
    return angle

def process_video():
    if not os.path.exists(INPUT_VIDEO):
        print(f"Error: {INPUT_VIDEO} not found!")
        return

    cap = cv2.VideoCapture(INPUT_VIDEO)
    width  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps    = cap.get(cv2.CAP_PROP_FPS)
    
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(OUTPUT_VIDEO, fourcc, fps, (width, height))

    counter = 0
    stage = "up"
    print("Processing AI Video with Advanced Tracking...")

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret: break

        # 1. Advanced Face Detection (MediaPipe)
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        face_results = face_detection.process(rgb_frame)
        
        if face_results.detections:
            for detection in face_results.detections:
                bboxC = detection.location_data.relative_bounding_box
                ih, iw, ic = frame.shape
                bbox = int(bboxC.xmin * iw), int(bboxC.ymin * ih), \
                       int(bboxC.width * iw), int(bboxC.height * ih)
                
                # Cyberpunk Face Box
                x, y, w, h = bbox
                cv2.rectangle(frame, (x, y), (x+w, y+h), (255, 200, 0), 2)
                # Corner accents
                length = 20
                cv2.line(frame, (x, y), (x + length, y), (255, 255, 255), 4)
                cv2.line(frame, (x, y), (x, y + length), (255, 255, 255), 4)
                
                cv2.putText(frame, "ID: MEMBER_042 | VERIFIED", (x, y-15), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

        # 2. Pose Estimation
        pose_results = pose.process(rgb_frame)

        if pose_results.pose_landmarks:
            # Draw Skeleton
            mp_drawing.draw_landmarks(frame, pose_results.pose_landmarks, mp_pose.POSE_CONNECTIONS,
                                     mp_drawing.DrawingSpec(color=(0, 255, 0), thickness=2, circle_radius=2),
                                     mp_drawing.DrawingSpec(color=(255, 255, 255), thickness=2, circle_radius=2))

            landmarks = pose_results.pose_landmarks.landmark
            
            # Rep Counting Logic (Squats/Deadlift Example)
            # Use hip, knee, ankle for squats
            hip = [landmarks[mp_pose.PoseLandmark.LEFT_HIP.value].x, landmarks[mp_pose.PoseLandmark.LEFT_HIP.value].y]
            knee = [landmarks[mp_pose.PoseLandmark.LEFT_KNEE.value].x, landmarks[mp_pose.PoseLandmark.LEFT_KNEE.value].y]
            ankle = [landmarks[mp_pose.PoseLandmark.LEFT_ANKLE.value].x, landmarks[mp_pose.PoseLandmark.LEFT_ANKLE.value].y]
            
            angle = calculate_angle(hip, knee, ankle)

            if angle > 160:
                if stage == "down":
                    counter += 1
                stage = "up"
            if angle < 110: # Adjusted for Deadlifts/Squats
                stage = "down"

        # 3. Premium HUD (Heads-up Display)
        # Overlay a dark rectangle for stats
        overlay = frame.copy()
        cv2.rectangle(overlay, (20, 20), (350, 150), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)

        cv2.putText(frame, f"AI WORKOUT COACH", (40, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        cv2.putText(frame, f"REPS: {counter}", (40, 90), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 0), 3)
        cv2.putText(frame, f"FORM: {stage.upper()}", (40, 130), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

        out.write(frame)

    cap.release()
    out.release()
    print(f"Success! Video saved as {OUTPUT_VIDEO}")

if __name__ == "__main__":
    process_video()
