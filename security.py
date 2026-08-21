import hashlib
import hmac
import logging
import re

from cryptography.fernet import Fernet, InvalidToken

from config import ADMIN_IDS, AUDIT_HMAC_KEY, DATA_ENCRYPTION_KEY, DEV_MODE

logger = logging.getLogger(__name__)

try:
    cipher = Fernet(DATA_ENCRYPTION_KEY.encode("utf-8"))
except Exception as exc:
    raise RuntimeError("DATA_ENCRYPTION_KEY must be a valid Fernet key") from exc


def encrypt(value: str | None) -> str | None:
    if value is None:
        return None
    return cipher.encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt(value: str | None) -> str | None:
    if value is None:
        return None
    try:
        return cipher.decrypt(value.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        logger.error("Encrypted value could not be decrypted")
        raise ValueError("Encrypted value cannot be decrypted") from exc


def is_encrypted(value: str | None) -> bool:
    if not value:
        return False
    try:
        cipher.decrypt(value.encode("utf-8"))
        return True
    except Exception:
        return False


def audit_actor_ref(telegram_id: int) -> str:
    return hmac.new(
        AUDIT_HMAC_KEY.encode("utf-8"),
        str(telegram_id).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def normalize_phone(value: str) -> str | None:
    raw = value.strip()
    digits = re.sub(r"\D", "", raw)
    if digits.startswith("8") and len(digits) == 11:
        digits = "7" + digits[1:]
    if digits.startswith("7") and len(digits) == 11:
        return "+" + digits
    if digits.startswith("9") and len(digits) == 10:
        return "+7" + digits
    return None


def clean_name(value: str) -> str | None:
    value = " ".join(value.strip().split())
    if not value or len(value) > 100:
        return None
    if any(ord(ch) < 32 for ch in value):
        return None
    if not re.fullmatch(r"[A-Za-zА-Яа-яЁё0-9 .\-']+", value):
        return None
    return value


def role_for(telegram_id: int, tester_ids: set[int] | None = None) -> str | None:
    if telegram_id in ADMIN_IDS:
        return "admin"
    if DEV_MODE:
        return "tester" if tester_ids and telegram_id in tester_ids else None
    return "user"
