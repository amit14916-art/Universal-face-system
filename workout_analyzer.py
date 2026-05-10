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
            "Lunges": "up",
            "Pushups": "up",
            "Shoulder Press": "down",
            "Sit-ups": "down",
            "Deadlifts": "up"
        }
        self.reps = {
            "Squats": 0,
            "Bicep Curls": 0,
            "Lunges": 0,
            "Pushups": 0,
            "Shoulder Press": 0,
            "Sit-ups": 0,
            "Deadlifts": 0
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
            nose = landmarks[0]
            nx, ny = int(nose.x * w), int(nose.y * h)
            roi_size = 30
            if 0 < nx-roi_size < w and 0 < ny-roi_size < h:
                face_roi = frame[ny-roi_size:ny+roi_size, nx-roi_size:nx+roi_size]
                cv2.rectangle(frame, (nx-roi_size, ny-roi_size), (nx+roi_size, ny+roi_size), (0, 200, 255), 1)
                estimated_hr = self.hr_monitor.update(face_roi)
            else:
                estimated_hr = 72

            # 2. Biometric Estimations
            l_ankle = landmarks[27]
            r_ankle = landmarks[28]
            mid_ankle_y = (l_ankle.y + r_ankle.y) / 2
            estimated_height = (mid_ankle_y - nose.y) * 220 
            
            shoulder_width = np.linalg.norm(np.array([landmarks[11].x, landmarks[11].y]) - np.array([landmarks[12].x, landmarks[12].y]))
            waist_width = np.linalg.norm(np.array([landmarks[23].x, landmarks[23].y]) - np.array([landmarks[24].x, landmarks[24].y]))
            v_ratio = waist_width / (shoulder_width + 1e-6)
            h_m = estimated_height / 100.0
            estimated_weight = (h_m ** 2) * (shoulder_width * 150) + (v_ratio * 20)
            estimated_body_fat = v_ratio * 30 
            
            # 3. Enhanced Exercise Detection Logic
            # Key Angles
            l_elbow = self.calculate_angle([landmarks[11].x, landmarks[11].y], [landmarks[13].x, landmarks[13].y], [landmarks[15].x, landmarks[15].y])
            r_elbow = self.calculate_angle([landmarks[12].x, landmarks[12].y], [landmarks[14].x, landmarks[14].y], [landmarks[16].x, landmarks[16].y])
            l_shoulder = self.calculate_angle([landmarks[13].x, landmarks[13].y], [landmarks[11].x, landmarks[11].y], [landmarks[23].x, landmarks[23].y])
            r_shoulder = self.calculate_angle([landmarks[14].x, landmarks[14].y], [landmarks[12].x, landmarks[12].y], [landmarks[24].x, landmarks[24].y])
            l_hip = self.calculate_angle([landmarks[11].x, landmarks[11].y], [landmarks[23].x, landmarks[23].y], [landmarks[25].x, landmarks[25].y])
            r_hip = self.calculate_angle([landmarks[12].x, landmarks[12].y], [landmarks[24].x, landmarks[24].y], [landmarks[26].x, landmarks[26].y])
            l_knee = self.calculate_angle([landmarks[23].x, landmarks[23].y], [landmarks[25].x, landmarks[25].y], [landmarks[27].x, landmarks[27].y])
            r_knee = self.calculate_angle([landmarks[24].x, landmarks[24].y], [landmarks[26].x, landmarks[26].y], [landmarks[28].x, landmarks[28].y])

            # Horizontal/Vertical checks
            is_lying = abs(landmarks[11].y - landmarks[23].y) < 0.2
            hands_above_head = landmarks[15].y < landmarks[0].y and landmarks[16].y < landmarks[0].y

            # Exercise Heuristics
            if is_lying and (l_elbow < 100 or r_elbow < 100):
                self.current_exercise = "Pushups"
                if min(l_elbow, r_elbow) < 80 and self.exercise_states["Pushups"] == "up":
                    self.exercise_states["Pushups"] = "down"
                if min(l_elbow, r_elbow) > 160 and self.exercise_states["Pushups"] == "down":
                    self.reps["Pushups"] += 1
                    self.exercise_states["Pushups"] = "up"
            
            elif hands_above_head:
                self.current_exercise = "Shoulder Press"
                if min(l_elbow, r_elbow) < 70 and self.exercise_states["Shoulder Press"] == "up":
                    self.exercise_states["Shoulder Press"] = "down"
                if min(l_elbow, r_elbow) > 150 and self.exercise_states["Shoulder Press"] == "down":
                    self.reps["Shoulder Press"] += 1
                    self.exercise_states["Shoulder Press"] = "up"

            elif is_lying and (l_hip < 100 or r_hip < 100):
                self.current_exercise = "Sit-ups"
                if min(l_hip, r_hip) < 80 and self.exercise_states["Sit-ups"] == "down":
                    self.exercise_states["Sit-ups"] = "up"
                if min(l_hip, r_hip) > 130 and self.exercise_states["Sit-ups"] == "up":
                    self.reps["Sit-ups"] += 1
                    self.exercise_states["Sit-ups"] = "down"

            elif l_knee < 110 or r_knee < 110:
                # Squats vs Lunges check
                knee_diff = abs(landmarks[25].y - landmarks[26].y)
                if knee_diff < 0.1:
                    self.current_exercise = "Squats"
                    if min(l_knee, r_knee) < 90 and self.exercise_states["Squats"] == "up":
                        self.exercise_states["Squats"] = "down"
                    if min(l_knee, r_knee) > 160 and self.exercise_states["Squats"] == "down":
                        self.reps["Squats"] += 1
                        self.exercise_states["Squats"] = "up"
                else:
                    self.current_exercise = "Lunges"
                    if min(l_knee, r_knee) < 100 and self.exercise_states["Lunges"] == "up":
                        self.exercise_states["Lunges"] = "down"
                    if min(l_knee, r_knee) > 150 and self.exercise_states["Lunges"] == "down":
                        self.reps["Lunges"] += 1
                        self.exercise_states["Lunges"] = "up"

            elif l_elbow < 110 or r_elbow < 110:
                # Bicep Curls (ensure standing/not lying)
                if not is_lying and not hands_above_head:
                    self.current_exercise = "Bicep Curls"
                    if min(l_elbow, r_elbow) < 45 and self.exercise_states["Bicep Curls"] == "down":
                        self.exercise_states["Bicep Curls"] = "up"
                    if min(l_elbow, r_elbow) > 145 and self.exercise_states["Bicep Curls"] == "up":
                        self.reps["Bicep Curls"] += 1
                        self.exercise_states["Bicep Curls"] = "down"

            elif l_hip < 130 or r_hip < 130:
                self.current_exercise = "Deadlifts"
                if min(l_hip, r_hip) < 110 and self.exercise_states["Deadlifts"] == "up":
                    self.exercise_states["Deadlifts"] = "down"
                if min(l_hip, r_hip) > 165 and self.exercise_states["Deadlifts"] == "down":
                    self.reps["Deadlifts"] += 1
                    self.exercise_states["Deadlifts"] = "up"
            else:
                self.current_exercise = "Standing"

            # Visuals
            self.mp_draw.draw_landmarks(frame, results.pose_landmarks, self.mp_pose.POSE_CONNECTIONS)
            
            # Premium HUD Overlays
            overlay = frame.copy()
            cv2.rectangle(overlay, (0, 0), (w, 140), (0, 0, 0), -1)
            cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)
            
            cv2.putText(frame, f"SURVEILLANCE: {self.current_exercise.upper()}", (30, 45), cv2.FONT_HERSHEY_TRIPLEX, 0.8, (0, 255, 0), 2)
            cv2.putText(frame, f"REP COUNT: {self.reps.get(self.current_exercise, 0)}", (30, 85), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 255), 3)
            
            # Biometrics HUD
            cv2.putText(frame, f"HEART: {int(estimated_hr)} BPM", (w-250, 45), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 200, 255), 2)
            cv2.putText(frame, f"BM: {int(estimated_weight)}KG | BF: {int(estimated_body_fat)}%", (w-250, 85), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)

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
            return frame, {"exercise": "Error", "reps": 0, "height": 0, "body_fat": 0}

