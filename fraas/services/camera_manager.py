import threading
from typing import Optional, Tuple

import cv2

from ..ai.face_recognizer import FaceRecognizer
from ..models.recognition_result import RecognitionResult


class CameraManager:
    def __init__(self):
        self.lock = threading.Lock()
        self.cap = None
        self.is_active = False
        self.camera_index = 0
        self.recognizer = FaceRecognizer()

    def start(self, camera_index: int = 0):
        with self.lock:
            # If camera is active and index changed, release and reopen new source.
            if self.cap is not None and self.cap.isOpened() and self.camera_index != camera_index:
                self.cap.release()
                self.cap = None
                self.is_active = False

            if self.cap is None or not self.cap.isOpened():
                self.cap = cv2.VideoCapture(camera_index)
                self.is_active = self.cap.isOpened()

            if self.is_active:
                self.camera_index = camera_index
            return self.is_active

    def stop(self):
        with self.lock:
            if self.cap is not None:
                self.cap.release()
                self.cap = None
            self.is_active = False

    def get_frame_with_recognition(self) -> Tuple[Optional[bytes], Optional[RecognitionResult]]:
        with self.lock:
            if not self.is_active or self.cap is None:
                return None, None

            ret, frame = self.cap.read()
            if not ret:
                self.is_active = False
                return None, None

            recognized = self.recognizer.recognize_from_frame(frame)

            # Draw status overlay (simple text)
            status_text = "FRAAS Running"
            color = (0, 255, 0) if recognized else (0, 0, 255)
            cv2.putText(
                frame,
                status_text,
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                color,
                2,
                cv2.LINE_AA,
            )

            ret, buffer = cv2.imencode(".jpg", frame)
            if not ret:
                return None, recognized
            return buffer.tobytes(), recognized


_camera_singleton: Optional[CameraManager] = None


def get_camera() -> CameraManager:
    global _camera_singleton
    if _camera_singleton is None:
        _camera_singleton = CameraManager()
    return _camera_singleton


