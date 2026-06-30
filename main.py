import logging
import os
import asyncio
import json
import threading
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from googleapiclient.discovery import build
from datetime import datetime, timedelta
from collections import defaultdict
import aioschedule
from flask import Flask
import datetime
import asyncio
import aioschedule
from pytube import YouTube

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable is not set.")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
CHANNEL_ID = os.getenv("CHANNEL_ID")
CHAT_ID = -1002371278515
SUBSCRIBERS_FILE = "subscribers.json"
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

app = Flask(__name__)


@app.route("/")
def home():
    return "Bot is alive!"


def run_flask():
    app.run(host="0.0.0.0", port=8080)


threading.Thread(target=run_flask, daemon=True).start()

def load_subscribers() -> dict:
    if os.path.exists(SUBSCRIBERS_FILE):
        try:
            with open(SUBSCRIBERS_FILE, "r") as f:
                data = json.load(f)
            if isinstance(data, list):
                return {str(cid): "номаълум" for cid in data}
            return data
        except Exception:
            return {}
    return {}


def save_subscribers(subs: dict):
    try:
        with open(SUBSCRIBERS_FILE, "w") as f:
            json.dump(subs, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error("Failed to save subscribers: %s", e)


subscribers: dict = load_subscribers()


async def check_youtube(notify_chat=True, notify_subscribers=True):
    try:
        youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)

        # Берём последние 5 видео
        request = youtube.search().list(
            part="snippet",
            channelId=CHANNEL_ID,
            order="date",
            maxResults=5
        )
        response = request.execute()

        videos = []
        for item in response["items"]:
            if "videoId" in item["id"]:
                video_id = item["id"]["videoId"]
                title = item["snippet"]["title"]
                url = f"https://www.youtube.com/watch?v={video_id}"
                videos.append((title, url))
                if notify_chat:
                    await bot.send_message(CHAT_ID, f"📺 {title}\n{url}")

        # Рассылка подписчикам
        if notify_subscribers and videos:
            for chat_id in list(subscribers.keys()):
                try:
                    for title, url in videos:
                        await bot.send_message(
                            int(chat_id),
                            f"🔔 Навори нав аз Tabiat Technologiya:\n📺 {title}\n{url}"
                        )
                except Exception as e:
                    logger.warning("Could not notify subscriber %s: %s", chat_id, e)

        return videos

    except Exception as e:
        logger.error("Failed to fetch YouTube videos: %s", e)
        if notify_chat:
            await bot.send_message(CHAT_ID, f"❌ Хатогӣ ҳангоми гирифтани видеоҳо: {e}")
        return []

async def scheduler():
    await bot.send_message(CHAT_ID, "✅ Планировщик запущен")

    while True:
        now = datetime.datetime.utcnow()

        # Каждое воскресенье в 19:00 UTC
        if now.weekday() == 6 and now.hour == 19 and now.minute == 0:
            await check_youtube()

        await asyncio.sleep(60)  # проверка каждую минуту


@dp.message_handler(commands=["start"])
async def start_command(message: types.Message):
    try:
        await message.answer(
            "Салом! Хуш омадед ба боти Tabiat Technologiya 🌿\n\n"
            "/help — Менюи амалҳо\n"
            "Ман ба шумо кӯмак мекунам. Паёми худро нависед!"
        )
    except Exception as e:
        logger.error("Failed to send start message: %s", e)


@dp.message_handler(commands=["help"])
async def help_command(message: types.Message):
    try:
        await message.answer(
            "📋 Рӯйхати фармонҳо:\n\n"
            "/start — Оғози кор бо бот\n"
            "/help — Менюи амалҳо\n"
            "/videos — Санҷиши видеоҳои нави YouTube\n"
            "/allvideos — Ҳаммаи наворҳои канали ТАБИАТ ТЕХНОЛОГИЯ\n"
            "/subscribe — Обуна шудан ба огоҳиномаҳо\n"
            "/unsubscribe — Бекор кардани обуна\n"
            "/stats — Шумораи обунашудагон\n"
            "/broadcast — Фиристодани эълон (танҳо админ)\n"
            "/subscribers — Тафсилоти обунашудагон (танҳо админ)\n\n"
            "Бот ҳоло дар мавриди сохту соз қарор дорад!"
        )
    except Exception as e:
        logger.error("Failed to send help message: %s", e)


@dp.message_handler(commands=["videos"])
async def videos_command(message: types.Message):
    if not YOUTUBE_API_KEY or not CHANNEL_ID:
        await message.answer("⚠️ YouTube API танзим нашудааст. Лутфан YOUTUBE_API_KEY ва CHANNEL_ID-ро илова кунед.")
        return
    try:
        await message.answer("🔍 Дар ҳоли ҷустуҷӯи охирин видеоҳо...")
        videos = await check_youtube(notify_chat=False, notify_subscribers=False)
        if videos:
            for title, url in videos:
                await message.answer(f"📺 {title}\n{url}")
            await message.answer(f"✅ {len(videos)} охирин навор нишон дода шуд!")
        else:
            await message.answer("📭 Видео ёфт нашуд.")
    except Exception as e:
        logger.error("Videos command failed: %s", e)
        await message.answer(f"❌ Хатогӣ ҳангоми гирифтани видеоҳо: {e}")

