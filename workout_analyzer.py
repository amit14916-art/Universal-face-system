import cv2
import mediapipe as mp
import numpy as np
import time
import logging

logger = logging.getLogger("WorkoutAnalyzer")

class WorkoutAnalyzer:
    def __init__(self):
        self.mp_pose = mp.solutions.pose
        self.pose = self.mp_pose.Pose(
            static_image_mode=False,
            model_complexity=1,
            smooth_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )
        self.mp_draw = mp.solutions.drawing_utils
        
        # State tracking for rep counting
        self.exercise_state = "up"
        self.reps = 0
        self.current_exercise = "Detecting..."
        self.confidence = 0.0
        
        # Performance metrics
        self.last_process_time = 0
        
        # Auto-detection history
        self.exercise_history = []
        
    def calculate_angle(self, a, b, c):
        a = np.array(a) # First
        b = np.array(b) # Mid
        c = np.array(c) # End
        
        radians = np.arctan2(c[1]-b[1], c[0]-b[0]) - np.arctan2(a[1]-b[1], a[0]-b[0])
        angle = np.abs(radians*180.0/np.pi)
        
        if angle > 180.0:
            angle = 360-angle
            
        return angle

    def analyze_frame(self, frame):
        """Processes a frame to detect pose and analyze workout."""
        results = self.pose.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        
        if not results.pose_landmarks:
            return frame, None

        landmarks = results.pose_landmarks.landmark
        
        # Get coordinates for key joints
        # 11: L Shoulder, 12: R Shoulder
        # 23: L Hip, 24: R Hip
        # 25: L Knee, 26: R Knee
        # 27: L Ankle, 28: R Ankle
        # 13: L Elbow, 14: R Elbow
        # 15: L Wrist, 16: R Wrist
        
        try:
            # 1. Height Estimation (Rough)
            # Use distance from nose to mid-ankle as a proxy for height
            nose = landmarks[0]
            l_ankle = landmarks[27]
            r_ankle = landmarks[28]
            mid_ankle_y = (l_ankle.y + r_ankle.y) / 2
            
            # This is relative to the frame height. 
            # To get real height, we'd need distance from camera.
            # We'll use a heuristic: 1.0 (top to bottom) is ~200cm
            estimated_height = (mid_ankle_y - nose.y) * 220 # placeholder scale
            
            # 2. Exercise Detection
            # Check angles to see what's moving
            l_knee_angle = self.calculate_angle(
                [landmarks[23].x, landmarks[23].y],
                [landmarks[25].x, landmarks[25].y],
                [landmarks[27].x, landmarks[27].y]
            )
            
            l_elbow_angle = self.calculate_angle(
                [landmarks[11].x, landmarks[11].y],
                [landmarks[13].x, landmarks[13].y],
                [landmarks[15].x, landmarks[15].y]
            )
            
            l_hip_angle = self.calculate_angle(
                [landmarks[11].x, landmarks[11].y],
                [landmarks[23].x, landmarks[23].y],
                [landmarks[25].x, landmarks[25].y]
            )

            # Auto-detect logic
            new_exercise = "Standing"
            if l_knee_angle < 140:
                new_exercise = "Squatting"
            elif l_elbow_angle < 100:
                new_exercise = "Bicep Curls"
            elif l_hip_angle < 100:
                new_exercise = "Lunges"
                
            if new_exercise != self.current_exercise:
                self.current_exercise = new_exercise
                
            # 3. Rep Counting (Squat example)
            if self.current_exercise == "Squatting":
                if l_knee_angle < 90 and self.exercise_state == "up":
                    self.exercise_state = "down"
                if l_knee_angle > 160 and self.exercise_state == "down":
                    self.reps += 1
                    self.exercise_state = "up"
            
            # 4. Body Fat Estimation (Rough Visual)
            # Use Waist-to-Shoulder ratio
            shoulder_width = np.linalg.norm(np.array([landmarks[11].x, landmarks[11].y]) - np.array([landmarks[12].x, landmarks[12].y]))
            waist_width = np.linalg.norm(np.array([landmarks[23].x, landmarks[23].y]) - np.array([landmarks[24].x, landmarks[24].y]))
            
            v_ratio = waist_width / (shoulder_width + 1e-6)
            # Heuristic: 0.7-0.8 is athletic, 0.9+ is higher body fat
            estimated_body_fat = v_ratio * 30 # very rough
            
            # Draw Landmarks
            self.mp_draw.draw_landmarks(frame, results.pose_landmarks, self.mp_pose.POSE_CONNECTIONS)
            
            # Overlay Info
            cv2.putText(frame, f"Exercise: {self.current_exercise}", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            cv2.putText(frame, f"Reps: {self.reps}", (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            cv2.putText(frame, f"Est. Height: {int(estimated_height)}cm", (50, 150), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 1)
            cv2.putText(frame, f"Est. Body Fat: {int(estimated_body_fat)}%", (50, 180), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 1)

            analysis_data = {
                "exercise": self.current_exercise,
                "reps": self.reps,
                "height": int(estimated_height),
                "body_fat": int(estimated_body_fat)
            }
            return frame, analysis_data

        except Exception as e:
            logger.error(f"Analysis error: {e}")
            return frame, None
