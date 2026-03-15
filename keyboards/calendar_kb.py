# -*- coding: utf-8 -*-
"""
Интерактивный календарь для выбора даты (админ и запись).
Дни с записями помечаются значком 📌 и количеством.
"""
import calendar
from datetime import datetime
from typing import Dict

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

MONTH_NAMES = (
    "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
    "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"
)


def month_calendar_kb(
    year: int,
    month: int,
    booking_counts: Dict[str, int],
    callback_prefix: str,
    only_dates_with_bookings: bool = False,
) -> InlineKeyboardMarkup:
    """
    Клавиатура-календарь на один месяц.
    booking_counts: { "2025-03-15": 2 } — даты с записями и их количество.
    callback_prefix: префикс для callback_data (admin_schedule, admin_cancelb и т.д.).
    only_dates_with_bookings: если True, кликабельны только дни с записями (для отмены).
    """
    first_weekday = datetime(year, month, 1).weekday()
    last_day = calendar.monthrange(year, month)[1]

    # Навигация: предыдущий / следующий месяц
    prev_month = month - 1 if month > 1 else 12
    prev_year = year if month > 1 else year - 1
    next_month = month + 1 if month < 12 else 1
    next_year = year if month < 12 else year + 1

    month_title = f"{MONTH_NAMES[month - 1]} {year}"

    rows = [
        [
            InlineKeyboardButton(
                text="◀ Пред",
                callback_data=f"{callback_prefix}_cal_{prev_year}_{prev_month}",
            ),
            InlineKeyboardButton(text=month_title, callback_data=f"{callback_prefix}_noop"),
            InlineKeyboardButton(
                text="След ▶",
                callback_data=f"{callback_prefix}_cal_{next_year}_{next_month}",
            ),
        ]
    ]

    # Пустые ячейки до первого дня месяца (пн=0)
    cells = []
    for _ in range(first_weekday):
        cells.append((" ", f"{callback_prefix}_noop"))

    for day in range(1, last_day + 1):
        date_str = f"{year}-{month:02d}-{day:02d}"
        count = booking_counts.get(date_str, 0)
        if count > 0:
            label = f"{day} 📌{count}"
        else:
            label = str(day)
        if only_dates_with_bookings and count == 0:
            cells.append((label, f"{callback_prefix}_noop"))
        else:
            cells.append((label, f"{callback_prefix}_day_{date_str}"))

    # Добить до 35 ячеек (5 недель)
    while len(cells) < 35:
        cells.append((" ", f"{callback_prefix}_noop"))

    for i in range(0, 35, 7):
        row_buttons = []
        for j in range(7):
            text, cbd = cells[i + j]
            row_buttons.append(InlineKeyboardButton(text=text, callback_data=cbd))
        rows.append(row_buttons)

    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_calendar_back_kb(back_callback: str = "menu_admin") -> InlineKeyboardMarkup:
    """Кнопка «Назад» под календарём (по умолчанию — в админ-меню)."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="◀ Назад в админ-меню", callback_data=back_callback)]
        ]
    )


def confirm_close_day_kb(date_str: str) -> InlineKeyboardMarkup:
    """Подтверждение закрытия дня."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Закрыть день", callback_data=f"admin_closeday_confirm_{date_str}"),
                InlineKeyboardButton(text="❌ Отмена", callback_data="admin_close_day"),
            ]
        ]
    )


def time_presets_kb(date_str: str, callback_prefix: str = "admin_addslot") -> InlineKeyboardMarkup:
    """Кнопки выбора времени для добавления слота (типичные часы работы)."""
    times = ["09:00", "09:30", "10:00", "10:30", "11:00", "11:30", "12:00", "12:30", "13:00", "13:30", "14:00", "14:30", "15:00", "15:30", "16:00", "16:30", "17:00", "17:30", "18:00", "18:30", "19:00"]
    rows = []
    row = []
    for t in times:
        row.append(InlineKeyboardButton(text=t, callback_data=f"{callback_prefix}_time_{date_str}_{t}"))
        if len(row) == 4:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text="◀ Назад к календарю", callback_data="admin_add_slot")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
