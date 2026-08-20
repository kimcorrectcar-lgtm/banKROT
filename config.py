import os

from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
PORT = int(os.getenv("PORT", "10000"))

MANAGER_PHONE = os.getenv("MANAGER_PHONE", "+7XXXXXXXXXX")
MANAGER_TELEGRAM = os.getenv("MANAGER_TELEGRAM", "")
MANAGER_WHATSAPP = os.getenv("MANAGER_WHATSAPP", "")
MANAGER_MAX_LEADS_CHAT_ID = os.getenv("MANAGER_MAX_LEADS_CHAT_ID", "")
