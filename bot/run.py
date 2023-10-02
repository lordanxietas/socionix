from bot import dp, bot
import asyncio

from config import *

from aiohttp import web
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application


async def on_startup(bot):
    await bot.set_webhook(url=WEBHOOK_URL)



def main():
    dp.startup.register(on_startup)

    app = web.Application()

    webhook_request_handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
    )

    webhook_request_handler.register(app, path='/bot')

    setup_application(app, dp, bot=bot)

    web.run_app(app, host=WEBHOOK_LOCAL_HOST, port=WEBHOOK_LOCAL_PORT)

main()