from datetime import datetime
from typing import List, Tuple, Dict, Optional

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def main_menu_kb(is_admin: bool = False) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(
                text="📅 Записаться", callback_data="menu_book"
            ),
        ],
        [
            InlineKeyboardButton(
                text="📋 Моя запись / Отменить", callback_data="menu_my_booking"
            ),
        ],
        [
            InlineKeyboardButton(
                text="💰 Прайсы", callback_data="menu_prices"
            ),
        ],
        [
            InlineKeyboardButton(
                text="🖼 Портфолио", callback_data="menu_portfolio"
            ),
        ],
    ]
    if is_admin:
        buttons.append(
            [
                InlineKeyboardButton(
                    text="⚙️ Админ-панель", callback_data="menu_admin"
                )
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def subscription_kb(channel_link: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📢 Подписаться на канал", url=channel_link
                )
            ],
            [
                InlineKeyboardButton(
                    text="✅ Проверить подписку",
                    callback_data="check_subscription",
                )
            ],
        ]
    )


def days_keyboard(
    dates: List[str],
    booking_counts: Optional[Dict[str, int]] = None,
) -> InlineKeyboardMarkup:
    """
    Клавиатура дат. Если передан booking_counts (дата -> кол-во записей),
    на кнопках отображается пометка 📌N для дней с записями.
    """
    booking_counts = booking_counts or {}
    buttons = []
    row = []
    for i, date_str in enumerate(dates, start=1):
        date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
        text = date_obj.strftime("%d.%m (%a)")
        cnt = booking_counts.get(date_str, 0)
        if cnt > 0:
            text += f" 📌{cnt}"
        row.append(
            InlineKeyboardButton(
                text=text, callback_data=f"day_{date_str}"
            )
        )
        if i % 5 == 0:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    buttons.append(
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_booking_flow")]
    )

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def time_slots_keyboard(slots: List[Tuple[int, str]]) -> InlineKeyboardMarkup:
    """
    Только свободные слоты: список (slot_id, time_str).
    """
    buttons = []
    row = []
    for i, (slot_id, time_str) in enumerate(slots, start=1):
        row.append(
            InlineKeyboardButton(
                text=time_str, callback_data=f"slot_{slot_id}"
            )
        )
        if i % 4 == 0:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    buttons.append(
        [InlineKeyboardButton(text="◀ Назад к датам", callback_data="back_to_dates")]
    )
    buttons.append(
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_booking_flow")]
    )

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def time_slots_keyboard_with_taken(
    slots: List[Tuple[int, str, bool]],
) -> InlineKeyboardMarkup:
    """
    Все слоты дня: (slot_id, time_str, is_booked).
    Свободные — кликабельны, занятые — подпись 🔒 занято, callback noop.
    """
    buttons = []
    row = []
    for i, (slot_id, time_str, is_booked) in enumerate(slots, start=1):
        if is_booked:
            text = f"{time_str} 🔒"
            callback_data = "slot_taken"
        else:
            text = time_str
            callback_data = f"slot_{slot_id}"
        row.append(
            InlineKeyboardButton(text=text, callback_data=callback_data)
        )
        if i % 4 == 0:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    buttons.append(
        [InlineKeyboardButton(text="◀ Назад к датам", callback_data="back_to_dates")]
    )
    buttons.append(
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_booking_flow")]
    )

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="➕ Добавить слот", callback_data="admin_add_slot"
                )
            ],
            [
                InlineKeyboardButton(
                    text="➖ Удалить слот", callback_data="admin_delete_slot"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🚫 Закрыть день", callback_data="admin_close_day"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📋 Просмотр расписания",
                    callback_data="admin_view_schedule",
                )
            ],
            [
                InlineKeyboardButton(
                    text="✏️ Отменить запись клиента",
                    callback_data="admin_cancel_booking",
                )
            ],
            [
                InlineKeyboardButton(
                    text="◀ Назад в меню", callback_data="admin_back_main"
                )
            ],
        ]
    )


def portfolio_kb(url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🖼 Смотреть портфолио",
                    url=url,
                )
            ]
        ]
    )