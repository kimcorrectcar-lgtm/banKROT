import os

from dotenv import load_dotenv


load_dotenv()


BOT_TOKEN = os.getenv(
    "BOT_TOKEN",
    "",
).strip()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "",
).strip()

MANAGER_PHONE = os.getenv(
    "MANAGER_PHONE",
    "+70000000000",
).strip()

MANAGER_TELEGRAM = os.getenv(
    "MANAGER_TELEGRAM",
    "https://t.me/your_manager",
).strip()

MANAGER_WHATSAPP = os.getenv(
    "MANAGER_WHATSAPP",
    "https://wa.me/70000000000",
).strip()

COMPANY_NAME = os.getenv(
    "COMPANY_NAME",
    "banKROT",
).strip()

WEB_HOST = os.getenv(
    "WEB_HOST",
    "0.0.0.0",
).strip()

WEB_PORT = int(
    os.getenv(
        "WEB_PORT",
        "10000",
    )
)


def validate_config() -> None:
    errors = []

    if not BOT_TOKEN:
        errors.append(
            "Не задан BOT_TOKEN"
        )

    if not DATABASE_URL:
        errors.append(
            "Не задан DATABASE_URL"
        )

    if errors:
        raise RuntimeError(
            "Ошибки конфигурации:\n- "
            + "\n- ".join(errors)
        )
