from datetime import datetime
from typing import Any

from aiogram import Router, F, Bot
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    Message,
    CallbackQuery,
)

from config import Config
from database.db import Database
from keyboards.common import (
    main_menu_kb,
    subscription_kb,
    days_keyboard,
    time_slots_keyboard,
    time_slots_keyboard_with_taken,
    portfolio_kb,
)
from states.booking import BookingStates
from utils.scheduler import ReminderScheduler

user_router = Router()


async def _ensure_user_record(db: Database, message: Message) -> None:
    await db.get_or_create_user(
        user_id=message.from_user.id,
        username=message.from_user.username,
        full_name=message.from_user.full_name or "",
    )


async def _check_subscription(
    bot: Bot, config: Config, db: Database, user_id: int
) -> bool:
    """
    Проверяет подписку в Telegram и сохраняет флаг в БД.
    """
    try:
        member = await bot.get_chat_member(config.CHANNEL_ID, user_id)
        status = member.status
        is_subscribed = status in ("member", "administrator", "creator")
    except Exception:
        # Если канал приватный/ошибка — лучше перестраховаться и считать, что не подписан
        is_subscribed = False

    await db.set_user_subscription(user_id, is_subscribed)
    return is_subscribed


@user_router.message(CommandStart())
async def cmd_start(
    message: Message,
    state: FSMContext,
    db: Database,
    config: Config,
) -> None:
    await state.clear()
    await _ensure_user_record(db, message)

    is_admin = message.from_user.id == config.ADMIN_ID
    is_sub = await db.is_user_subscribed(message.from_user.id)

    text = (
        "👋 <b>Добро пожаловать!</b>\n\n"
        "✨ Это бот мастера по маникюру.\n\n"
        "📅 Записаться на приём\n"
        "📋 Посмотреть или отменить запись\n\n"
        "Выберите действие в меню ниже 👇"
    )
    if not is_sub:
        text += (
            "\n\n⚠️ <b>Важно:</b> для записи нужно подписаться на канал."
        )

    await message.answer(
        text=text,
        parse_mode="HTML",
        reply_markup=main_menu_kb(is_admin=is_admin),
    )


@user_router.callback_query(F.data == "menu_prices")
async def prices_callback(callback: CallbackQuery) -> None:
    """
    Прайсы — без FSM.
    """
    text = (
        "💰 <b>Прайс-лист</b>\n\n"
        "💅 Френч — <b>1000₽</b>\n"
        "💅 Квадрат — <b>500₽</b>\n"
    )
    await callback.message.edit_text(
        text=text,
        parse_mode="HTML",
        reply_markup=callback.message.reply_markup,
    )
    await callback.answer()


@user_router.callback_query(F.data == "menu_portfolio")
async def portfolio_callback(callback: CallbackQuery) -> None:
    """
    Портфолио — без FSM, просто ссылка.
    """
    text = "🖼 <b>Портфолио работ</b>\n\nНажмите кнопку ниже 👇"
    kb = portfolio_kb(
        "https://ru.pinterest.com/crystalwithluv/_created/"
    )
    await callback.message.answer(
        text=text,
        parse_mode="HTML",
        reply_markup=kb,
    )
    await callback.answer()


@user_router.callback_query(F.data == "menu_book")
async def menu_book_callback(
    callback: CallbackQuery,
    state: FSMContext,
    db: Database,
    config: Config,
    bot: Bot,
) -> None:
    """
    Начало процесса записи: сначала проверка подписки.
    """
    user_id = callback.from_user.id
    is_subscribed = await _check_subscription(bot, config, db, user_id)
    if not is_subscribed:
        text = (
            "⚠️ Для записи нужно подписаться на канал.\n\n"
            "После подписки нажмите <b>«Проверить подписку»</b> 👇"
        )
        await callback.message.answer(
            text=text,
            parse_mode="HTML",
            reply_markup=subscription_kb(config.CHANNEL_LINK),
        )
        await callback.answer()
        return

    # Проверка, нет ли уже активной записи
    if await db.has_active_booking(user_id):
        existing = await db.get_user_booking(user_id)
        if existing:
            _, date_str, time_str, _name = existing
            date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
            text = (
                "📌 <b>У вас уже есть активная запись</b>\n\n"
                f"📅 {date_obj.strftime('%d.%m.%Y')} в <b>{time_str}</b>\n\n"
                "Сначала отмените её в разделе «Моя запись»."
            )
            await callback.message.answer(
                text=text,
                parse_mode="HTML",
            )
            await callback.answer()
            return

    dates = await db.get_available_days_next_month()
    if not dates:
        await callback.message.answer(
            "😔 На ближайший месяц пока нет свободных слотов.",
        )
        await callback.answer()
        return

    booking_counts = await db.get_booking_counts_for_dates(dates)
    await state.set_state(BookingStates.CHOOSING_DATE)
    await callback.message.answer(
        "📅 Выберите дату (📌 — уже есть записи в этот день):",
        reply_markup=days_keyboard(dates, booking_counts),
    )
    await callback.answer()


