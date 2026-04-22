from dotenv import load_dotenv
import os

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY", "fallback-insecure-key")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 480))

INTERVIEWER_USERNAME = os.getenv("INTERVIEWER_USERNAME", "admin")
INTERVIEWER_PASSWORD = os.getenv("INTERVIEWER_PASSWORD", "proctor123")

AGENT_API_KEY = os.getenv("AGENT_API_KEY", "agent-secret-key")