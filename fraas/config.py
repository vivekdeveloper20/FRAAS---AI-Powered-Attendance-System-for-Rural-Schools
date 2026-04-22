import os


class Config:
    SECRET_KEY = os.environ.get("FRAAS_SECRET_KEY", "change-this-in-production")
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    INSTANCE_DIR = os.path.join(BASE_DIR, "..", "instance")
    os.makedirs(INSTANCE_DIR, exist_ok=True)

    SQLALCHEMY_DATABASE_URI = (
        os.environ.get("FRAAS_DATABASE_URI")
        or f"sqlite:///{os.path.join(INSTANCE_DIR, 'fraas.db')}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    LOG_FILE = os.path.join(INSTANCE_DIR, "fraas.log")

    FACE_DATA_DIR = os.path.join(INSTANCE_DIR, "face_data")
    TRAINED_MODEL_DIR = os.path.join(INSTANCE_DIR, "models")
    os.makedirs(FACE_DATA_DIR, exist_ok=True)
    os.makedirs(TRAINED_MODEL_DIR, exist_ok=True)

    FACE_IMAGE_WIDTH = 200
    FACE_IMAGE_HEIGHT = 200
    LBPH_RADIUS = 1
    LBPH_NEIGHBORS = 8
    LBPH_GRID_X = 8
    LBPH_GRID_Y = 8

    RECOGNITION_CONFIDENCE_THRESHOLD = 60
    MIN_RECOGNITION_INTERVAL_SECONDS = 10

    SYNC_ENDPOINT = os.environ.get("FRAAS_SYNC_ENDPOINT", "")