@user_router.callback_query(F.data == "check_subscription")
async def check_subscription_callback(
    callback: CallbackQuery,
    db: Database,
    config: Config,
    bot: Bot,
) -> None:
    user_id = callback.from_user.id
    is_subscribed = await _check_subscription(bot, config, db, user_id)
    if is_subscribed:
        await callback.message.answer(
            "✅ Спасибо за подписку! Теперь можно записаться через меню 📅",
        )
    else:
        await callback.message.answer(
            "❌ Подписка не обнаружена. Подпишитесь на канал и нажмите «Проверить подписку» снова.",
        )
    await callback.answer()


@user_router.callback_query(
    BookingStates.CHOOSING_DATE, F.data.startswith("day_")
)
async def choose_date_callback(
    callback: CallbackQuery, state: FSMContext, db: Database
) -> None:
    date_str = callback.data.split("day_")[1]
    all_slots = await db.list_slots_for_date(date_str)
    free_slots = [(sid, t) for sid, t, booked in all_slots if not booked]
    if not free_slots:
        await callback.answer("На этот день нет свободных слотов.", show_alert=True)
        return

    await state.update_data(date=date_str)
    await state.set_state(BookingStates.CHOOSING_TIME)
    await callback.message.edit_text(
        text="🕐 Выберите время (🔒 — занято):",
        reply_markup=time_slots_keyboard_with_taken(all_slots),
    )
    await callback.answer()


@user_router.callback_query(
    BookingStates.CHOOSING_TIME, F.data == "slot_taken"
)
async def slot_taken_callback(callback: CallbackQuery) -> None:
    await callback.answer("Это время уже занято.", show_alert=True)


@user_router.callback_query(
    BookingStates.CHOOSING_TIME, F.data.startswith("slot_")
)
async def choose_time_callback(
    callback: CallbackQuery, state: FSMContext
) -> None:
    slot_id = int(callback.data.split("slot_")[1])
    await state.update_data(slot_id=slot_id)
    await state.set_state(BookingStates.ENTERING_NAME)
    await callback.message.edit_text(
        "✏️ Введите ваше <b>имя</b>:",
        parse_mode="HTML",
    )
    await callback.answer()


@user_router.message(BookingStates.ENTERING_NAME)
async def entering_name(
    message: Message, state: FSMContext
) -> None:
    name = message.text.strip()
    if len(name) < 2:
        await message.answer("Пожалуйста, введите корректное имя.")
        return

    await state.update_data(name=name)
    await state.set_state(BookingStates.ENTERING_PHONE)
    await message.answer(
        "📱 Введите ваш <b>номер телефона</b> (в любом формате):",
        parse_mode="HTML",
    )


@user_router.message(BookingStates.ENTERING_PHONE)
async def entering_phone(
    message: Message, state: FSMContext, db: Database
) -> None:
    phone = message.text.strip()
    if len(phone) < 5:
        await message.answer("❌ Введите корректный номер телефона.")
        return

    await state.update_data(phone=phone)
    data = await state.get_data()
    date_str = data["date"]
    slot_id = data["slot_id"]
    name = data["name"]

    date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
    slots = await db.get_free_slots_for_date(date_str)
    time_str = next((t for sid, t in slots if sid == slot_id), None) or f"{slot_id}"

    text = (
        "📋 <b>Проверьте данные:</b>\n\n"
        f"📅 Дата: <b>{date_obj.strftime('%d.%m.%Y')}</b>\n"
        f"🕐 Время: <b>{time_str}</b>\n"
        f"👤 Имя: <b>{name}</b>\n"
        f"📱 Телефон: <b>{phone}</b>\n\n"
        "Всё верно? Подтвердите запись 👇"
    )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Подтвердить", callback_data="confirm_booking"
                ),
                InlineKeyboardButton(
                    text="❌ Отмена", callback_data="cancel_booking_flow"
                ),
            ]
        ]
    )

    await state.set_state(BookingStates.CONFIRMING)
    await message.answer(text=text, parse_mode="HTML", reply_markup=kb)


from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton  # noqa: E402


@user_router.callback_query(F.data == "cancel_booking_flow")
async def cancel_booking_flow_callback(
    callback: CallbackQuery, state: FSMContext
) -> None:
    await state.clear()
    await callback.message.edit_text("❌ Запись отменена.")
    await callback.answer()


@user_router.callback_query(F.data == "back_to_dates")
async def back_to_dates_callback(
    callback: CallbackQuery, state: FSMContext, db: Database
) -> None:
    dates = await db.get_available_days_next_month()
    if not dates:
        await callback.message.edit_text(
            "На ближайший месяц пока нет доступных слотов."
        )
        await callback.answer()
        return

    booking_counts = await db.get_booking_counts_for_dates(dates)
    await state.set_state(BookingStates.CHOOSING_DATE)
    await callback.message.edit_text(
        "📅 Выберите дату (📌 — есть записи в этот день):",
        reply_markup=days_keyboard(dates, booking_counts),
    )
    await callback.answer()


