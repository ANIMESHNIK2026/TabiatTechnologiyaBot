from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
import os

BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

@dp.message_handler()
async def echo(message: types.Message):
    await message.answer("Привет!")

if __name__ == "__main__":
    executor.start_polling(dp)
