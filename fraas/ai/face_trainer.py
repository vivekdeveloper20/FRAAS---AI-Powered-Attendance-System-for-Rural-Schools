import os
from typing import List, Tuple

import cv2
import numpy as np
from flask import current_app


def _load_training_data() -> Tuple[List[np.ndarray], List[int]]:
    cfg = current_app.config
    base_dir = cfg["FACE_DATA_DIR"]
    images: List[np.ndarray] = []
    labels: List[int] = []

    if not os.path.isdir(base_dir):
        return images, labels

    for student_id_str in os.listdir(base_dir):
        student_dir = os.path.join(base_dir, student_id_str)
        if not os.path.isdir(student_dir):
            continue
        try:
            student_id = int(student_id_str)
        except ValueError:
            continue
        for file in os.listdir(student_dir):
            if not file.lower().endswith((".png", ".jpg", ".jpeg")):
                continue
            path = os.path.join(student_dir, file)
            img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
            if img is None:
                continue
            images.append(img)
            labels.append(student_id)
    return images, labels


def train_model() -> bool:
    """
    Train an LBPH face recognizer from stored face images.
    Saves trained model to disk.
    """
    images, labels = _load_training_data()
    cfg = current_app.config
    model_path = os.path.join(cfg["TRAINED_MODEL_DIR"], "lbph_model.yml")
    
    if not images:
        if os.path.exists(model_path):
            os.remove(model_path)
            # Create a dummy file or adjust time so recognizer detects modification
            with open(model_path + '.deleted', 'w') as f:
                f.write('deleted')
        return False
    recognizer = cv2.face.LBPHFaceRecognizer_create(
        radius=cfg["LBPH_RADIUS"],
        neighbors=cfg["LBPH_NEIGHBORS"],
        grid_x=cfg["LBPH_GRID_X"],
        grid_y=cfg["LBPH_GRID_Y"],
    )
    recognizer.train(images, np.array(labels))

    model_path = os.path.join(cfg["TRAINED_MODEL_DIR"], "lbph_model.yml")
    recognizer.write(model_path)
    return True


