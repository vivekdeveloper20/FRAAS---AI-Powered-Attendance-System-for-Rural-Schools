import os
import time
from typing import Optional

import cv2
from flask import current_app

from ..models.recognition_result import RecognitionResult


class FaceRecognizer:
    def __init__(self):
        self.recognizer = None
        self.last_recognized_at = {}
        self.cached_name = "Unknown"
        self.cached_label = -1
        self.marked_success_until = 0.0
        self.model_last_modified = 0.0
        
        # Initialize Cascade Classifier once
        cascade_path = os.path.join(cv2.data.haarcascades, "haarcascade_frontalface_default.xml")
        self.face_cascade = cv2.CascadeClassifier(cascade_path)

    def show_marked_success(self):
        self.marked_success_until = time.time() + 2.0

    def _load_model(self) -> bool:
        cfg = current_app.config
        model_path = os.path.join(cfg["TRAINED_MODEL_DIR"], "lbph_model.yml")
        if not os.path.exists(model_path):
            self.recognizer = None
            self.cached_label = -1
            self.cached_name = "Unknown"
            self.model_last_modified = 0.0
            return False
            
        mtime = os.path.getmtime(model_path)
        if self.recognizer is not None and self.model_last_modified == mtime:
            return True
        
        # Clear out cached label so if a student is deleted/retrained, we fetch from DB again
        self.cached_label = -1
        self.cached_name = "Unknown"
        
        try:
            self.recognizer = cv2.face.LBPHFaceRecognizer_create(
                radius=cfg["LBPH_RADIUS"],
                neighbors=cfg["LBPH_NEIGHBORS"],
                grid_x=cfg["LBPH_GRID_X"],
                grid_y=cfg["LBPH_GRID_Y"],
            )
            self.recognizer.read(model_path)
            self.model_last_modified = mtime
            return True
        except Exception as e:
            print(f"Error loading model: {e}")
            return False

    def recognize_from_frame(self, frame) -> Optional[RecognitionResult]:
        """
        Detect and recognize a face from a BGR frame.
        """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Use more standard scaleFactor and minNeighbors for better detection
        faces = self.face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
        
        # Draw ephemeral floating success text if newly marked
        if time.time() < self.marked_success_until:
            cv2.putText(frame, "Attendance Marked", (30, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 3)

        if len(faces) == 0:
            return None
            
        x, y, w, h = faces[0]
        now = time.time()
        min_interval = current_app.config.get("MIN_RECOGNITION_INTERVAL_SECONDS", 5)

        if not self._load_model():
            # If Model fails to load (no trained data), ALWAYS draw red box
            cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 0, 255), 2)
            cv2.putText(frame, "Untrained System", (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
            last_untrained = self.last_recognized_at.get('untrained', 0.0)
            if now - last_untrained >= min_interval:
                self.last_recognized_at['untrained'] = now
                return RecognitionResult(student_id=-1, confidence=0.0)
            return None

        # Model loaded, proceed with recognition

        roi = gray[y : y + h, x : x + w]
        cfg = current_app.config
        roi_resized = cv2.resize(roi, (cfg["FACE_IMAGE_WIDTH"], cfg["FACE_IMAGE_HEIGHT"]))

        try:
            label, confidence = self.recognizer.predict(roi_resized)
        except Exception as e:
            print(f"Prediction error: {e}")
            return None

        from ..models import Student

        if confidence > current_app.config["RECOGNITION_CONFIDENCE_THRESHOLD"]:
            # Unknown Face Bounding Box
            cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 0, 255), 2)
            cv2.putText(frame, "Unknown", (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
            
            last_unk = self.last_recognized_at.get(-1, 0.0)
            if now - last_unk >= min_interval:
                self.last_recognized_at[-1] = now
                try:
                    import uuid
                    import datetime
                    unknown_dir = os.path.join(current_app.config["INSTANCE_DIR"], "unknown_faces")
                    os.makedirs(unknown_dir, exist_ok=True)
                    fmt = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"unknown_{fmt}_{uuid.uuid4().hex[:4]}.jpg"
                    
                    hf, wf = frame.shape[:2]
                    crop_y1 = max(0, y-20)
                    crop_y2 = min(hf, y+h+20)
                    crop_x1 = max(0, x-20)
                    crop_x2 = min(wf, x+w+20)
                    
                    face_crop = frame[crop_y1:crop_y2, crop_x1:crop_x2]
                    cv2.imwrite(os.path.join(unknown_dir, filename), face_crop)
                except Exception as e:
                    print(f"Failed to save unknown face: {e}")
                    
                return RecognitionResult(student_id=-1, confidence=float(confidence))
            return None

        # Known Face Bounding Box
        if int(label) != self.cached_label:
            student = Student.query.get(int(label))
            if student is None:
                self.cached_name = "Unknown"
                self.cached_label = -1
            else:
                self.cached_name = f"{student.name} (ID: {student.roll_number})"
                self.cached_label = int(label)
        
        # If student fetched was valid
        if self.cached_label != -1:
            cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
            cv2.putText(frame, self.cached_name, (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

            # Gate the backend DB attendance trigger behind interval
            last_known = self.last_recognized_at.get(self.cached_label, 0.0)
            if now - last_known >= min_interval:
                self.last_recognized_at[self.cached_label] = now
                return RecognitionResult(student_id=self.cached_label, confidence=float(confidence))
            
            return None
        else:
            # Fallback to unknown face response
            cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 0, 255), 2)
            cv2.putText(frame, "Unknown", (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
            
            last_unk = self.last_recognized_at.get(-1, 0.0)
            if now - last_unk >= min_interval:
                self.last_recognized_at[-1] = now
                try:
                    import uuid
                    import datetime
                    unknown_dir = os.path.join(current_app.config["INSTANCE_DIR"], "unknown_faces")
                    os.makedirs(unknown_dir, exist_ok=True)
                    fmt = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"unknown_{fmt}_{uuid.uuid4().hex[:4]}.jpg"
                    
                    hf, wf = frame.shape[:2]
                    crop_y1 = max(0, y-20)
                    crop_y2 = min(hf, y+h+20)
                    crop_x1 = max(0, x-20)
                    crop_x2 = min(wf, x+w+20)
                    
                    face_crop = frame[crop_y1:crop_y2, crop_x1:crop_x2]
                    cv2.imwrite(os.path.join(unknown_dir, filename), face_crop)
                except Exception as e:
                    print(f"Failed to save fallback unknown face: {e}")
                return RecognitionResult(student_id=-1, confidence=float(confidence))
            return None


