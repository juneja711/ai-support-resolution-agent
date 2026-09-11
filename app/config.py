import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

# Base directory for the project
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env file if present
load_dotenv(BASE_DIR / ".env")

class Settings(BaseSettings):
    """Application configuration settings."""
    PROJECT_NAME: str = "AI Customer Support & Resolution Agent"
    VERSION: str = "1.0.0"
    
    # OpenAI Settings
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
    
    # Database Settings (SQLite)
    DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'data' / 'support.db'}")
    
    # Vector Database & Knowledge Base
    CHROMA_PERSIST_DIR: str = str(BASE_DIR / "data" / "chroma_db")
    KNOWLEDGE_BASE_DIR: str = str(BASE_DIR / "data" / "knowledge_base")

    model_config = SettingsConfigDict(env_file=".env", extra="allow")

settings = Settings()
