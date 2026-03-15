import os
from pathlib import Path
from dataclasses import dataclass

from dotenv import load_dotenv

# Корень проекта — от него ищем .env и database.db при любом способе запуска
PROJECT_ROOT = Path(__file__).resolve().parent
load_dotenv(PROJECT_ROOT / ".env")


@dataclass
class Config:
    BOT_TOKEN: str
    ADMIN_ID: int
    CHANNEL_ID: int
    CHANNEL_LINK: str
    DATABASE_PATH: str = "database.db"


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

    channel_id = int(os.getenv("CHANNEL_ID", "0"))
    if not channel_id:
        raise RuntimeError("Не указан CHANNEL_ID в .env")

    channel_link = os.getenv("CHANNEL_LINK", "")
    if not channel_link:
        raise RuntimeError("Не указан CHANNEL_LINK в .env")

    db_path = os.getenv("DATABASE_PATH", str(PROJECT_ROOT / "database.db"))

    return Config(
        BOT_TOKEN=token,
        ADMIN_ID=admin_id,
        CHANNEL_ID=channel_id,
        CHANNEL_LINK=channel_link,
        DATABASE_PATH=db_path,
    )