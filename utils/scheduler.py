from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram import Bot

from database.db import Database


class ReminderScheduler:
    """
    Обёртка вокруг APScheduler для планирования напоминаний.
    """

    def __init__(self, bot: Bot, db: Database):
        self.bot = bot
        self.db = db
        self.scheduler = AsyncIOScheduler(timezone="Europe/Moscow")

    async def start(self):
        self.scheduler.start()
        await self._restore_jobs()

    async def _restore_jobs(self):
        """
        На старте бота восстанавливает будущие задачи из БД.
        """
        rows = await self.db.get_future_bookings_with_reminders()
        now = datetime.now()
        for booking_id, user_id, date_str, time_str in rows:
            dt_visit = datetime.strptime(
                f"{date_str} {time_str}", "%Y-%m-%d %H:%M"
            )
            reminder_time = dt_visit - timedelta(hours=24)
            if reminder_time <= now:
                # нет смысла восстанавливать просроченное напоминание
                continue

            job_id = f"reminder_{booking_id}"
            # На всякий случай удалим, если вдруг уже есть
            try:
                self.scheduler.remove_job(job_id)
            except Exception:
                pass

            self.scheduler.add_job(
                self._send_reminder,
                "date",
                id=job_id,
                run_date=reminder_time,
                kwargs={
                    "user_id": user_id,
                    "date_str": date_str,
                    "time_str": time_str,
                    "booking_id": booking_id,
                },
            )

    async def schedule_reminder(
        self,
        booking_id: int,
        user_id: int,
        date_str: str,
        time_str: str,
    ):
        """
        Создаёт задачу напоминания за 24 часа до записи.
        Если до записи < 24 часов, напоминание не планируется.
        """
        dt_visit = datetime.strptime(
            f"{date_str} {time_str}", "%Y-%m-%d %H:%M"
        )
        reminder_time = dt_visit - timedelta(hours=24)
        now = datetime.now()
        if reminder_time <= now:
            # Не создаём напоминание
            await self.db.set_booking_reminder_job(booking_id, None)
            return

        job_id = f"reminder_{booking_id}"
        try:
            self.scheduler.remove_job(job_id)
        except Exception:
            pass

        self.scheduler.add_job(
            self._send_reminder,
            "date",
            id=job_id,
            run_date=reminder_time,
            kwargs={
                "user_id": user_id,
                "date_str": date_str,
                "time_str": time_str,
                "booking_id": booking_id,
            },
        )
        await self.db.set_booking_reminder_job(booking_id, job_id)

    async def cancel_reminder(self, booking_id: int):
        job_id = f"reminder_{booking_id}"
        try:
            self.scheduler.remove_job(job_id)
        except Exception:
            pass
        await self.db.set_booking_reminder_job(booking_id, None)

    async def _send_reminder(
        self, user_id: int, date_str: str, time_str: str, booking_id: int
    ):
        """
        Фактическая отправка напоминания в Telegram.
        """
        text = (
            "Напоминаем, что вы записаны на маникюр "
            f"завтра в <b>{time_str}</b>.\n"
            "Ждём вас ❤️"
        )
        try:
            await self.bot.send_message(
                chat_id=user_id,
                text=text,
                parse_mode="HTML",
            )
        finally:
            # После успешной (или неуспешной) попытки — удаляем id задачи в БД
            await self.db.set_booking_reminder_job(booking_id, None)