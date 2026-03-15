# -*- coding: utf-8 -*-
import aiosqlite
from datetime import datetime

from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from config import Config
from database.db import Database
from keyboards.common import admin_menu_kb
from keyboards.calendar_kb import (
    month_calendar_kb,
    admin_calendar_back_kb,
    confirm_close_day_kb,
    time_presets_kb,
)
from states.admin import AdminStates
from utils.scheduler import ReminderScheduler

admin_router = Router()


def _admin_only(callback: CallbackQuery, config: Config) -> bool:
    if callback.from_user.id != config.ADMIN_ID:
        callback.answer("Доступ запрещён.", show_alert=True)
        return False
    return True


# ---------- Админ-меню ----------


@admin_router.callback_query(F.data == "menu_admin")
async def open_admin_panel(
    callback: CallbackQuery,
    config: Config,
    state: FSMContext,
) -> None:
    if not _admin_only(callback, config):
        return
    await state.set_state(AdminStates.CHOOSING_ACTION)
    await callback.message.edit_text(
        "⚙️ <b>Админ-панель</b>\n\nВыберите действие:",
        parse_mode="HTML",
        reply_markup=admin_menu_kb(),
    )
    await callback.answer()


@admin_router.callback_query(F.data == "admin_back_main")
async def admin_back_main(
    callback: CallbackQuery, state: FSMContext
) -> None:
    await state.clear()
    await callback.message.edit_text(
        "◀ Возврат в главное меню.\nОтправьте /start для обновления.",
        parse_mode="HTML",
    )
    await callback.answer()


# ---------- Просмотр расписания: сначала все записи, потом календарь ----------


@admin_router.callback_query(F.data == "admin_view_schedule")
async def admin_view_schedule_start(
    callback: CallbackQuery,
    config: Config,
    state: FSMContext,
    db: Database,
) -> None:
    if not _admin_only(callback, config):
        return
    all_bookings = await db.get_all_bookings_next_days(30)
    if not all_bookings:
        text = "📋 <b>Просмотр расписания</b>\n\nНа ближайшие 30 дней записей нет."
    else:
        lines = ["📋 <b>Все записи на ближайшие 30 дней</b>\n"]
        prev_date = None
        for date_str, time_str, name, bid in all_bookings:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
            d_fmt = date_obj.strftime("%d.%m.%Y")
            if d_fmt != prev_date:
                lines.append(f"\n📅 <b>{d_fmt}</b>")
                prev_date = d_fmt
            lines.append(f"  🕐 {time_str} — {name} (id: <code>{bid}</code>)")
        text = "\n".join(lines).strip()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 Календарь по датам", callback_data="admin_view_schedule_cal")],
        [InlineKeyboardButton(text="◀ В админ-меню", callback_data="menu_admin")],
    ])
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=kb,
    )
    await callback.answer()


@admin_router.callback_query(F.data == "admin_view_schedule_cal")
async def admin_view_schedule_open_calendar(
    callback: CallbackQuery,
    config: Config,
    db: Database,
) -> None:
    if not _admin_only(callback, config):
        return
    now = datetime.now()
    counts = await db.get_month_dates_with_booking_count(now.year, now.month)
    kb = month_calendar_kb(now.year, now.month, counts, "admin_schedule")
    back = admin_calendar_back_kb()
    for row in back.inline_keyboard:
        kb.inline_keyboard.append(row)
    await callback.message.edit_text(
        "📋 <b>Просмотр расписания</b>\n\nВыберите дату (📌 — дни с записями):",
        parse_mode="HTML",
        reply_markup=kb,
    )
    await callback.answer()


@admin_router.callback_query(F.data.startswith("admin_schedule_cal_"))
async def admin_schedule_cal(
    callback: CallbackQuery,
    db: Database,
) -> None:
    parts = callback.data.split("_")
    if len(parts) < 5:
        await callback.answer()
        return
    year, month = int(parts[3]), int(parts[4])
    counts = await db.get_month_dates_with_booking_count(year, month)
    kb = month_calendar_kb(year, month, counts, "admin_schedule")
    back = admin_calendar_back_kb()
    for row in back.inline_keyboard:
        kb.inline_keyboard.append(row)
    await callback.message.edit_text(
        "📋 <b>Просмотр расписания</b>\n\nВыберите дату (📌 — дни с записями):",
        parse_mode="HTML",
        reply_markup=kb,
    )
    await callback.answer()