@user_router.callback_query(F.data == "confirm_booking")
async def confirm_booking_callback(
    callback: CallbackQuery,
    state: FSMContext,
    db: Database,
    config: Config,
    bot: Bot,
    scheduler: ReminderScheduler,
) -> None:
    user_id = callback.from_user.id
    data = await state.get_data()
    date_str = data["date"]
    slot_id = data["slot_id"]
    name = data["name"]
    phone = data["phone"]

    # Получаем актуальное время слота
    slots = await db.get_free_slots_for_date(date_str)
    time_str = None
    for s_id, t_str in slots:
        if s_id == slot_id:
            time_str = t_str
            break

    if time_str is None:
        await callback.message.edit_text(
            "К сожалению, выбранный слот уже недоступен. Попробуйте выбрать другой."
        )
        await state.clear()
        await callback.answer()
        return

    # Создаём запись в БД
    booking_id = await db.create_booking(
        user_id=user_id,
        slot_id=slot_id,
        name=name,
        phone=phone,
    )
    if booking_id is None:
        await callback.message.edit_text(
            "Не удалось создать запись. Возможно, у вас уже есть активная запись "
            "или слот стал недоступен. Попробуйте ещё раз."
        )
        await state.clear()
        await callback.answer()
        return

    # Обновляем телефон пользователя в таблице users
    # (не критично, но полезно)
    async with aiosqlite.connect(db.path) as conn:
        await conn.execute(
            """
            UPDATE users
            SET phone = ?
            WHERE user_id = ?
            """,
            (phone, user_id),
        )
        await conn.commit()

    date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()

    # Сообщение пользователю
    text_user = (
        "✅ <b>Запись создана!</b>\n\n"
        f"📅 {date_obj.strftime('%d.%m.%Y')} в <b>{time_str}</b>\n"
        f"👤 {name} · 📱 {phone}\n\n"
        "Отменить запись можно в разделе «Моя запись» 📋"
    )
    await callback.message.edit_text(text_user, parse_mode="HTML")

    # Уведомление админу
    text_admin = (
        "📌 <b>Новая запись!</b>\n\n"
        f"👤 {name}\n"
        f"📱 {phone}\n"
        f"📅 {date_obj.strftime('%d.%m.%Y')} в {time_str}\n\n"
        f"ID: <code>{user_id}</code> · запись <code>{booking_id}</code>"
    )
    try:
        await bot.send_message(
            chat_id=config.ADMIN_ID,
            text=text_admin,
            parse_mode="HTML",
        )
    except Exception:
        pass

    # Сообщение в канал с расписанием
    channel_text = (
        "📅 <b>Новая запись</b>\n\n"
        f"🕐 {date_obj.strftime('%d.%m.%Y')} в {time_str}\n"
        f"👤 {name} · 📱 {phone}"
    )
    try:
        await bot.send_message(
            chat_id=config.CHANNEL_ID,
            text=channel_text,
            parse_mode="HTML",
        )
    except Exception:
        pass

    # Планируем напоминание
    await scheduler.schedule_reminder(
        booking_id=booking_id,
        user_id=user_id,
        date_str=date_str,
        time_str=time_str,
    )

    await state.clear()
    await callback.answer()


import aiosqlite  # noqa: E402


@user_router.callback_query(F.data == "menu_my_booking")
async def my_booking_callback(
    callback: CallbackQuery,
    db: Database,
    state: FSMContext,
) -> None:
    await state.clear()
    info = await db.get_user_booking(callback.from_user.id)
    if not info:
        await callback.message.answer(
            "📋 У вас пока нет активной записи."
        )
        await callback.answer()
        return

    booking_id, date_str, time_str, name = info
    date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()

    text = (
        "📌 <b>Ваша запись</b>\n\n"
        f"📅 {date_obj.strftime('%d.%m.%Y')} в <b>{time_str}</b>\n"
        f"👤 {name}\n\n"
        "Можно отменить 👇"
    )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="❌ Отменить запись",
                    callback_data="cancel_own_booking",
                )
            ]
        ]
    )
    await callback.message.answer(text=text, parse_mode="HTML", reply_markup=kb)
    await callback.answer()


@user_router.callback_query(F.data == "cancel_own_booking")
async def cancel_own_booking_callback(
    callback: CallbackQuery,
    db: Database,
    scheduler: ReminderScheduler,
) -> None:
    user_id = callback.from_user.id
    result = await db.cancel_booking(user_id)
    if not result:
        await callback.message.answer(
            "📋 У вас нет активной записи."
        )
        await callback.answer()
        return

    booking_id, date_str, time_str, reminder_job_id = result
    # Удаляем задачу напоминания
    await scheduler.cancel_reminder(booking_id)

    date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
    text = (
        "✅ <b>Запись отменена</b>\n\n"
        f"📅 {date_obj.strftime('%d.%m.%Y')} в {time_str}"
    )
    await callback.message.answer(text=text, parse_mode="HTML")
    await callback.answer()