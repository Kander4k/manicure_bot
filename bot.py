from aiogram.client.default import DefaultBotProperties
import asyncio

from aiogram import Bot, Dispatcher, BaseMiddleware
from aiogram.fsm.storage.memory import MemoryStorage

from config import load_config, Config
from database.db import Database
from handlers.user import user_router
from handlers.admin import admin_router
from utils.scheduler import ReminderScheduler


class InjectMiddleware(BaseMiddleware):
    """Передаёт config, db, scheduler и bot в каждый хендлер (иначе бот не отвечает)."""

    def __init__(self, config: Config, db: Database, scheduler: ReminderScheduler, bot: Bot):
        self.config = config
        self.db = db
        self.scheduler = scheduler
        self.bot = bot

    async def __call__(self, handler, event, data):
        data["config"] = self.config
        data["db"] = self.db
        data["scheduler"] = self.scheduler
        data["bot"] = self.bot
        return await handler(event, data)


async def main():
    config: Config = load_config()
    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode="HTML"),
    )
    # Инициализация БД
    db = Database(config.DATABASE_PATH)
    await db.init()

    # Хранилище состояний (FSM)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    # Планировщик напоминаний
    scheduler = ReminderScheduler(bot=bot, db=db)
    await scheduler.start()

    # Middleware: без него хендлеры не получают db/config/scheduler/bot и не срабатывают
    dp.update.middleware(InjectMiddleware(config, db, scheduler, bot))

    dp.include_router(user_router)
    dp.include_router(admin_router)

    print(
        f"Бот запущен для клиента: {config.CLIENT_NAME} "
        f"(admin_id={config.ADMIN_ID}, db={config.DATABASE_PATH})"
    )

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())