@admin_router.callback_query(F.data.startswith("admin_schedule_day_"))
async def admin_schedule_show_day(
    callback: CallbackQuery,
    db: Database,
) -> None:
    date_str = callback.data.replace("admin_schedule_day_", "")
    try:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        await callback.answer("Неверная дата.", show_alert=True)
        return
    bookings = await db.list_bookings_for_date(date_str)
    slots = await db.list_slots_for_date(date_str)
    if not slots:
        await callback.message.edit_text(
            f"📅 На <b>{date_obj.strftime('%d.%m.%Y')}</b> слотов нет.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀ К календарю", callback_data="admin_view_schedule")]
            ]),
        )
        await callback.answer()
        return
    lines = [f"📋 <b>Расписание на {date_obj.strftime('%d.%m.%Y')}</b>\n"]
    if bookings:
        lines.append("📌 <b>Записи:</b>")
        for bid, time_str, name in bookings:
            lines.append(f"  • {time_str} — {name} (id: <code>{bid}</code>)")
        lines.append("")
    lines.append("🕐 <b>Слоты:</b>")
    for slot_id, time_str, is_booked in slots:
        st = "🔴 занят" if is_booked else "🟢 свободен"
        lines.append(f"  • {time_str} — {st}")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀ К календарю", callback_data="admin_view_schedule")]
    ])
    await callback.message.edit_text(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=kb,
    )
    await callback.answer()


@admin_router.callback_query(F.data == "admin_schedule_noop")
async def admin_schedule_noop(callback: CallbackQuery) -> None:
    await callback.answer()


# ---------- Отмена записи клиента (календарь) ----------


@admin_router.callback_query(F.data == "admin_cancel_booking")
async def admin_cancel_booking_start(
    callback: CallbackQuery,
    config: Config,
    state: FSMContext,
    db: Database,
) -> None:
    if not _admin_only(callback, config):
        return
    now = datetime.now()
    counts = await db.get_month_dates_with_booking_count(now.year, now.month)
    kb = month_calendar_kb(
        now.year, now.month, counts, "admin_cancelb",
        only_dates_with_bookings=True,
    )
    back = admin_calendar_back_kb()
    for row in back.inline_keyboard:
        kb.inline_keyboard.append(row)
    await callback.message.edit_text(
        "✏️ <b>Отменить запись клиента</b>\n\nВыберите дату (📌 — есть записи):",
        parse_mode="HTML",
        reply_markup=kb,
    )
    await callback.answer()


@admin_router.callback_query(F.data.startswith("admin_cancelb_cal_"))
async def admin_cancelb_cal(
    callback: CallbackQuery,
    db: Database,
) -> None:
    parts = callback.data.split("_")
    if len(parts) < 5:
        await callback.answer()
        return
    year, month = int(parts[3]), int(parts[4])
    counts = await db.get_month_dates_with_booking_count(year, month)
    kb = month_calendar_kb(year, month, counts, "admin_cancelb", only_dates_with_bookings=True)
    back = admin_calendar_back_kb()
    for row in back.inline_keyboard:
        kb.inline_keyboard.append(row)
    await callback.message.edit_text(
        "✏️ <b>Отменить запись клиента</b>\n\nВыберите дату (📌 — есть записи):",
        parse_mode="HTML",
        reply_markup=kb,
    )
    await callback.answer()


