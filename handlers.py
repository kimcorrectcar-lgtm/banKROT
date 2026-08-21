import os
from dotenv import load_dotenv

load_dotenv()


def parse_ids(value: str) -> set[int]:
    result: set[int] = set()
    for item in value.split(","):
        item = item.strip()
        if item:
            try:
                result.add(int(item))
            except ValueError as exc:
                raise RuntimeError(f"Invalid Telegram ID: {item}") from exc
    return result


BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
PORT = int(os.getenv("PORT", "10000"))
DEV_MODE = os.getenv("DEV_MODE", "true").strip().lower() in {"1", "true", "yes", "on"}

ADMIN_IDS = parse_ids(os.getenv("ADMIN_IDS", ""))
ENV_TESTER_IDS = parse_ids(os.getenv("TESTER_IDS", ""))

DATA_ENCRYPTION_KEY = os.getenv("DATA_ENCRYPTION_KEY", "").strip()
AUDIT_HMAC_KEY = os.getenv("AUDIT_HMAC_KEY", "").strip()

MANAGER_PHONE = os.getenv("MANAGER_PHONE", "").strip()
MANAGER_TELEGRAM = os.getenv("MANAGER_TELEGRAM", "").strip()
MANAGER_WHATSAPP = os.getenv("MANAGER_WHATSAPP", "").strip()
MANAGER_LEADS_CHAT_ID = os.getenv("MANAGER_LEADS_CHAT_ID", "").strip()

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not configured")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not configured")
if not DATA_ENCRYPTION_KEY:
    raise RuntimeError("DATA_ENCRYPTION_KEY is not configured")
if not AUDIT_HMAC_KEY:
    raise RuntimeError("AUDIT_HMAC_KEY is not configured")
if not ADMIN_IDS:
    raise RuntimeError("ADMIN_IDS is not configured")
