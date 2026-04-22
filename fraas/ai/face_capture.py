import os
from typing import Optional

import cv2
from flask import current_app


def capture_faces_for_student(student_id: int, num_samples: int = 20) -> int:
    """
    Capture multiple face images for a student using the default camera.
    Returns number of samples successfully captured.
    """
    face_cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        return 0

    samples_collected = 0
    cfg = current_app.config
    student_dir = os.path.join(cfg["FACE_DATA_DIR"], str(student_id))
    os.makedirs(student_dir, exist_ok=True)

    while samples_collected < num_samples:
        ret, frame = cap.read()
        if not ret:
            break
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, scaleFactor=1.3, minNeighbors=5)
        for (x, y, w, h) in faces:
            roi = gray[y : y + h, x : x + w]
            roi_resized = cv2.resize(
                roi,
                (cfg["FACE_IMAGE_WIDTH"], cfg["FACE_IMAGE_HEIGHT"]),
            )
            img_path = os.path.join(student_dir, f"{samples_collected + 1}.png")
            cv2.imwrite(img_path, roi_resized)
            samples_collected += 1
            break

    cap.release()
    return samples_collected