@admin_router.callback_query(F.data.startswith("admin_cancelb_day_"))
async def admin_cancel_booking_choose_date(
    callback: CallbackQuery,
    db: Database,
    state: FSMContext,
) -> None:
    date_str = callback.data.replace("admin_cancelb_day_", "")
    date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
    bookings = await db.list_bookings_for_date(date_str)
    if not bookings:
        await callback.answer("На эту дату записей нет.", show_alert=True)
        return
    await state.update_data(cancel_date=date_str)
    await state.set_state(AdminStates.CANCEL_BOOKING_CHOOSE_BOOKING)
    rows = []
    for booking_id, time_str, name in bookings:
        rows.append([
            InlineKeyboardButton(
                text=f"🕐 {time_str} — {name}",
                callback_data=f"admin_cancel_booking_{booking_id}",
            )
        ])
    rows.append([InlineKeyboardButton(text="◀ К календарю", callback_data="admin_cancel_booking")])
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    await callback.message.edit_text(
        f"✏️ <b>Отмена записи</b>\n\nДата: <b>{date_obj.strftime('%d.%m.%Y')}</b>\nВыберите запись:",
        parse_mode="HTML",
        reply_markup=kb,
    )
    await callback.answer()


@admin_router.callback_query(F.data == "admin_cancelb_noop")
async def admin_cancelb_noop(callback: CallbackQuery) -> None:
    await callback.answer()


@admin_router.callback_query(
    AdminStates.CANCEL_BOOKING_CHOOSE_BOOKING,
    F.data.startswith("admin_cancel_booking_"),
)
async def admin_cancel_booking_process(
    callback: CallbackQuery,
    db: Database,
    scheduler: ReminderScheduler,
    state: FSMContext,
) -> None:
    if "_" not in callback.data or callback.data.count("_") < 3:
        await callback.answer()
        return
    booking_id = int(callback.data.split("_")[-1])
    booking = await db.get_booking_by_id(booking_id)
    if not booking:
        await callback.message.edit_text("Запись не найдена.")
        await state.clear()
        await callback.answer()
        return
    _, user_id, date_str, time_str, name = booking
    async with aiosqlite.connect(db.path) as conn:
        cur = await conn.execute(
            "SELECT slot_id FROM bookings WHERE id = ?",
            (booking_id,),
        )
        row = await cur.fetchone()
        if not row:
            await callback.message.edit_text("Ошибка: запись не найдена.")
            await state.clear()
            await callback.answer()
            return
        slot_id = row[0]
        await conn.execute("DELETE FROM bookings WHERE id = ?", (booking_id,))
        await conn.execute("UPDATE slots SET is_booked = 0 WHERE id = ?", (slot_id,))
        await conn.commit()
    await scheduler.cancel_reminder(booking_id)
    await state.clear()
    date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
    await callback.message.edit_text(
        f"✅ Запись отменена: <b>{name}</b>, {date_obj.strftime('%d.%m.%Y')} в {time_str}.",
        parse_mode="HTML",
    )
    await callback.answer()


# ---------- Добавить слот (календарь + время) ----------


@admin_router.callback_query(F.data == "admin_add_slot")
async def admin_add_slot_start(
    callback: CallbackQuery,
    config: Config,
    state: FSMContext,
    db: Database,
) -> None:
    if not _admin_only(callback, config):
        return
    now = datetime.now()
    counts = await db.get_month_dates_with_booking_count(now.year, now.month)
    kb = month_calendar_kb(now.year, now.month, counts, "admin_addslot")
    back = admin_calendar_back_kb()
    for row in back.inline_keyboard:
        kb.inline_keyboard.append(row)
    await callback.message.edit_text(
        "➕ <b>Добавить слот</b>\n\nВыберите дату:",
        parse_mode="HTML",
        reply_markup=kb,
    )
    await callback.answer()


@admin_router.callback_query(F.data.startswith("admin_addslot_cal_"))
async def admin_addslot_cal(
    callback: CallbackQuery,
    db: Database,
) -> None:
    parts = callback.data.split("_")
    if len(parts) < 5:
        await callback.answer()
        return
    year, month = int(parts[3]), int(parts[4])
    counts = await db.get_month_dates_with_booking_count(year, month)
    kb = month_calendar_kb(year, month, counts, "admin_addslot")
    back = admin_calendar_back_kb()
    for row in back.inline_keyboard:
        kb.inline_keyboard.append(row)
    await callback.message.edit_text(
        "➕ <b>Добавить слот</b>\n\nВыберите дату:",
        parse_mode="HTML",
        reply_markup=kb,
    )
    await callback.answer()


