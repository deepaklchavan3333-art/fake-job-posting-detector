import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
MODEL_DIR = BASE_DIR / "models"
MODEL_PATH = MODEL_DIR / "fake_job_model.joblib"
METRICS_PATH = MODEL_DIR / "training_metrics.json"
DATABASE_PATH = Path(os.getenv("DATABASE_PATH", BASE_DIR / "database" / "clearhire.sqlite3"))
SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "dev-only-change-this-key")
FRONTEND_ORIGINS = [origin.strip() for origin in os.getenv("FRONTEND_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if origin.strip()]
SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true"
