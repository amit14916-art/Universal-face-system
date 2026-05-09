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
        self.exercise_states = {
            "Squats": "up",
            "Bicep Curls": "down",
            "Lunges": "up"
        }
        self.reps = {
            "Squats": 0,
            "Bicep Curls": 0,
            "Lunges": 0
        }
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
            return frame, {
                "exercise": "Detecting...",
                "reps": 0,
                "height": 0,
                "body_fat": 0
            }

        landmarks = results.pose_landmarks.landmark
        
        try:
            # 1. Height Estimation (Rough)
            nose = landmarks[0]
            l_ankle = landmarks[27]
            r_ankle = landmarks[28]
            mid_ankle_y = (l_ankle.y + r_ankle.y) / 2
            estimated_height = (mid_ankle_y - nose.y) * 220 
            
            # 2. Exercise Detection & Rep Counting
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

            # --- Logic for Each Exercise ---
            
            # A. SQUATS
            if l_knee_angle < 110:
                self.current_exercise = "Squats"
                if l_knee_angle < 90 and self.exercise_states["Squats"] == "up":
                    self.exercise_states["Squats"] = "down"
                if l_knee_angle > 160 and self.exercise_states["Squats"] == "down":
                    self.reps["Squats"] += 1
                    self.exercise_states["Squats"] = "up"
            
            # B. BICEP CURLS
            elif l_elbow_angle < 100:
                self.current_exercise = "Bicep Curls"
                if l_elbow_angle < 40 and self.exercise_states["Bicep Curls"] == "down":
                    self.exercise_states["Bicep Curls"] = "up"
                if l_elbow_angle > 140 and self.exercise_states["Bicep Curls"] == "up":
                    self.reps["Bicep Curls"] += 1
                    self.exercise_states["Bicep Curls"] = "down"
            
            # C. LUNGES
            elif l_hip_angle < 110:
                self.current_exercise = "Lunges"
                if l_hip_angle < 90 and self.exercise_states["Lunges"] == "up":
                    self.exercise_states["Lunges"] = "down"
                if l_hip_angle > 150 and self.exercise_states["Lunges"] == "down":
                    self.reps["Lunges"] += 1
                    self.exercise_states["Lunges"] = "up"
            
            else:
                # If no clear exercise movement, but we were just doing something, keep it but don't count
                if l_knee_angle > 160 and l_elbow_angle > 160 and l_hip_angle > 160:
                     self.current_exercise = "Standing"

            # 4. Body Fat Estimation
            shoulder_width = np.linalg.norm(np.array([landmarks[11].x, landmarks[11].y]) - np.array([landmarks[12].x, landmarks[12].y]))
            waist_width = np.linalg.norm(np.array([landmarks[23].x, landmarks[23].y]) - np.array([landmarks[24].x, landmarks[24].y]))
            v_ratio = waist_width / (shoulder_width + 1e-6)
            estimated_body_fat = v_ratio * 30 
            
            # Draw Landmarks
            self.mp_draw.draw_landmarks(frame, results.pose_landmarks, self.mp_pose.POSE_CONNECTIONS)
            
            # Overlay Info (Live on frame)
            cv2.putText(frame, f"AI Detected: {self.current_exercise}", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 3)
            current_reps = self.reps.get(self.current_exercise, 0)
            cv2.putText(frame, f"Reps: {current_reps}", (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 3)

            analysis_data = {
                "exercise": self.current_exercise,
                "reps": current_reps,
                "height": int(estimated_height),
                "body_fat": int(estimated_body_fat)
            }
            return frame, analysis_data

        except Exception as e:
            logger.error(f"Analysis error: {e}")
            return frame, {
                "exercise": "Error",
                "reps": 0,
                "height": 0,
                "body_fat": 0
            }