@admin_router.callback_query(F.data.startswith("admin_addslot_day_"))
async def admin_add_slot_choose_date(
    callback: CallbackQuery,
    db: Database,
) -> None:
    date_str = callback.data.replace("admin_addslot_day_", "")
    date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
    kb = time_presets_kb(date_str, "admin_addslot")
    await callback.message.edit_text(
        f"➕ <b>Добавить слот</b>\n\nДата: <b>{date_obj.strftime('%d.%m.%Y')}</b>\nВыберите время:",
        parse_mode="HTML",
        reply_markup=kb,
    )
    await callback.answer()


@admin_router.callback_query(F.data.startswith("admin_addslot_time_"))
async def admin_add_slot_process(
    callback: CallbackQuery,
    db: Database,
) -> None:
    # admin_addslot_time_2025-03-15_09:00
    rest = callback.data.replace("admin_addslot_time_", "")
    if "_" not in rest:
        await callback.answer()
        return
    date_str, time_str = rest.split("_", 1)
    await db.add_slot(date_str, time_str)
    date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
    await callback.message.edit_text(
        f"✅ Слот <b>{time_str}</b> на {date_obj.strftime('%d.%m.%Y')} добавлен.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀ В админ-меню", callback_data="menu_admin")]
        ]),
    )
    await callback.answer()


@admin_router.callback_query(F.data == "admin_addslot_noop")
async def admin_addslot_noop(callback: CallbackQuery) -> None:
    await callback.answer()


# ---------- Удалить слот (календарь) ----------


@admin_router.callback_query(F.data == "admin_delete_slot")
async def admin_delete_slot_start(
    callback: CallbackQuery,
    config: Config,
    state: FSMContext,
    db: Database,
) -> None:
    if not _admin_only(callback, config):
        return
    now = datetime.now()
    counts = await db.get_month_dates_with_booking_count(now.year, now.month)
    kb = month_calendar_kb(now.year, now.month, counts, "admin_delslot")
    back = admin_calendar_back_kb()
    for row in back.inline_keyboard:
        kb.inline_keyboard.append(row)
    await callback.message.edit_text(
        "➖ <b>Удалить слот</b>\n\nВыберите дату (удаляются только свободные слоты):",
        parse_mode="HTML",
        reply_markup=kb,
    )
    await callback.answer()


@admin_router.callback_query(F.data.startswith("admin_delslot_cal_"))
async def admin_delslot_cal(
    callback: CallbackQuery,
    db: Database,
) -> None:
    parts = callback.data.split("_")
    if len(parts) < 5:
        await callback.answer()
        return
    year, month = int(parts[3]), int(parts[4])
    counts = await db.get_month_dates_with_booking_count(year, month)
    kb = month_calendar_kb(year, month, counts, "admin_delslot")
    back = admin_calendar_back_kb()
    for row in back.inline_keyboard:
        kb.inline_keyboard.append(row)
    await callback.message.edit_text(
        "➖ <b>Удалить слот</b>\n\nВыберите дату:",
        parse_mode="HTML",
        reply_markup=kb,
    )
    await callback.answer()


@admin_router.callback_query(F.data.startswith("admin_delslot_day_"))
async def admin_delete_slot_choose_date(
    callback: CallbackQuery,
    db: Database,
    state: FSMContext,
) -> None:
    date_str = callback.data.replace("admin_delslot_day_", "")
    date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
    slots = await db.list_slots_for_date(date_str)
    free = [s for s in slots if not s[2]]
    if not free:
        await callback.message.edit_text(
            f"➖ На <b>{date_obj.strftime('%d.%m.%Y')}</b> нет свободных слотов для удаления.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀ К календарю", callback_data="admin_delete_slot")]
            ]),
        )
        await callback.answer()
        return
    await state.update_data(delslot_date=date_str)
    await state.set_state(AdminStates.DELETE_SLOT_CHOOSE_SLOT)
    rows = []
    for slot_id, time_str, is_booked in free:
        rows.append([
            InlineKeyboardButton(
                text=f"🕐 {time_str} (свободен)",
                callback_data=f"admin_del_slot_{slot_id}",
            )
        ])
    rows.append([InlineKeyboardButton(text="◀ К календарю", callback_data="admin_delete_slot")])
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    await callback.message.edit_text(
        f"➖ <b>Удалить слот</b>\n\nДата: <b>{date_obj.strftime('%d.%m.%Y')}</b>\nВыберите слот:",
        parse_mode="HTML",
        reply_markup=kb,
    )
    await callback.answer()


