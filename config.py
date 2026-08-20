import os

from dotenv import load_dotenv


load_dotenv()


BOT_TOKEN = os.getenv(
    "BOT_TOKEN"
)

DATABASE_URL = os.getenv(
    "DATABASE_URL"
)

PORT = int(
    os.getenv(
        "PORT",
        "10000",
    )
)
