import asyncio
import html

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramForbiddenError
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (CallbackQuery, Message, MessageOriginChannel,
                           ReactionTypeEmoji)

import config
import db
import keyboards as kb
import utils

router = Router()
router.message.filter(F.chat.type == "private", F.from_user.id.in_(config.ADMIN_IDS))
router.callback_query.filter(F.from_user.id.in_(config.ADMIN_IDS))

PANEL = "🌹 به پنل مدیریت خوش اومدی"
_tasks: set = set()


class St(StatesGroup):
    upload = State()
    broadcast = State()
    pin = State()
    caption = State()
    channel = State()


async def drop_draft(state: FSMContext):
    """اگه وسط آپلود لغو شد، پیش‌نویس رو پاک کن."""
    if await state.get_state() == St.upload.state:
        data = await state.get_data()
        if data.get("batch_id"):
            await db.delete_batch(data["batch_id"])


# ---------- پنل ----------
@router.message(Command("admin"))
@router.message(Command("cancel"))
async def cmd_admin(message: Message, state: FSMContext):
    await drop_draft(state)
    await state.clear()
    await message.answer(PANEL, reply_markup=kb.admin_panel())


@router.callback_query(F.data == "adm:home")
async def home(cb: CallbackQuery, state: FSMContext):
    await drop_draft(state)
    await state.clear()
    await utils.safe_edit(cb.message, PANEL, kb.admin_panel())
    await cb.answer()


# ---------- آمار ----------
@router.callback_query(F.data == "adm:stats")
async def stats(cb: CallbackQuery):
    s = await db.stats()
    u, d = s["users"], s["dl"]
    text = (
        "📊 <b>آمار ربات</b>\n\n"
        f"👥 کل کاربران: <b>{u['total']}</b>\n"
        f"🚫 بلاک‌کرده‌ها: {u['blocked']}\n"
        f"📁 تعداد آپلودها: {s['batches']}\n\n"
        "📥 <b>تعداد دانلود</b>\n"
        f"• ۱۲ ساعت اخیر: <b>{d['h12']}</b>\n"
        f"• ۱ روز اخیر: <b>{d['d1']}</b>\n"
        f"• ۱ هفته اخیر: <b>{d['w1']}</b>\n"
        f"• ۱ ماه اخیر: <b>{d['m1']}</b>\n"
        f"• کل: <b>{d['total']}</b>"
    )
    await utils.safe_edit(cb.message, text, kb.back())
    await cb.answer()


# ---------- آپلود گروهی ----------
@router.callback_query(F.data == "adm:upload")
async def upload_start(cb: CallbackQuery, state: FSMContext):
    await drop_draft(state)
    batch_id, code = await db.create_batch(cb.from_user.id)
    await state.set_state(St.upload)
    await state.update_data(batch_id=batch_id, code=code)
    await utils.safe_edit(
        cb.message,
        "📥 فایل‌هات رو (عکس، فیلم، گیف، ...) پشت سر هم بفرست.\n"
        "وقتی تموم شد دکمه «پایان» رو بزن.",
        kb.upload_controls(),
    )
    await cb.answer()


@router.callback_query(F.data == "adm:upload_cancel", StateFilter(St.upload))
async def upload_cancel(cb: CallbackQuery, state: FSMContext):
    await drop_draft(state)
    await state.clear()
    await utils.safe_edit(cb.message, PANEL, kb.admin_panel())
    await cb.answer("لغو شد")


