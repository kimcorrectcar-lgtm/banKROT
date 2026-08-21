import asyncio
import logging

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from admin import router as admin_router
from config import BOT_TOKEN, PORT
from database import acquire_polling_lock, close_db, init_db, release_polling_lock
from handlers import router as user_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger(__name__)


async def health(request: web.Request) -> web.Response:
    return web.Response(text="OK")


async def start_server() -> web.AppRunner:
    app = web.Application()
    app.router.add_get("/", health)
    app.router.add_get("/health", health)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", PORT).start()
    return runner


async def main() -> None:
    await init_db()
    runner = await start_server()
    bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(admin_router)
    dp.include_router(user_router)

    polling_lock = None
    try:
        logger.info("banKROT started on port %s", PORT)
        logger.info("Waiting for the PostgreSQL polling lock...")
        polling_lock = await acquire_polling_lock()
        logger.info("Telegram polling lock acquired")
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await release_polling_lock(polling_lock)
        await runner.cleanup()
        await bot.session.close()
        await close_db()


if __name__ == "__main__":
    asyncio.run(main())
