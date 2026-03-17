import os
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv

# Корень проекта — от него ищем .env и database.db при любом способе запуска
PROJECT_ROOT = Path(__file__).resolve().parent
load_dotenv(PROJECT_ROOT / ".env")


@dataclass
class Config:
    BOT_TOKEN: str
    ADMIN_ID: int
    # Канал для ПОДПИСКИ (опционально): если не задан — подписка не требуется
    SUBSCRIBE_CHANNEL_ID: Optional[int] = None
    SUBSCRIBE_CHANNEL_LINK: str = ""

    # Канал-ЖУРНАЛ (опционально): если не задан — записи не дублируются в канал
    LOG_CHANNEL_ID: Optional[int] = None
    DATABASE_PATH: str = "database.db"
    CLIENT_NAME: str = "Manicure Master"
    PRICES_TEXT: str = ""
    PORTFOLIO_URL: str = ""


def load_config() -> Config:
    """
    Загружает конфиг из переменных окружения.
    Удобнее всего задать их в .env.
    """
    token = os.getenv("BOT_TOKEN", "")
    if not token:
        raise RuntimeError("Не указан BOT_TOKEN в .env")

    admin_id = int(os.getenv("ADMIN_ID", "0"))
    if not admin_id:
        raise RuntimeError("Не указан ADMIN_ID в .env")

    # --- Новые переменные (рекомендуемый способ) ---
    raw_subscribe_channel_id = os.getenv("SUBSCRIBE_CHANNEL_ID", "").strip()
    subscribe_channel_id: Optional[int] = (
        int(raw_subscribe_channel_id) if raw_subscribe_channel_id else None
    )
    subscribe_channel_link = os.getenv("SUBSCRIBE_CHANNEL_LINK", "").strip()

    raw_log_channel_id = os.getenv("LOG_CHANNEL_ID", "").strip()
    log_channel_id: Optional[int] = int(raw_log_channel_id) if raw_log_channel_id else None

    # --- Обратная совместимость со старым именованием ---
    # Раньше был один канал: CHANNEL_ID/CHANNEL_LINK (и для подписки, и для логов).
    raw_channel_id = os.getenv("CHANNEL_ID", "").strip()
    legacy_channel_id: Optional[int] = int(raw_channel_id) if raw_channel_id else None
    legacy_channel_link = os.getenv("CHANNEL_LINK", "").strip()

    if subscribe_channel_id is None:
        subscribe_channel_id = legacy_channel_id
    if not subscribe_channel_link:
        subscribe_channel_link = legacy_channel_link
    if log_channel_id is None:
        log_channel_id = legacy_channel_id

    db_path = os.getenv("DATABASE_PATH", str(PROJECT_ROOT / "database.db"))
    client_name = os.getenv("CLIENT_NAME", "Manicure Master")
    prices_text = os.getenv(
        "PRICES_TEXT",
        "💰 <b>Прайс-лист</b>\n\n"
        "💅 Услуга 1 — <b>1000₽</b>\n"
        "💅 Услуга 2 — <b>1500₽</b>\n",
    )
    portfolio_url = os.getenv(
        "PORTFOLIO_URL",
        "https://ru.pinterest.com/crystalwithluv/_created/",
    )

    return Config(
        BOT_TOKEN=token,
        ADMIN_ID=admin_id,
        SUBSCRIBE_CHANNEL_ID=subscribe_channel_id,
        SUBSCRIBE_CHANNEL_LINK=subscribe_channel_link,
        LOG_CHANNEL_ID=log_channel_id,
        DATABASE_PATH=db_path,
        CLIENT_NAME=client_name,
        PRICES_TEXT=prices_text,
        PORTFOLIO_URL=portfolio_url,
    )