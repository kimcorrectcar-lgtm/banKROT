import asyncio
import logging

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from admin import router as admin_router
from config import BOT_TOKEN, PORT
from database import close_db, init_db
from handlers import router as user_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
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
    runner = None
    bot = None
    try:
        await init_db()

        bot = Bot(
            BOT_TOKEN,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )

        # The project uses long polling. Removing a webhook left by an older
        # deployment prevents webhook/polling mode from fighting each other.
        await bot.delete_webhook(drop_pending_updates=False)

        dp = Dispatcher(storage=MemoryStorage())
        # User router first, admin router second. FSM-specific user handlers
        # therefore get the first chance to process entered names/phones.
        dp.include_router(user_router)
        dp.include_router(admin_router)

        runner = await start_server()
        logger.info("banKROT started on port %s", PORT)
        logger.info("Telegram polling started")

        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
        )
    finally:
        if runner is not None:
            await runner.cleanup()
        await close_db()
        if bot is not None:
            await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
