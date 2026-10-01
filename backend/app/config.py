import os
from pathlib import Path
from dotenv import load_dotenv

# Base directory is BharatAgentic2026/
BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / ".env")

class Settings:
    APP_NAME: str = os.getenv("APP_NAME", "VyaparMitra")
    APP_ENV: str = os.getenv("APP_ENV", "development")
    DATABASE_PATH: str = os.getenv("DATABASE_PATH", str(BASE_DIR / "data" / "vyaparmitra.db"))
    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

settings = Settings()
