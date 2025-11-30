# backend/config.py
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    """Configuration class for AVI Backend"""

    # Flask
    DEBUG = os.getenv("DEBUG", "True").lower() == "true"
    SECRET_KEY = os.getenv("SECRET_KEY", "avi-secret-key")

    # ----------------------------------------------------------------------
    # API KEYS (Loaded from .env)
    # ----------------------------------------------------------------------

    # RapidAPI (MAIN AI ENGINE NOW)
    RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")   # <- REQUIRED FOR FEEDBACK & NLP
    # Froq api key
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")   # <- REQUIRED
    # OpenAI / HuggingFace (Unused now, but kept optional)
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    HUGGINGFACE_API_KEY = os.getenv("HUGGINGFACE_API_KEY")
    GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
    # ----------------------------------------------------------------------
    # Database Settings
    # ----------------------------------------------------------------------
    MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    MONGO_DB = os.getenv("MONGO_DB", "avi_system")

    # ----------------------------------------------------------------------
    # Model & System Settings
    # ----------------------------------------------------------------------
    WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")
    SENTENCE_BERT_MODEL = os.getenv("SENTENCE_BERT_MODEL", "sentence-transformers/all-MiniLM-L6-v2")

    # ----------------------------------------------------------------------
    # File System Paths
    # ----------------------------------------------------------------------
    BASE_DIR = os.getcwd()
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "backend", "uploads")
    LOG_FOLDER = os.path.join(BASE_DIR, "backend", "logs")


# Ensure folders exist
os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
os.makedirs(Config.LOG_FOLDER, exist_ok=True)

class Config:
    DEBUG = True
    MONGO_URI = os.getenv("MONGO_URI", "")
    RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY", "")