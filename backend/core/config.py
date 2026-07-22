"""
AI Course Assistant Backend — Application Configuration.

Loads all settings from environment variables with sensible defaults.
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from .env file."""

    # --- Application ---
    APP_NAME: str = "AI Course Assistant"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    # --- Database ---
    DATABASE_URL: str = "postgresql+asyncpg://aca_user:aca_secret@localhost:5433/aca_db"
    DATABASE_URL_SYNC: str = "postgresql://aca_user:aca_secret@localhost:5433/aca_db"

    # --- Redis ---
    REDIS_URL: str = "redis://localhost:6380/0"

    # --- Qdrant ---
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333

    # --- JWT ---
    JWT_SECRET_KEY: str = "your-super-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_MINUTES: int = 1440  # 24 hours

    # --- AI / LLM ---
    GEMINI_API_KEY: str = ""
    LLM_MODEL: str = "gemini-2.0-flash"

    # --- Embeddings ---
    EMBEDDING_MODEL: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    EMBEDDING_DIMENSION: int = 384

    # --- Ingestion ---
    CHUNK_SIZE: int = 500
    CHUNK_OVERLAP: int = 100

    # --- Storage ---
    UPLOAD_DIR: str = "./uploads"
    MAX_FILE_SIZE_MB: int = 50
    MAX_PDFS_PER_COURSE: int = 20

    # --- CORS ---
    FRONTEND_URL: str = "http://localhost:3001"

    # --- OCR ---
    FORCE_OCR: bool = False
    OCR_LANGUAGES: str = "eng+mal"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


# Singleton settings instance
settings = Settings()
