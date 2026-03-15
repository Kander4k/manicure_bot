import aiosqlite
from datetime import datetime, timedelta
from typing import List, Optional, Tuple, Any


class Database:
    """
    Обёртка над SQLite для работы с пользователями, днями, слотами и записями.
    """

    def __init__(self, path: str):
        self.path = path

    async def init(self) -> None:
        """
        Создаёт таблицы при первом запуске.
        """
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    full_name TEXT,
                    phone TEXT,
                    is_subscribed INTEGER DEFAULT 0
                )
                """
            )

            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS days (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT UNIQUE NOT NULL,
                    is_closed INTEGER DEFAULT 0
                )
                """
            )

            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS slots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    day_id INTEGER NOT NULL,
                    time TEXT NOT NULL,
                    is_booked INTEGER DEFAULT 0,
                    FOREIGN KEY(day_id) REFERENCES days(id)
                )
                """
            )

            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS bookings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    slot_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    phone TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    reminder_job_id TEXT,
                    FOREIGN KEY(user_id) REFERENCES users(user_id),
                    FOREIGN KEY(slot_id) REFERENCES slots(id)
                )
                """
            )

            # Один активный booking на пользователя
            await db.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_bookings_user_id
                ON bookings(user_id)
                """
            )

            await db.commit()

    async def get_or_create_user(
        self, user_id: int, username: Optional[str], full_name: str
    ) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                """
                INSERT OR IGNORE INTO users (user_id, username, full_name)
                VALUES (?, ?, ?)
                """,
                (user_id, username, full_name),
            )
            await db.commit()

    async def set_user_subscription(self, user_id: int, is_subscribed: bool) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                """
                UPDATE users SET is_subscribed = ?
                WHERE user_id = ?
                """,
                (1 if is_subscribed else 0, user_id),
            )
            await db.commit()

    async def is_user_subscribed(self, user_id: int) -> bool:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                "SELECT is_subscribed FROM users WHERE user_id = ?",
                (user_id,),
            )
            row = await cur.fetchone()
            if row:
                return bool(row[0])
            return False

    async def has_active_booking(self, user_id: int) -> bool:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                "SELECT id FROM bookings WHERE user_id = ?",
                (user_id,),
            )
            row = await cur.fetchone()
            return row is not None

    async def add_work_day(self, date_str: str) -> None:
        """
        Добавляет рабочий день (если еще нет).
        date_str в формате YYYY-MM-DD.
        """
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                """
                INSERT OR IGNORE INTO days (date, is_closed)
                VALUES (?, 0)
                """,
                (date_str,),
            )
            await db.commit()

    async def close_day(self, date_str: str) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                "UPDATE days SET is_closed = 1 WHERE date = ?",
                (date_str,),
            )
            # Отменяем все записи этого дня и освобождаем слоты
            await db.execute(
                """
                UPDATE slots
                SET is_booked = 0
                WHERE day_id IN (
                    SELECT id FROM days WHERE date = ?
                )
                """,
                (date_str,),
            )
            await db.execute(
                """
                DELETE FROM bookings
                WHERE slot_id IN (
                    SELECT id FROM slots
                    WHERE day_id IN (SELECT id FROM days WHERE date = ?)
                )
                """,
                (date_str,),
            )
            await db.commit()

    async def add_slot(self, date_str: str, time_str: str) -> None:
        """
        Добавляет новый временной слот к указанному дню.
        """
        async with aiosqlite.connect(self.path) as db:
            # Убедиться, что день есть
            await db.execute(
                """
                INSERT OR IGNORE INTO days (date, is_closed)
                VALUES (?, 0)
                """,
                (date_str,),
            )

            cur = await db.execute(
                "SELECT id FROM days WHERE date = ?",
                (date_str,),
            )
            day_row = await cur.fetchone()
            if not day_row:
                return
            day_id = day_row[0]

            await db.execute(
                """
                INSERT INTO slots (day_id, time, is_booked)
                VALUES (?, ?, 0)
                """,
                (day_id, time_str),
            )
            await db.commit()

    async def delete_slot(self, slot_id: int) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                "DELETE FROM slots WHERE id = ? AND is_booked = 0",
                (slot_id,),
            )
            await db.commit()

    async def get_available_days_next_month(self) -> List[str]:
        """
        Возвращает список дат (YYYY-MM-DD) на 30 дней вперёд,
        у которых есть хотя бы один свободный слот и день не закрыт.
        """
        now = datetime.now().date()
        limit = now + timedelta(days=30)

        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                """
                SELECT DISTINCT d.date
                FROM days d
                JOIN slots s ON s.day_id = d.id
                WHERE d.is_closed = 0
                  AND s.is_booked = 0
                  AND date(d.date) BETWEEN date(?) AND date(?)
                ORDER BY d.date
                """,
                (now.isoformat(), limit.isoformat()),
            )
            rows = await cur.fetchall()
            return [r[0] for r in rows]

    async def get_free_slots_for_date(self, date_str: str) -> List[Tuple[int, str]]:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                """
                SELECT s.id, s.time
                FROM slots s
                JOIN days d ON d.id = s.day_id
                WHERE d.date = ?
                  AND d.is_closed = 0
                  AND s.is_booked = 0
                ORDER BY time
                """,
                (date_str,),
            )
            rows = await cur.fetchall()
            return [(r[0], r[1]) for r in rows]

    async def create_booking(
        self,
        user_id: int,
        slot_id: int,
        name: str,
        phone: str,
    ) -> Optional[int]:
        """
        Создаёт запись, помечает слот как занятый.
        Возвращает id новой записи или None при конфликте.
        """
        async with aiosqlite.connect(self.path) as db:
            try:
                await db.execute("BEGIN")
                # Проверка, не занят ли слот
                cur = await db.execute(
                    "SELECT is_booked FROM slots WHERE id = ?",
                    (slot_id,),
                )
                row = await cur.fetchone()
                if not row or row[0] == 1:
                    await db.execute("ROLLBACK")
                    return None

                # Проверка, нет ли уже записи у пользователя
                cur = await db.execute(
                    "SELECT id FROM bookings WHERE user_id = ?",
                    (user_id,),
                )
                row = await cur.fetchone()
                if row:
                    await db.execute("ROLLBACK")
                    return None

                await db.execute(
                    "UPDATE slots SET is_booked = 1 WHERE id = ?",
                    (slot_id,),
                )
                created_at = datetime.utcnow().isoformat()
                cur = await db.execute(
                    """
                    INSERT INTO bookings (user_id, slot_id, name, phone, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (user_id, slot_id, name, phone, created_at),
                )
                booking_id = cur.lastrowid
                await db.commit()
                return booking_id
            except Exception:
                await db.execute("ROLLBACK")
                raise

    async def set_booking_reminder_job(
        self, booking_id: int, job_id: Optional[str]
    ) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                "UPDATE bookings SET reminder_job_id = ? WHERE id = ?",
                (job_id, booking_id),
            )
            await db.commit()

    async def cancel_booking(self, user_id: int) -> Optional[Tuple[int, str, str, str]]:
        """
        Отменяет запись пользователя, возвращает кортеж:
        (booking_id, date_str, time_str, reminder_job_id)
        или None, если записи нет.
        """
        async with aiosqlite.connect(self.path) as db:
            await db.execute("BEGIN")
            cur = await db.execute(
                """
                SELECT b.id,
                       d.date,
                       s.time,
                       b.reminder_job_id,
                       s.id
                FROM bookings b
                JOIN slots s ON s.id = b.slot_id
                JOIN days d ON d.id = s.day_id
                WHERE b.user_id = ?
                """,
                (user_id,),
            )
            row = await cur.fetchone()
            if not row:
                await db.execute("ROLLBACK")
                return None

            booking_id, date_str, time_str, reminder_job_id, slot_id = row

            await db.execute(
                "DELETE FROM bookings WHERE id = ?",
                (booking_id,),
            )
            await db.execute(
                "UPDATE slots SET is_booked = 0 WHERE id = ?",
                (slot_id,),
            )
            await db.commit()
            return booking_id, date_str, time_str, reminder_job_id

    async def get_user_booking(
        self, user_id: int
    ) -> Optional[Tuple[int, str, str, str]]:
        """
        Возвращает (booking_id, date_str, time_str, name) или None.
        """
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                """
                SELECT b.id, d.date, s.time, b.name
                FROM bookings b
                JOIN slots s ON s.id = b.slot_id
                JOIN days d ON d.id = s.day_id
                WHERE b.user_id = ?
                """,
                (user_id,),
            )
            row = await cur.fetchone()
            if not row:
                return None
            return row[0], row[1], row[2], row[3]

    async def get_booking_by_id(
        self, booking_id: int
    ) -> Optional[Tuple[int, int, str, str, str]]:
        """
        Возвращает информацию по id записи:
        (booking_id, user_id, date_str, time_str, name)
        """
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                """
                SELECT b.id, b.user_id, d.date, s.time, b.name
                FROM bookings b
                JOIN slots s ON s.id = b.slot_id
                JOIN days d ON d.id = s.day_id
                WHERE b.id = ?
                """,
                (booking_id,),
            )
            row = await cur.fetchone()
            if not row:
                return None
            return row[0], row[1], row[2], row[3], row[4]

    async def list_bookings_for_date(
        self, date_str: str
    ) -> List[Tuple[int, str, str]]:
        """
        Для админа: список записей на дату.
        Возвращает (booking_id, time, name).
        """
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                """
                SELECT b.id, s.time, b.name
                FROM bookings b
                JOIN slots s ON s.id = b.slot_id
                JOIN days d ON d.id = s.day_id
                WHERE d.date = ?
                ORDER BY s.time
                """,
                (date_str,),
            )
            rows = await cur.fetchall()
            return [(r[0], r[1], r[2]) for r in rows]

    async def list_slots_for_date(
        self, date_str: str
    ) -> List[Tuple[int, str, bool]]:
        """
        Для админа: список всех слотов (id, time, is_booked) на дату.
        """
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                """
                SELECT s.id, s.time, s.is_booked
                FROM slots s
                JOIN days d ON d.id = s.day_id
                WHERE d.date = ?
                ORDER BY s.time
                """,
                (date_str,),
            )
            rows = await cur.fetchall()
            return [(r[0], r[1], bool(r[2])) for r in rows]

    async def get_booking_counts_for_dates(
        self, date_list: List[str]
    ) -> dict:
        """
        Возвращает {date_str: количество_записей} для переданного списка дат.
        Для клиента: пометки на кнопках дат.
        """
        if not date_list:
            return {}
        placeholders = ",".join("?" * len(date_list))
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                f"""
                SELECT d.date, COUNT(b.id) as cnt
                FROM bookings b
                JOIN slots s ON b.slot_id = s.id
                JOIN days d ON s.day_id = d.id
                WHERE d.date IN ({placeholders})
                GROUP BY d.date
                """,
                date_list,
            )
            rows = await cur.fetchall()
            return {row[0]: row[1] for row in rows}

    async def get_all_bookings_next_days(
        self, days: int = 30
    ) -> List[Tuple[str, str, str, int]]:
        """
        Все записи на ближайшие days дней.
        Возвращает (date_str, time_str, name, booking_id), отсортировано по дате и времени.
        """
        now = datetime.now().date()
        limit = now + timedelta(days=days)
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                """
                SELECT d.date, s.time, b.name, b.id
                FROM bookings b
                JOIN slots s ON b.slot_id = s.id
                JOIN days d ON s.day_id = d.id
                WHERE date(d.date) BETWEEN date(?) AND date(?)
                ORDER BY d.date, s.time
                """,
                (now.isoformat(), limit.isoformat()),
            )
            rows = await cur.fetchall()
            return [(r[0], r[1], r[2], r[3]) for r in rows]

    async def get_month_dates_with_booking_count(
        self, year: int, month: int
    ) -> dict:
        """
        Возвращает словарь {date_str: количество_записей} для всех дат месяца,
        на которые есть хотя бы одна запись.
        """
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                """
                SELECT d.date, COUNT(b.id) as cnt
                FROM bookings b
                JOIN slots s ON b.slot_id = s.id
                JOIN days d ON s.day_id = d.id
                WHERE CAST(strftime('%Y', d.date) AS INT) = ?
                  AND CAST(strftime('%m', d.date) AS INT) = ?
                GROUP BY d.date
                """,
                (year, month),
            )
            rows = await cur.fetchall()
            return {row[0]: row[1] for row in rows}

    async def get_future_bookings_with_reminders(
        self,
    ) -> List[Tuple[int, int, str, str]]:
        """
        Для восстановления задач на старте.
        Возвращает (booking_id, user_id, date_str, time_str).
        """
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                """
                SELECT b.id, b.user_id, d.date, s.time
                FROM bookings b
                JOIN slots s ON s.id = b.slot_id
                JOIN days d ON d.id = s.day_id
                WHERE b.reminder_job_id IS NOT NULL
                """
            )
            rows = await cur.fetchall()
            return [(r[0], r[1], r[2], r[3]) for r in rows]