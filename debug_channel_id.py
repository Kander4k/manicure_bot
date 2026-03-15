import asyncio
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties

API_TOKEN = "8326116015:AAGWEHT_YVmSbDS30xD5g3YHW69CwDxtKcc"

async def main():
    bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
    me = await bot.get_me()
    print("Bot:", me)

    # Попробуем просто отправить сообщение в канал по @username
    # и посмотрим, что скажет ошибка
    try:
        msg = await bot.send_message(
            chat_id="@manicure777777",
            text="Тестовое сообщение для определения ID канала",
        )
        print("Message sent, chat id =", msg.chat.id)
    except Exception as e:
        print("Error:", e)

    await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())