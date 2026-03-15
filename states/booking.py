from aiogram.fsm.state import StatesGroup, State


class BookingStates(StatesGroup):
    CHOOSING_DATE = State()
    CHOOSING_TIME = State()
    ENTERING_NAME = State()
    ENTERING_PHONE = State()
    CONFIRMING = State()