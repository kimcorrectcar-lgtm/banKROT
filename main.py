import asyncio
import logging
import os

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv

from handlers import router

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.getenv("PORT", "10000"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger("bankrot")


async def health(request: web.Request) -> web.Response:
    return web.Response(text="OK")


async def start_health_server() -> web.AppRunner:
    app = web.Application()

    app.router.add_get("/", health)
    app.router.add_get("/health", health)

    runner = web.AppRunner(app)
    await runner.setup()

    site = web.TCPSite(
        runner,
        "0.0.0.0",
        PORT,
    )

    await site.start()

    logger.info(
        "Health server started on port %s",
        PORT,
    )

    return runner


async def main() -> None:
    if not BOT_TOKEN:
        raise RuntimeError(
            "BOT_TOKEN is not configured"
        )

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML
        ),
    )

    dp = Dispatcher(
        storage=MemoryStorage()
    )

    dp.include_router(router)

    health_runner = await start_health_server()

    try:
        logger.info(
            "banKROT bot started"
        )

        await dp.start_polling(bot)

    finally:
        await health_runner.cleanup()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
