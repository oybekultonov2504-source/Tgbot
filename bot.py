import asyncio
import os
import re
import shutil
import uuid
from pathlib import Path

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup, Message
from dotenv import load_dotenv
import yt_dlp

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
DOWNLOAD_DIR = Path(os.getenv("DOWNLOAD_DIR", "downloads"))
MAX_CONCURRENT = int(os.getenv("MAX_CONCURRENT_DOWNLOADS", "2"))
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

router = Router()
semaphore = asyncio.Semaphore(MAX_CONCURRENT)
URL_RE = re.compile(r"https?://(?:www\.)?(?:youtube\.com|youtu\.be)/\S+", re.I)

# Temporary in-memory jobs for the local MVP.
jobs: dict[str, str] = {}


def format_keyboard(job_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎵 MP3", callback_data=f"dl:{job_id}:mp3"),
            InlineKeyboardButton(text="📱 360p", callback_data=f"dl:{job_id}:360"),
        ],
        [
            InlineKeyboardButton(text="📺 720p", callback_data=f"dl:{job_id}:720"),
            InlineKeyboardButton(text="🔥 Лучшее", callback_data=f"dl:{job_id}:best"),
        ],
    ])


def ydl_options(mode: str, folder: Path) -> dict:
    common = {
        "outtmpl": str(folder / "%(title).120s [%(id)s].%(ext)s"),
        "noplaylist": True,
        "restrictfilenames": True,
        "quiet": True,
        "no_warnings": True,
    }
    if mode == "mp3":
        return common | {
            "format": "bestaudio/best",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }],
        }
    height = {"360": 360, "720": 720}.get(mode)
    if height:
        common["format"] = (
            f"bestvideo[height<={height}]+bestaudio/"
            f"best[height<={height}]/best"
        )
        common["merge_output_format"] = "mp4"
    else:
        common["format"] = "bestvideo+bestaudio/best"
        common["merge_output_format"] = "mp4"
    return common


def extract_info(url: str) -> dict:
    with yt_dlp.YoutubeDL({"quiet": True, "noplaylist": True}) as ydl:
        return ydl.extract_info(url, download=False)


def download(url: str, mode: str, folder: Path) -> Path:
    with yt_dlp.YoutubeDL(ydl_options(mode, folder)) as ydl:
        ydl.extract_info(url, download=True)
    candidates = [p for p in folder.iterdir() if p.is_file() and not p.name.endswith((".part", ".ytdl"))]
    if not candidates:
        raise RuntimeError("Файл после загрузки не найден")
    return max(candidates, key=lambda p: p.stat().st_mtime)


@router.message(CommandStart())
async def start(message: Message):
    await message.answer(
        "👋 Отправь ссылку YouTube. Я покажу варианты загрузки.\n\n"
        "Скачивай только контент, который тебе разрешено сохранять."
    )


@router.message(F.text)
async def receive_url(message: Message):
    text = message.text or ""
    match = URL_RE.search(text)
    if not match:
        await message.answer("Отправь корректную ссылку YouTube.")
        return

    url = match.group(0)
    status = await message.answer("🔎 Проверяю видео…")
    try:
        info = await asyncio.to_thread(extract_info, url)
        title = info.get("title") or "Видео"
        duration = info.get("duration")
        duration_text = f" • {duration // 60}:{duration % 60:02d}" if isinstance(duration, int) else ""
        job_id = uuid.uuid4().hex[:12]
        jobs[job_id] = url
        await status.edit_text(
            f"🎬 {title}{duration_text}\n\nВыбери формат:",
            reply_markup=format_keyboard(job_id),
        )
    except Exception as exc:
        await status.edit_text(f"❌ Не удалось получить видео: {type(exc).__name__}")


@router.callback_query(F.data.startswith("dl:"))
async def download_callback(callback: CallbackQuery):
    _, job_id, mode = callback.data.split(":", 2)
    url = jobs.get(job_id)
    if not url:
        await callback.answer("Ссылка устарела. Отправь её ещё раз.", show_alert=True)
        return

    await callback.answer()
    msg = callback.message
    await msg.edit_text("⏳ Загружаю и обрабатываю…")
    folder = DOWNLOAD_DIR / uuid.uuid4().hex
    folder.mkdir(parents=True, exist_ok=True)

    try:
        async with semaphore:
            path = await asyncio.to_thread(download, url, mode, folder)

        size_mb = path.stat().st_size / 1024 / 1024
        await msg.edit_text(f"📤 Готово: {size_mb:.1f} MB. Отправляю…")
        media = FSInputFile(path)
        if mode == "mp3":
            await msg.answer_audio(media)
        else:
            await msg.answer_video(media, supports_streaming=True)
        await msg.delete()
    except Exception as exc:
        await msg.edit_text(
            "❌ Загрузка не удалась. Проверь FFmpeg, доступ к YouTube и попробуй другое видео.\n"
            f"Ошибка: {type(exc).__name__}"
        )
    finally:
        shutil.rmtree(folder, ignore_errors=True)
        jobs.pop(job_id, None)


async def main():
    if not TOKEN or TOKEN == "PASTE_YOUR_BOT_TOKEN_HERE":
        raise RuntimeError("Добавь BOT_TOKEN в файл .env")
    bot = Bot(TOKEN)
    dp = Dispatcher()
    dp.include_router(router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
