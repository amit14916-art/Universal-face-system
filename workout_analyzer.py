import cv2
import mediapipe as mp
import numpy as np
import time
import logging

logger = logging.getLogger("WorkoutAnalyzer")

class HeartRateMonitor:
    def __init__(self, buffer_size=150):
        self.buffer_size = buffer_size
        self.data_buffer = []
        self.times = []
        self.bpm = 72
        self.last_update = time.time()
        
    def update(self, face_roi):
        if face_roi is None or face_roi.size == 0:
            return self.bpm
            
        # rPPG Logic: Green channel spatial average
        # Green channel has the best signal-to-noise ratio for blood volume pulse
        avg_green = np.mean(face_roi[:, :, 1])
        
        self.data_buffer.append(avg_green)
        self.times.append(time.time())
        
        if len(self.data_buffer) > self.buffer_size:
            self.data_buffer.pop(0)
            self.times.pop(0)
            
        # Only calculate if we have enough data (at least 3-4 seconds)
        if len(self.data_buffer) >= self.buffer_size and time.time() - self.last_update > 1.0:
            try:
                # 1. Detrend and Normalize
                signal = np.array(self.data_buffer)
                signal = (signal - np.mean(signal)) / (np.std(signal) + 1e-6)
                
                # 2. Fast Fourier Transform
                fps = len(self.data_buffer) / (self.times[-1] - self.times[0])
                freqs = np.fft.rfftfreq(len(signal), d=1.0/fps)
                fft_magnitude = np.abs(np.fft.rfft(signal))
                
                # 3. Bandpass Filter (0.75 - 3 Hz -> 45 - 180 BPM)
                valid_idx = np.where((freqs >= 0.75) & (freqs <= 3.0))[0]
                if len(valid_idx) > 0:
                    best_freq = freqs[valid_idx[np.argmax(fft_magnitude[valid_idx])]]
                    detected_bpm = best_freq * 60
                    
                    # Smooth the BPM result
                    self.bpm = int(0.7 * self.bpm + 0.3 * detected_bpm)
                    self.last_update = time.time()
            except Exception as e:
                logger.error(f"rPPG Error: {e}")
                
        return self.bpm

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
        self.hr_monitor = HeartRateMonitor()
        
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
        h, w = frame.shape[:2]
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
            # 1. Heart Rate Monitoring (rPPG)
            # Use nose landmark (0) as the center for ROI
            nose = landmarks[0]
            nx, ny = int(nose.x * w), int(nose.y * h)
            roi_size = 30
            if 0 < nx-roi_size < w and 0 < ny-roi_size < h:
                face_roi = frame[ny-roi_size:ny+roi_size, nx-roi_size:nx+roi_size]
                # Draw ROI for feedback
                cv2.rectangle(frame, (nx-roi_size, ny-roi_size), (nx+roi_size, ny+roi_size), (0, 200, 255), 1)
                estimated_hr = self.hr_monitor.update(face_roi)
            else:
                estimated_hr = 72 # Default

            # 2. Biometric Estimations (Heuristics)
            l_ankle = landmarks[27]
            r_ankle = landmarks[28]
            mid_ankle_y = (l_ankle.y + r_ankle.y) / 2
            estimated_height = (mid_ankle_y - nose.y) * 220 
            
            # B. Weight & Body Fat
            shoulder_width = np.linalg.norm(np.array([landmarks[11].x, landmarks[11].y]) - np.array([landmarks[12].x, landmarks[12].y]))
            waist_width = np.linalg.norm(np.array([landmarks[23].x, landmarks[23].y]) - np.array([landmarks[24].x, landmarks[24].y]))
            v_ratio = waist_width / (shoulder_width + 1e-6)
            h_m = estimated_height / 100.0
            estimated_weight = (h_m ** 2) * (shoulder_width * 150) + (v_ratio * 20)
            estimated_body_fat = v_ratio * 30 
            
            # 3. Exercise Detection & Rep Counting
            l_knee_angle = self.calculate_angle([landmarks[23].x, landmarks[23].y], [landmarks[25].x, landmarks[25].y], [landmarks[27].x, landmarks[27].y])
            l_elbow_angle = self.calculate_angle([landmarks[11].x, landmarks[11].y], [landmarks[13].x, landmarks[13].y], [landmarks[15].x, landmarks[15].y])
            l_hip_angle = self.calculate_angle([landmarks[11].x, landmarks[11].y], [landmarks[23].x, landmarks[23].y], [landmarks[25].x, landmarks[25].y])

            if l_knee_angle < 110:
                self.current_exercise = "Squats"
                if l_knee_angle < 90 and self.exercise_states["Squats"] == "up":
                    self.exercise_states["Squats"] = "down"
                if l_knee_angle > 160 and self.exercise_states["Squats"] == "down":
                    self.reps["Squats"] += 1
                    self.exercise_states["Squats"] = "up"
            elif l_elbow_angle < 100:
                self.current_exercise = "Bicep Curls"
                if l_elbow_angle < 40 and self.exercise_states["Bicep Curls"] == "down":
                    self.exercise_states["Bicep Curls"] = "up"
                if l_elbow_angle > 140 and self.exercise_states["Bicep Curls"] == "up":
                    self.reps["Bicep Curls"] += 1
                    self.exercise_states["Bicep Curls"] = "down"
            elif l_hip_angle < 110:
                self.current_exercise = "Lunges"
                if l_hip_angle < 90 and self.exercise_states["Lunges"] == "up":
                    self.exercise_states["Lunges"] = "down"
                if l_hip_angle > 150 and self.exercise_states["Lunges"] == "down":
                    self.reps["Lunges"] += 1
                    self.exercise_states["Lunges"] = "up"
            else:
                if l_knee_angle > 160 and l_elbow_angle > 160 and l_hip_angle > 160:
                     self.current_exercise = "Standing"

            # Visuals
            self.mp_draw.draw_landmarks(frame, results.pose_landmarks, self.mp_pose.POSE_CONNECTIONS)
            cv2.putText(frame, f"AI: {self.current_exercise} | REPS: {self.reps.get(self.current_exercise, 0)}", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            cv2.putText(frame, f"rPPG Pulse: {int(estimated_hr)} BPM", (50, 85), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 200, 255), 2)
            cv2.putText(frame, f"H: {int(estimated_height)}cm | W: {int(estimated_weight)}kg | BF: {int(estimated_body_fat)}%", (50, 115), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

            analysis_data = {
                "exercise": self.current_exercise,
                "reps": self.reps.get(self.current_exercise, 0),
                "height": int(estimated_height),
                "weight": int(estimated_weight),
                "body_fat": int(estimated_body_fat),
                "heart_rate": int(estimated_hr)
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

