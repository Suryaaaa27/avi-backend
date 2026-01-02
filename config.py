# config.py
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class Config:
    """Configuration class for AVI Backend"""

    # -------------------------------
    # Flask
    # -------------------------------
    DEBUG = os.getenv("DEBUG", "true").lower() == "true"
    SECRET_KEY = os.getenv("SECRET_KEY", "avi-secret-key")

    # -------------------------------
    # API Keys
    # -------------------------------
    RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY", "")
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    HUGGINGFACE_API_KEY = os.getenv("HUGGINGFACE_API_KEY", "")
    GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")

    # -------------------------------
    # Database
    # -------------------------------
    MONGO_URI = os.getenv("MONGO_URI", "")
    MONGO_DB = os.getenv("MONGO_DB", "avi_system")

    # -------------------------------
    # Models
    # -------------------------------
    WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")
    SENTENCE_BERT_MODEL = os.getenv(
        "SENTENCE_BERT_MODEL",
        "sentence-transformers/all-MiniLM-L6-v2"
    )

    # -------------------------------
    # Serverless-safe paths
    # (ONLY /tmp is writable on Vercel)
    # -------------------------------
    BASE_DIR = os.getcwd()
    UPLOAD_FOLDER = "/tmp/uploads"
    LOG_FOLDER = "/tmp/logs"


# Create folders ONLY in /tmp (safe on Vercel)
os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
os.makedirs(Config.LOG_FOLDER, exist_ok=True)
