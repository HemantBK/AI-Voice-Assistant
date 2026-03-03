import os
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "base")
WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "cpu")
KOKORO_VOICE = os.getenv("KOKORO_VOICE", "af_heart")
KOKORO_SPEED = float(os.getenv("KOKORO_SPEED", "1.0"))
LLM_MODEL = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")
SYSTEM_PROMPT = os.getenv("SYSTEM_PROMPT", (
    "You are a helpful voice assistant. Keep responses concise and conversational, "
    "ideally under 3 sentences. Be friendly and natural."
))
