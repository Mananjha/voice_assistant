import os
from dotenv import load_dotenv

load_dotenv()

HF_TOKEN = os.getenv("HF_TOKEN")

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")


BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8000")

if not HF_TOKEN:
    raise ValueError(
        "HF_TOKEN is missing. Add HF_TOKEN to your .env file."
    )