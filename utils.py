import asyncio

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramRetryAfter
from aiogram.types import Message

import db


async def safe_edit(message: Message, text: str, markup=None):
    try:
        await message.edit_text(text, reply_markup=markup)
    except TelegramBadRequest:
        pass


async def with_retry(factory, tries: int = 3):
    """اگه تلگرام flood-wait داد صبر می‌کنه و دوباره تلاش می‌کنه."""
    for _ in range(tries):
        try:
            return await factory()
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after + 1)
    return None


def extract_media(m: Message):
    """(نوع، file_id) یا None"""
    if m.photo:
        return "photo", m.photo[-1].file_id
    if m.video:
        return "video", m.video.file_id
    if m.animation:  # قبل از document چک میشه
        return "animation", m.animation.file_id
    if m.document:
        return "document", m.document.file_id
    if m.audio:
        return "audio", m.audio.file_id
    if m.voice:
        return "voice", m.voice.file_id
    if m.video_note:
        return "video_note", m.video_note.file_id
    return None


async def send_file(bot: Bot, chat_id: int, f, caption: str | None):
    t, fid = f["file_type"], f["file_id"]
    if t == "photo":
        return await bot.send_photo(chat_id, fid, caption=caption)
    if t == "video":
        return await bot.send_video(chat_id, fid, caption=caption)
    if t == "animation":
        return await bot.send_animation(chat_id, fid, caption=caption)
    if t == "document":
        return await bot.send_document(chat_id, fid, caption=caption)
    if t == "audio":
        return await bot.send_audio(chat_id, fid, caption=caption)
    if t == "voice":
        return await bot.send_voice(chat_id, fid, caption=caption)
    if t == "video_note":
        return await bot.send_video_note(chat_id, fid)


async def missing_channels(bot: Bot, user_id: int) -> list:
    missing = []
    for ch in await db.list_channels():
        try:
            m = await bot.get_chat_member(ch["chat_id"], user_id)
        except Exception:
            continue  # ربات از کانال حذف شده یا مشکل موقتی؛ کاربر رو گیر نندازیم
        if m.status in ("left", "kicked"):
            missing.append(ch)
        elif m.status == "restricted" and not getattr(m, "is_member", True):
            missing.append(ch)
    return missing


async def deliver(bot: Bot, chat_id: int, user_id: int, batch):
    files = await db.get_files(batch["id"])
    caption = await db.get_setting("default_caption")
    for f in files:
        await with_retry(lambda f=f: send_file(bot, chat_id, f, caption))
        await asyncio.sleep(0.05)
    await db.log_download(batch["id"], user_id)