@dp.message_handler(commands=["subscribe"])
async def subscribe_command(message: types.Message):
    try:
        chat_id = str(message.chat.id)
        if chat_id in subscribers:
            joined = subscribers[chat_id]
            await message.answer(f"✅ Шумо аллакай обуна шудаед!\nСана: {joined} 🔔")
        else:
            joined_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
            subscribers[chat_id] = joined_at
            save_subscribers(subscribers)
            await message.answer("🔔 Шумо бо муваффақият обуна шудед!\nҲангоми нашри видеои нав ба шумо паём мефиристам.")
    except Exception as e:
        logger.error("Subscribe command failed: %s", e)


@dp.message_handler(commands=["unsubscribe"])
async def unsubscribe_command(message: types.Message):
    try:
        chat_id = str(message.chat.id)
        if chat_id in subscribers:
            del subscribers[chat_id]
            save_subscribers(subscribers)
            await message.answer("🔕 Обунаи шумо бекор карда шуд.")
        else:
            await message.answer("ℹ️ Шумо ҳанӯз обуна нашудаед.")
    except Exception as e:
        logger.error("Unsubscribe command failed: %s", e)


@dp.message_handler(commands=["stats"])
async def stats_command(message: types.Message):
    try:
        count = len(subscribers)
        await message.answer(f"📊 Шумораи обунашудагон: {count} нафар")
    except Exception as e:
        logger.error("Stats command failed: %s", e)


@dp.message_handler(commands=["subscribers"])
async def subscribers_command(message: types.Message):
    if message.chat.id != ADMIN_ID:
        await message.answer("⛔ Шумо иҷозат надоред.")
        return
    try:
        total = len(subscribers)
        if total == 0:
            await message.answer("📭 Ҳанӯз ягон обунашуда нест.")
            return

        by_month = defaultdict(int)
        unknown = 0
        for joined_at in subscribers.values():
            if joined_at == "номаълум":
                unknown += 1
            else:
                try:
                    month = joined_at[:7]
                    by_month[month] += 1
                except Exception:
                    unknown += 1

        lines = [f"👥 Ҷамъи обунашудагон: {total} нафар\n"]
        lines.append("📅 Тақсимот аз рӯи моҳ:")
        for month in sorted(by_month.keys()):
            lines.append(f"  {month}: {by_month[month]} нафар")
        if unknown:
            lines.append(f"  Номаълум: {unknown} нафар")

        await message.answer("\n".join(lines))
    except Exception as e:
        logger.error("Subscribers command failed: %s", e)


@dp.message_handler(commands=["broadcast"])
async def broadcast_command(message: types.Message):
    if message.chat.id != ADMIN_ID:
        await message.answer("⛔ Шумо иҷозат надоред.")
        return
    text = message.get_args()
    if not text:
        await message.answer("✏️ Паёмро баъд аз фармон нависед:\n/broadcast Паёми шумо")
        return
    sent = 0
    failed = 0
    for chat_id in list(subscribers.keys()):
        try:
            await bot.send_message(int(chat_id), f"📢 Эълон:\n\n{text}")
            sent += 1
        except Exception as e:
            logger.warning("Broadcast failed for %s: %s", chat_id, e)
            failed += 1
    await message.answer(f"✅ Фиристода шуд: {sent}\n❌ Нашуд: {failed}")
    
@dp.message_handler(commands=["allvideos"])
async def all_videos(message: types.Message):
    try:
        youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)

        channel_response = youtube.channels().list(
            part="contentDetails",
            id=CHANNEL_ID
        ).execute()

        uploads_playlist_id = channel_response["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]

        videos = []
        next_page_token = None

        while True:
            playlist_response = youtube.playlistItems().list(
                part="snippet",
                playlistId=uploads_playlist_id,
                maxResults=50,
                pageToken=next_page_token
            ).execute()

            for item in playlist_response["items"]:
                title = item["snippet"]["title"]
                video_id = item["snippet"]["resourceId"]["videoId"]
                videos.append((title, video_id))

            next_page_token = playlist_response.get("nextPageToken")
            if not next_page_token:
                break

        # Отправляем список частями по 20 видео
        videos_per_page = 20
        for start in range(0, len(videos), videos_per_page):
            end = start + videos_per_page
            page_videos = videos[start:end]

            response_text = "📺 Наворҳои канал:\n\n"
            for i, (title, video_id) in enumerate(page_videos, start=start + 1):
                response_text += f"{i}. {title}\nhttps://www.youtube.com/watch?v={video_id}\n\n"

            await message.answer(response_text)

    except Exception as e:
        await message.answer(f"Хатоги дар ҳолати қабули руйхати наворҳо: {e}")

# Обработка YouTube ссылок
@dp.message_handler(lambda message: "youtube.com" in message.text or "youtu.be" in message.text)
async def handle_youtube(message: types.Message):
    await message.answer("⏳ Скачиваю видео...")
    try:
        yt = YouTube(message.text)
        stream = yt.streams.get_highest_resolution()
        file_path = stream.download(filename="video.mp4")
        await bot.send_video(message.chat.id, open(file_path, "rb"))
    except Exception as e:
        await message.answer(f"❌ Хатогӣ ҳангоми скачивании: {e}")

@dp.message_handler(lambda message: not message.text.startswith("/"))
async def echo(message: types.Message):
    try:
        await message.answer("Салом!")
    except Exception as e:
        logger.error("Failed to send message: %s", e)


if __name__ == "__main__":
    loop = asyncio.get_event_loop()

    # Запускаем планировщик как задачу
    loop.create_task(scheduler())

    # Запускаем бота в том же loop
    executor.start_polling(dp, skip_updates=True, loop=loop)