@router.callback_query(F.data == "adm:upload_done", StateFilter(St.upload))
async def upload_done(cb: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    n = await db.finish_batch(data["batch_id"])
    if not n:
        await cb.answer("هنوز فایلی نفرستادی!", show_alert=True)
        return
    await state.clear()
    me = await bot.me()
    link = f"https://t.me/{me.username}?start={data['code']}"
    await utils.safe_edit(
        cb.message,
        f"✅ {n} فایل ذخیره شد.\n\n🔗 لینک:\n<code>{link}</code>",
        kb.back(),
    )
    await cb.answer()


@router.message(StateFilter(St.upload))
async def upload_receive(message: Message, state: FSMContext):
    media = utils.extract_media(message)
    if not media:
        await message.reply("⚠️ فقط فایل/مدیا بفرست (یا «پایان» رو بزن).")
        return
    data = await state.get_data()
    await db.add_file(data["batch_id"], media[1], media[0], message.message_id)
    try:
        await message.react([ReactionTypeEmoji(emoji="👍")])
    except Exception:
        pass


# ---------- جوین اجباری ----------
async def show_channels(target: Message, edit: bool):
    channels = await db.list_channels()
    text = "🔒 <b>کانال‌های جوین اجباری</b>\n\n"
    text += "برای حذف روی کانال بزن." if channels else "هنوز کانالی اضافه نشده."
    markup = kb.channels_menu(channels)
    if edit:
        await utils.safe_edit(target, text, markup)
    else:
        await target.answer(text, reply_markup=markup)


@router.callback_query(F.data == "adm:channels")
async def channels(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await show_channels(cb.message, edit=True)
    await cb.answer()


@router.callback_query(F.data.startswith("adm:chdel:"))
async def channel_del(cb: CallbackQuery):
    await db.del_channel(int(cb.data.split(":")[2]))
    await show_channels(cb.message, edit=True)
    await cb.answer("حذف شد")


@router.callback_query(F.data == "adm:chadd")
async def channel_add(cb: CallbackQuery, state: FSMContext):
    await state.set_state(St.channel)
    await utils.safe_edit(
        cb.message,
        "اول ربات رو تو کانال/گروه <b>ادمین</b> کن، بعد یکی از اینا رو بفرست:\n"
        "• یوزرنیم (مثل @channel)\n• آیدی عددی (مثل -100123...)\n• یه پیام فوروارد شده از کانال\n\n"
        "برای لغو: /cancel",
    )
    await cb.answer()


@router.message(StateFilter(St.channel))
async def channel_receive(message: Message, state: FSMContext, bot: Bot):
    ref = None
    if isinstance(message.forward_origin, MessageOriginChannel):
        ref = message.forward_origin.chat.id
    elif message.text:
        ref = message.text.strip().replace("https://t.me/", "").replace("t.me/", "")
        if ref.lstrip("-").isdigit():
            ref = int(ref)
        elif not ref.startswith("@"):
            ref = "@" + ref
    if ref is None:
        await message.reply("⚠️ یوزرنیم، آیدی یا پیام فوروارد شده بفرست.")
        return
    try:
        chat = await bot.get_chat(ref)
        me = await bot.me()
        member = await bot.get_chat_member(chat.id, me.id)
    except Exception as e:
        await message.reply(f"❌ کانال پیدا نشد یا ربات داخلش نیست.\n<code>{html.escape(str(e))}</code>")
        return
    if member.status not in ("administrator", "creator"):
        await message.reply("❌ ربات تو اون کانال ادمین نیست.")
        return
    link = f"https://t.me/{chat.username}" if chat.username else None
    if not link:
        try:
            link = await bot.export_chat_invite_link(chat.id)
        except Exception:
            link = None
    if not link:
        await message.reply("❌ کانال خصوصیه و ربات دسترسی ساخت لینک دعوت نداره. اون دسترسی رو بده و دوباره بفرست.")
        return
    await db.add_channel(chat.id, chat.title or str(chat.id), chat.username, link)
    await state.clear()
    await message.answer(f"✅ «{html.escape(chat.title or '')}» اضافه شد.")
    await show_channels(message, edit=False)


# ---------- کپشن پیشفرض ----------
async def show_caption(target: Message):
    cap = await db.get_setting("default_caption")
    text = "🖊 <b>کپشن پیشفرض</b>\n\n"
    text += f"کپشن فعلی:\n{cap}" if cap else "کپشنی تنظیم نشده."
    await utils.safe_edit(target, text, kb.caption_menu(bool(cap)))


@router.callback_query(F.data == "adm:caption")
async def caption(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await show_caption(cb.message)
    await cb.answer()


@router.callback_query(F.data == "adm:capdel")
async def caption_del(cb: CallbackQuery):
    await db.del_setting("default_caption")
    await show_caption(cb.message)
    await cb.answer("حذف شد")


@router.callback_query(F.data == "adm:capset")
async def caption_set(cb: CallbackQuery, state: FSMContext):
    await state.set_state(St.caption)
    await utils.safe_edit(cb.message, "✏️ کپشن جدید رو بفرست (حداکثر ۱۰۲۴ کاراکتر).\nبرای لغو: /cancel")
    await cb.answer()


@router.message(StateFilter(St.caption), F.text)
async def caption_receive(message: Message, state: FSMContext):
    if len(message.text) > 1024:
        await message.reply("⚠️ کپشن بلند تر از ۱۰۲۴ کاراکتره.")
        return
    await db.set_setting("default_caption", message.html_text)
    await state.clear()
    await message.answer("✅ کپشن ذخیره شد. از این به بعد روی همه فایل‌ها میره.", reply_markup=kb.back())


# ---------- ارسال همگانی / سنجاق ----------
async def run_broadcast(bot: Bot, admin_id: int, from_chat: int, msg_id: int, pin: bool):
    ids = await db.all_user_ids()
    ok = fail = 0
    for uid in ids:
        try:
            sent = await utils.with_retry(
                lambda: bot.copy_message(uid, from_chat, msg_id)
            )
            if sent is None:
                fail += 1
                continue
            if pin:
                try:
                    await utils.with_retry(
                        lambda: bot.pin_chat_message(uid, sent.message_id, disable_notification=True)
                    )
                except Exception:
                    pass
            ok += 1
        except TelegramForbiddenError:
            await db.mark_blocked(uid)
            fail += 1
        except Exception:
            fail += 1
        await asyncio.sleep(0.05)  # حدود ۲۰ پیام در ثانیه
    await bot.send_message(
        admin_id,
        f"✅ {'ارسال و سنجاق' if pin else 'ارسال همگانی'} تموم شد\n\n"
        f"موفق: <b>{ok}</b>\nناموفق: <b>{fail}</b>",
    )


def launch(bot: Bot, message: Message, pin: bool):
    t = asyncio.create_task(
        run_broadcast(bot, message.from_user.id, message.chat.id, message.message_id, pin)
    )
    _tasks.add(t)
    t.add_done_callback(_tasks.discard)


@router.callback_query(F.data == "adm:broadcast")
async def broadcast_start(cb: CallbackQuery, state: FSMContext):
    await state.set_state(St.broadcast)
    await utils.safe_edit(
        cb.message,
        "📨 پیامی که میخوای برای همه کاربرا بره رو بفرست (هر نوع پیامی).\nبرای لغو: /cancel",
    )
    await cb.answer()


@router.callback_query(F.data == "adm:pin")
async def pin_start(cb: CallbackQuery, state: FSMContext):
    await state.set_state(St.pin)
    await utils.safe_edit(
        cb.message,
        "📌 پیامی که میخوای برای همه کاربرا بره و تو چتشون <b>سنجاق</b> بشه رو بفرست.\nبرای لغو: /cancel",
    )
    await cb.answer()


@router.message(StateFilter(St.broadcast))
async def broadcast_receive(message: Message, state: FSMContext, bot: Bot):
    await state.clear()
    launch(bot, message, pin=False)
    await message.reply("⏳ ارسال شروع شد. وقتی تموم شد گزارش میدم.")


@router.message(StateFilter(St.pin))
async def pin_receive(message: Message, state: FSMContext, bot: Bot):
    await state.clear()
    launch(bot, message, pin=True)
    await message.reply("⏳ ارسال و سنجاق شروع شد. وقتی تموم شد گزارش میدم.")
