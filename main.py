import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

import access
import admin
import config
import db
import user

logging.basicConfig(level=logging.INFO)


async def health(_request):
    return web.Response(text="ok")


async def main():
    if not config.ADMIN_IDS:
        logging.warning("ADMIN_IDS خالیه! هیچکس به پنل دسترسی نداره.")

    await db.init(config.DATABASE_URL)
    await access.reload()

    bot = Bot(config.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    dp.update.outer_middleware(access.BanMiddleware())  # کاربرای بن‌شده به هیچ هندلری نمیرسن
    dp.include_router(admin.router)  # اول ادمین، بعد کاربر
    dp.include_router(user.router)

    if not config.BASE_URL:
        # حالت تست لوکال
        await bot.delete_webhook()
        try:
            await dp.start_polling(bot)
        finally:
            await db.close()
        return

    app = web.Application()
    app.router.add_get("/", health)  # برای پینگ UptimeRobot
    SimpleRequestHandler(dp, bot, secret_token=config.WEBHOOK_SECRET).register(app, path="/webhook")
    setup_application(app, dp, bot=bot)

    await bot.set_webhook(
        f"{config.BASE_URL}/webhook",
        secret_token=config.WEBHOOK_SECRET,
        allowed_updates=dp.resolve_used_update_types(),
    )
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", config.PORT).start()
    logging.info("Bot is running on port %s", config.PORT)
    try:
        await asyncio.Event().wait()
    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())