@admin_router.callback_query(
    AdminStates.DELETE_SLOT_CHOOSE_SLOT,
    F.data.startswith("admin_del_slot_"),
)
async def admin_delete_slot_process(
    callback: CallbackQuery,
    db: Database,
    state: FSMContext,
) -> None:
    slot_id = int(callback.data.split("admin_del_slot_")[1])
    await db.delete_slot(slot_id)
    await state.clear()
    await callback.message.edit_text(
        "✅ Слот удалён (если был свободен).",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀ В админ-меню", callback_data="menu_admin")]
        ]),
    )
    await callback.answer()


@admin_router.callback_query(F.data == "admin_delslot_noop")
async def admin_delslot_noop(callback: CallbackQuery) -> None:
    await callback.answer()


# ---------- Закрыть день (календарь + подтверждение) ----------


@admin_router.callback_query(F.data == "admin_close_day")
async def admin_close_day_start(
    callback: CallbackQuery,
    config: Config,
    state: FSMContext,
    db: Database,
) -> None:
    if not _admin_only(callback, config):
        return
    now = datetime.now()
    counts = await db.get_month_dates_with_booking_count(now.year, now.month)
    kb = month_calendar_kb(now.year, now.month, counts, "admin_closeday")
    back = admin_calendar_back_kb()
    for row in back.inline_keyboard:
        kb.inline_keyboard.append(row)
    await callback.message.edit_text(
        "🚫 <b>Закрыть день</b>\n\nВыберите дату (все записи будут отменены):",
        parse_mode="HTML",
        reply_markup=kb,
    )
    await callback.answer()


@admin_router.callback_query(F.data.startswith("admin_closeday_cal_"))
async def admin_closeday_cal(
    callback: CallbackQuery,
    db: Database,
) -> None:
    parts = callback.data.split("_")
    if len(parts) < 5:
        await callback.answer()
        return
    year, month = int(parts[3]), int(parts[4])
    counts = await db.get_month_dates_with_booking_count(year, month)
    kb = month_calendar_kb(year, month, counts, "admin_closeday")
    back = admin_calendar_back_kb()
    for row in back.inline_keyboard:
        kb.inline_keyboard.append(row)
    await callback.message.edit_text(
        "🚫 <b>Закрыть день</b>\n\nВыберите дату:",
        parse_mode="HTML",
        reply_markup=kb,
    )
    await callback.answer()


@admin_router.callback_query(F.data.startswith("admin_closeday_day_"))
async def admin_close_day_confirm(
    callback: CallbackQuery,
) -> None:
    date_str = callback.data.replace("admin_closeday_day_", "")
    date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
    kb = confirm_close_day_kb(date_str)
    await callback.message.edit_text(
        f"🚫 Закрыть <b>{date_obj.strftime('%d.%m.%Y')}</b>?\n\nВсе записи на этот день будут отменены.",
        parse_mode="HTML",
        reply_markup=kb,
    )
    await callback.answer()


@admin_router.callback_query(F.data.startswith("admin_closeday_confirm_"))
async def admin_close_day_process(
    callback: CallbackQuery,
    db: Database,
) -> None:
    date_str = callback.data.replace("admin_closeday_confirm_", "")
    await db.close_day(date_str)
    date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
    await callback.message.edit_text(
        f"✅ День <b>{date_obj.strftime('%d.%m.%Y')}</b> закрыт. Записи отменены.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀ В админ-меню", callback_data="menu_admin")]
        ]),
    )
    await callback.answer()


@admin_router.callback_query(F.data == "admin_closeday_noop")
async def admin_closeday_noop(callback: CallbackQuery) -> None:
    await callback.answer()
