import html

from aiogram import Bot, F, Router
from aiogram.filters import CommandObject, CommandStart
from aiogram.types import CallbackQuery, Message

import db
import keyboards as kb
import utils

router = Router()
router.message.filter(F.chat.type == "private")


async def process_code(bot: Bot, chat_id: int, user_id: int, code: str):
    batch = await db.get_batch(code)
    if not batch:
        await bot.send_message(chat_id, "❌ این لینک معتبر نیست یا حذف شده.")
        return
    missing = await utils.missing_channels(bot, user_id)
    if missing:
        await bot.send_message(
            chat_id,
            "⚠️ برای دریافت فایل‌ها اول تو کانال‌های زیر عضو شو، بعد دکمه «عضو شدم» رو بزن:",
            reply_markup=kb.join_kb(missing, code),
        )
        return
    await utils.deliver(bot, chat_id, user_id, batch)


@router.message(CommandStart())
async def start(message: Message, command: CommandObject, bot: Bot):
    await db.add_user(message.from_user)
    if not command.args:
        name = html.escape(message.from_user.first_name or "")
        await message.answer(f"سلام {name} 👋\nبرای دریافت فایل از لینک اختصاصی استفاده کن.")
        return
    await process_code(bot, message.chat.id, message.from_user.id, command.args)


@router.callback_query(F.data.startswith("chk:"))
async def recheck(cb: CallbackQuery, bot: Bot):
    code = cb.data.split(":", 1)[1]
    missing = await utils.missing_channels(bot, cb.from_user.id)
    if missing:
        await cb.answer("هنوز تو همه کانال‌ها عضو نشدی ❌", show_alert=True)
        return
    await cb.answer()
    try:
        await cb.message.delete()
    except Exception:
        pass
    await process_code(bot, cb.from_user.id, cb.from_user.id, code)
