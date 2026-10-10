import asyncio
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramRetryAfter
from aiogram.types import InputMediaPhoto, Message

import db


def full_name(u) -> str:
    return " ".join(x for x in (u["first_name"], u["last_name"]) if x).strip()


def user_label(u) -> str:
    """@یوزرنیم؛ اگه نداشت اسمی که خودش گذاشته؛ اگه اون هم نبود آیدی عددی."""
    if u["username"]:
        return f"@{u['username']}"
    return full_name(u) or str(u["user_id"])


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


async def _is_missing(bot: Bot, ch, user_id: int) -> bool:
    try:
        m = await bot.get_chat_member(ch["chat_id"], user_id)
    except Exception:
        return False  # ربات از کانال حذف شده یا مشکل موقتی؛ کاربر رو گیر نندازیم
    if m.status in ("left", "kicked"):
        return True
    return m.status == "restricted" and not getattr(m, "is_member", True)


async def missing_channels(bot: Bot, user_id: int) -> list:
    """کانال‌ها رو هم‌زمان چک می‌کنه (نه یکی‌یکی)، با حفظ ترتیب."""
    chans = await db.list_channels()
    results = await asyncio.gather(*(_is_missing(bot, ch, user_id) for ch in chans))
    return [ch for ch, miss in zip(chans, results) if miss]


_bg_tasks: set = set()


def spawn(coro):
    """کار پس‌زمینه که جواب کاربر رو معطل نکنه؛ خطاش فقط لاگ میشه."""
    t = asyncio.create_task(coro)
    _bg_tasks.add(t)

    def _done(task):
        _bg_tasks.discard(task)
        if not task.cancelled() and task.exception():
            logging.warning("background task failed: %r", task.exception())

    t.add_done_callback(_done)
    return t


async def delete_after(bot: Bot, messages: list, delay: int):
    """بعد از delay ثانیه، پیام‌های داده‌شده رو از چت پاک می‌کنه."""
    await asyncio.sleep(delay)
    for m in messages:
        try:
            await bot.delete_message(m.chat.id, m.message_id)
        except Exception:
            pass


MAX_ALBUM = 10  # سقف تلگرام برای هر آلبوم


def group_files(files):
    """عکس‌های پشت‌سرهم رو ده‌تا‌ده‌تا گروه می‌کنه؛ بقیه فایل‌ها تکی و به همون ترتیب میان.
    خروجی: لیست (photos یا single، [فایل‌ها])"""
    out, buf = [], []

    def flush():
        nonlocal buf
        if buf:
            out.append(("photos", buf))
            buf = []

    for f in files:
        if f["file_type"] == "photo":
            buf.append(f)
            if len(buf) == MAX_ALBUM:
                flush()
        else:
            flush()
            out.append(("single", [f]))
    flush()
    return out


async def deliver(bot: Bot, chat_id: int, user_id: int, batch):
    files, caption, enabled_raw, secs_raw = await asyncio.gather(
        db.get_files(batch["id"]),
        db.get_setting("default_caption"),
        db.get_setting("delete_timer_enabled"),
        db.get_setting("delete_timer_seconds"),
    )
    spawn(db.log_download(batch["id"], user_id))  # ثبت آمار، ارسال فایل رو معطل نکنه
    sent = []
    first = True  # کپشن فقط روی اولین پیام/آلبوم میره
    for kind, group in group_files(files):
        cap = caption if first else None
        first = False
        if kind == "photos" and len(group) > 1:
            # آلبوم: عکس‌ها به‌صورت پک (حداکثر ۱۰ تا) ارسال میشن
            media = [
                InputMediaPhoto(media=f["file_id"], caption=cap if i == 0 else None)
                for i, f in enumerate(group)
            ]
            msgs = await with_retry(lambda media=media: bot.send_media_group(chat_id, media))
            if msgs:
                sent.extend(msgs)
        else:
            for f in group:
                m = await with_retry(lambda f=f, cap=cap: send_file(bot, chat_id, f, cap))
                if m:
                    sent.append(m)
                cap = None
                await asyncio.sleep(0.05)
        await asyncio.sleep(0.05)

    enabled = enabled_raw != "0"
    secs = int(secs_raw) if secs_raw and secs_raw.isdigit() else 30
    if enabled and secs > 0 and sent:
        await bot.send_message(
            chat_id,
            f"⚠️ این فایل(ها) تا <b>{secs} ثانیه</b> دیگه از این چت پاک می‌شن؛ "
            "حتماً سیوشون کن یا به چت دیگه‌ای فوروارد کن.",
        )
        asyncio.create_task(delete_after(bot, sent, secs))
