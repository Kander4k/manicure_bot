from aiogram.fsm.state import StatesGroup, State


class AdminStates(StatesGroup):
    CHOOSING_ACTION = State()
    ADD_DAY_CHOOSE_DATE = State()
    ADD_SLOT_CHOOSE_DATE = State()
    ADD_SLOT_CHOOSE_TIME = State()
    DELETE_SLOT_CHOOSE_DATE = State()
    DELETE_SLOT_CHOOSE_SLOT = State()
    CLOSE_DAY_CHOOSE_DATE = State()
    VIEW_SCHEDULE_CHOOSE_DATE = State()
    CANCEL_BOOKING_CHOOSE_DATE = State()
    CANCEL_BOOKING_CHOOSE_BOOKING = State()