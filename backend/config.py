import os
from dotenv import load_dotenv

load_dotenv()

# --- IBM Granite via local Ollama (approved substitution for watsonx.ai) ---
# granite3.3:2b is self-hosted via Ollama instead of watsonx cloud API.
# This avoids billing/API-key requirements while still running IBM Granite.
OLLAMA_URL: str = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "granite3.3:2b")

# --- Legacy watsonx vars kept for reference (not used in Sub-task 4) ---
WATSONX_API_KEY: str = os.getenv("WATSONX_API_KEY", "")
WATSONX_PROJECT_ID: str = os.getenv("WATSONX_PROJECT_ID", "")
WATSONX_URL: str = os.getenv("WATSONX_URL", "https://us-south.ml.cloud.ibm.com")
WATSONX_MODEL_ID: str = os.getenv("WATSONX_MODEL_ID", "ibm/granite-3-3-8b-instruct")

TMP_DIR: str = os.getenv("TMP_DIR", "/tmp/captainai")
MAX_FILE_SIZE_MB: int = int(os.getenv("MAX_FILE_SIZE_MB", "500"))
WHISPER_MODEL_SIZE: str = os.getenv("WHISPER_MODEL_SIZE", "small")
