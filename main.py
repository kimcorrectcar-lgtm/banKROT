import asyncio
import logging

from aiohttp import web
from aiogram import Bot, Dispatcher

from config import (
    BOT_TOKEN,
    WEB_HOST,
    WEB_PORT,
    validate_config,
)
from database import (
    close_database,
    init_database,
)
from handlers import router


logging.basicConfig(
    level=logging.INFO,
    format=(
        "%(asctime)s | "
        "%(levelname)s | "
        "%(name)s | "
        "%(message)s"
    ),
)

logger = logging.getLogger(__name__)


async def health_handler(
    request: web.Request,
) -> web.Response:
    return web.json_response(
        {
            "status": "ok",
            "service": "banKROT",
        }
    )


async def start_web_server() -> web.AppRunner:
    app = web.Application()

    app.router.add_get(
        "/",
        health_handler,
    )

    app.router.add_get(
        "/health",
        health_handler,
    )

    runner = web.AppRunner(app)

    await runner.setup()

    site = web.TCPSite(
        runner,
        WEB_HOST,
        WEB_PORT,
    )

    await site.start()

    logger.info(
        "Health server started on %s:%s",
        WEB_HOST,
        WEB_PORT,
    )

    return runner


async def main() -> None:
    validate_config()

    logger.info("Starting banKROT...")

    await init_database()

    bot = Bot(
        token=BOT_TOKEN,
    )

    dp = Dispatcher()

    dp.include_router(router)

    web_runner = await start_web_server()

    try:
        logger.info(
            "Telegram bot started",
        )

        await dp.start_polling(
            bot,
        )

    finally:
        logger.info(
            "Stopping banKROT...",
        )

        await bot.session.close()

        await web_runner.cleanup()

        await close_database()


if __name__ == "__main__":
    asyncio.run(main())
