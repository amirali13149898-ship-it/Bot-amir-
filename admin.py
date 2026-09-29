import asyncio
import html

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramForbiddenError
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (CallbackQuery, Message, MessageOriginChannel,
                           MessageOriginUser, ReactionTypeEmoji)

import access
import config
import db
import keyboards as kb
import utils

router = Router()
router.message.filter(F.chat.type == "private", access.IsAdmin())
router.callback_query.filter(access.IsAdmin())

PANEL = "🌹 به پنل مدیریت خوش اومدی"
_tasks: set = set()


class St(StatesGroup):
    upload = State()
    broadcast = State()
    pin = State()
    caption = State()
    channel = State()
    add_admin = State()
    set_seconds = State()


async def drop_draft(state: FSMContext):
    """اگه وسط آپلود لغو شد، پیش‌نویس رو پاک کن."""
    if await state.get_state() == St.upload.state:
        data = await state.get_data()
        if data.get("batch_id"):
            await db.delete_batch(data["batch_id"])


async def reset(state: FSMContext):
    await drop_draft(state)
    await state.clear()


async def show(target: Message, text: str, markup=None, edit: bool = True):
    """edit=True: ویرایش پیام اینلاین | edit=False: پیام جدید (برای دکمه‌های کیبورد)"""
    if edit:
        await utils.safe_edit(target, text, markup)
    else:
        await target.answer(text, reply_markup=markup)


# ---------- پنل ----------
@router.message(Command("admin"))
@router.message(Command("cancel"))
async def cmd_admin(message: Message, state: FSMContext):
    await reset(state)
    owner = access.is_owner(message.from_user.id)
    perms = access.perms_of(message.from_user.id)
    await message.answer("⌨️ کیبورد پنل فعال شد.", reply_markup=kb.admin_reply(perms, owner))
    await message.answer(PANEL, reply_markup=kb.admin_panel(perms, owner))


@router.callback_query(F.data == "adm:home")
async def home(cb: CallbackQuery, state: FSMContext):
    await reset(state)
    owner = access.is_owner(cb.from_user.id)
    await utils.safe_edit(cb.message, PANEL, kb.admin_panel(access.perms_of(cb.from_user.id), owner))
    await cb.answer()


# ---------- دکمه‌های کیبورد پایین (قبل از handlerهای state ثبت میشن تا اولویت داشته باشن) ----------
async def need_perm(message: Message, perm: str) -> bool:
    """اگه دسترسی نداشت True برمیگردونه و پیام قفل میفرسته."""
    if access.has_perm(message.from_user.id, perm):
        return False
    await message.answer("🔒 دسترسی این بخش رو نداری.")
    return True


@router.message(F.text == kb.BTN_STATS)
async def k_stats(message: Message, state: FSMContext):
    if await need_perm(message, "stats"):
        return
    await reset(state)
    await do_stats(message, edit=False)


@router.message(F.text == kb.BTN_UPLOAD)
async def k_upload(message: Message, state: FSMContext):
    if await need_perm(message, "upload"):
        return
    await reset(state)
    await do_upload_start(message, message.from_user.id, state, edit=False)


@router.message(F.text == kb.BTN_CHANNELS)
async def k_channels(message: Message, state: FSMContext):
    if await need_perm(message, "channels"):
        return
    await reset(state)
    await show_channels(message, edit=False)


@router.message(F.text == kb.BTN_CAPTION)
async def k_caption(message: Message, state: FSMContext):
    if await need_perm(message, "caption"):
        return
    await reset(state)
    await show_caption(message, edit=False)


@router.message(F.text == kb.BTN_BROADCAST)
async def k_broadcast(message: Message, state: FSMContext):
    if await need_perm(message, "broadcast"):
        return
    await reset(state)
    await do_broadcast_start(message, state, edit=False)


@router.message(F.text == kb.BTN_PIN)
async def k_pin(message: Message, state: FSMContext):
    if await need_perm(message, "pin"):
        return
    await reset(state)
    await do_pin_start(message, state, edit=False)


@router.message(F.text == kb.BTN_SETTINGS)
async def k_settings(message: Message, state: FSMContext):
    if await need_perm(message, "settings"):
        return
    await reset(state)
    await show_settings(message, edit=False)


@router.message(F.text == kb.BTN_ADMINS, access.IsOwner())
async def k_admins(message: Message, state: FSMContext):
    await reset(state)
    await show_admins(message, edit=False)


@router.message(F.text == kb.BTN_ADMINS)  # ادمین معمولی
async def k_admins_locked(message: Message):
    await message.answer("🔒 این بخش فقط مخصوص مالک ربات هست.")


async def need_perm_cb(cb: CallbackQuery, perm: str) -> bool:
    if access.has_perm(cb.from_user.id, perm):
        return False
    await cb.answer("🔒 دسترسی این بخش رو نداری.", show_alert=True)
    return True


# ---------- آمار ----------
@router.callback_query(F.data == "adm:stats")
async def stats(cb: CallbackQuery):
    if await need_perm_cb(cb, "stats"):
        return
    await do_stats(cb.message, edit=True)
    await cb.answer()


async def do_stats(target: Message, edit: bool):
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
    await show(target, text, kb.back(), edit)


# ---------- آپلود گروهی ----------
@router.callback_query(F.data == "adm:upload")
async def upload_start(cb: CallbackQuery, state: FSMContext):
    if await need_perm_cb(cb, "upload"):
        return
    await do_upload_start(cb.message, cb.from_user.id, state, edit=True)
    await cb.answer()


async def do_upload_start(target: Message, admin_id: int, state: FSMContext, edit: bool):
    await drop_draft(state)
    batch_id, code = await db.create_batch(admin_id)
    await state.set_state(St.upload)
    await state.update_data(batch_id=batch_id, code=code)
    await show(
        target,
        "📥 فایل‌هات رو (عکس، فیلم، گیف، ...) پشت سر هم بفرست.\n"
        "وقتی تموم شد دکمه «پایان» رو بزن.",
        kb.upload_controls(),
        edit,
    )


@router.callback_query(F.data == "adm:upload_cancel", StateFilter(St.upload))
async def upload_cancel(cb: CallbackQuery, state: FSMContext):
    await drop_draft(state)
    await state.clear()
    owner = access.is_owner(cb.from_user.id)
    await utils.safe_edit(cb.message, PANEL, kb.admin_panel(access.perms_of(cb.from_user.id), owner))
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
    await show(target, text, kb.channels_menu(channels), edit)


@router.callback_query(F.data == "adm:channels")
async def channels(cb: CallbackQuery, state: FSMContext):
    if await need_perm_cb(cb, "channels"):
        return
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
async def show_caption(target: Message, edit: bool = True):
    cap = await db.get_setting("default_caption")
    text = "🖊 <b>کپشن پیشفرض</b>\n\n"
    text += f"کپشن فعلی:\n{cap}" if cap else "کپشنی تنظیم نشده."
    await show(target, text, kb.caption_menu(bool(cap)), edit)


@router.callback_query(F.data == "adm:caption")
async def caption(cb: CallbackQuery, state: FSMContext):
    if await need_perm_cb(cb, "caption"):
        return
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


async def do_broadcast_start(target: Message, state: FSMContext, edit: bool):
    await state.set_state(St.broadcast)
    await show(
        target,
        "📨 پیامی که میخوای برای همه کاربرا بره رو بفرست (هر نوع پیامی).\nبرای لغو: /cancel",
        None,
        edit,
    )


async def do_pin_start(target: Message, state: FSMContext, edit: bool):
    await state.set_state(St.pin)
    await show(
        target,
        "📌 پیامی که میخوای برای همه کاربرا بره و تو چتشون <b>سنجاق</b> بشه رو بفرست.\nبرای لغو: /cancel",
        None,
        edit,
    )


@router.callback_query(F.data == "adm:broadcast")
async def broadcast_start(cb: CallbackQuery, state: FSMContext):
    if await need_perm_cb(cb, "broadcast"):
        return
    await do_broadcast_start(cb.message, state, edit=True)
    await cb.answer()


@router.callback_query(F.data == "adm:pin")
async def pin_start(cb: CallbackQuery, state: FSMContext):
    if await need_perm_cb(cb, "pin"):
        return
    await do_pin_start(cb.message, state, edit=True)
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


# ================= مدیریت ادمین‌ها (فقط مالک) =================
async def show_admins(target: Message, edit: bool):
    admins = await db.list_admins()
    text = "👑 <b>مدیریت ادمین‌ها</b>\n\n"
    text += "مالک‌ها:\n" + "\n".join(f"• <code>{i}</code>" for i in sorted(access.OWNER_IDS)) + "\n\n"
    text += "برای حذف ادمین روی اسمش بزن." if admins else "هنوز ادمین دیگه‌ای اضافه نشده."
    await show(target, text, kb.admins_menu(admins), edit)


@router.callback_query(F.data == "own:admins", access.IsOwner())
async def own_admins(cb: CallbackQuery, state: FSMContext):
    await reset(state)
    await show_admins(cb.message, edit=True)
    await cb.answer()


@router.callback_query(F.data == "own:add", access.IsOwner())
async def own_add(cb: CallbackQuery, state: FSMContext):
    await state.set_state(St.add_admin)
    await utils.safe_edit(
        cb.message,
        "➕ ادمین جدید رو با یکی از این روش‌ها معرفی کن:\n"
        "• آیدی عددی (مثل 123456789)\n"
        "• یوزرنیم (مثل @username) — فقط اگه قبلاً ربات رو استارت زده باشه\n"
        "• یه پیام فوروارد شده از اون شخص\n\n"
        "برای لغو: /cancel",
    )
    await cb.answer()


@router.message(StateFilter(St.add_admin), access.IsOwner())
async def own_add_receive(message: Message, state: FSMContext, bot: Bot):
    uid = None
    if isinstance(message.forward_origin, MessageOriginUser):
        uid = message.forward_origin.sender_user.id
    elif message.text:
        t = message.text.strip()
        if t.lstrip("-").isdigit():
            uid = int(t)
        else:
            uid = await db.find_user_by_username(t.lstrip("@").replace("https://t.me/", ""))
    if uid is None:
        await message.reply(
            "⚠️ پیدا نشد. آیدی عددی بفرست، یا یه پیام فوروارد شده از اون شخص "
            "(یوزرنیم فقط برای کسایی جواب میده که ربات رو استارت زدن)."
        )
        return
    if access.is_owner(uid):
        await message.reply("این شخص مالک ربات هست و از قبل دسترسی کامل داره.")
        return
    if access.is_admin(uid):
        await message.reply("این شخص از قبل ادمین هست.")
        return
    await db.add_admin(uid, message.from_user.id)
    await access.reload()
    await state.clear()
    await message.answer(f"✅ کاربر <code>{uid}</code> ادمین شد.")
    try:
        await bot.send_message(
            uid, "🌹 تو به عنوان ادمین ربات اضافه شدی.\nبرای باز کردن پنل: /admin"
        )
    except Exception:
        await message.answer("ℹ️ به این شخص پیام نرفت (احتمالاً ربات رو استارت نکرده). باید یه بار /start بزنه.")
    await show_admins(message, edit=False)


@router.callback_query(F.data.startswith("own:del:"), access.IsOwner())
async def own_del(cb: CallbackQuery):
    uid = int(cb.data.split(":")[2])
    await db.del_admin(uid)
    await access.reload()
    await show_admins(cb.message, edit=True)
    await cb.answer("ادمین حذف شد")


# ---------- دسترسی‌های تکی هر ادمین (فقط مالک) ----------
@router.callback_query(F.data.startswith("own:perm:"), access.IsOwner())
async def own_perm_open(cb: CallbackQuery):
    uid = int(cb.data.split(":")[2])
    current = await db.get_admin_perms(uid)
    await utils.safe_edit(
        cb.message,
        f"⚙️ <b>دسترسی‌های کاربر</b> <code>{uid}</code>\n\nبا زدن هر گزینه، روشن/خاموشش کن.",
        kb.perms_menu(uid, current),
    )
    await cb.answer()


@router.callback_query(F.data.startswith("own:permtg:"), access.IsOwner())
async def own_perm_toggle(cb: CallbackQuery):
    _, _, uid, key = cb.data.split(":")
    uid = int(uid)
    current = await db.get_admin_perms(uid)
    if key in current:
        current.discard(key)
    else:
        current.add(key)
    await db.set_admin_perms(uid, current)
    await access.reload()
    await utils.safe_edit(
        cb.message,
        f"⚙️ <b>دسترسی‌های کاربر</b> <code>{uid}</code>\n\nبا زدن هر گزینه، روشن/خاموشش کن.",
        kb.perms_menu(uid, current),
    )
    await cb.answer()


# ---------- تنظیمات (تایمر حذف خودکار + پاکسازی آرشیو) ----------
async def show_settings(target: Message, edit: bool = True):
    enabled = (await db.get_setting("delete_timer_enabled")) != "0"
    secs_raw = await db.get_setting("delete_timer_seconds")
    secs = int(secs_raw) if secs_raw and secs_raw.isdigit() else 30
    text = (
        "⏱ <b>تنظیمات</b>\n\n"
        "وقتی فایلی برای کاربر ارسال میشه، ربات یه پیام هشدار میفرسته و بعد از "
        "مدت مشخص‌شده، خودِ فایل‌های ارسالی رو از چت کاربر پاک می‌کنه "
        "(کاربر باید تا اون موقع سیوشون کنه)."
    )
    await show(target, text, kb.settings_menu(enabled, secs), edit)


@router.callback_query(F.data == "adm:settings")
async def settings_open(cb: CallbackQuery, state: FSMContext):
    if await need_perm_cb(cb, "settings"):
        return
    await state.clear()
    await show_settings(cb.message, edit=True)
    await cb.answer()


@router.callback_query(F.data == "set:toggle")
async def settings_toggle(cb: CallbackQuery):
    if await need_perm_cb(cb, "settings"):
        return
    enabled = (await db.get_setting("delete_timer_enabled")) != "0"
    await db.set_setting("delete_timer_enabled", "0" if enabled else "1")
    await show_settings(cb.message, edit=True)
    await cb.answer()


@router.callback_query(F.data == "set:seconds")
async def settings_seconds_ask(cb: CallbackQuery, state: FSMContext):
    if await need_perm_cb(cb, "settings"):
        return
    await state.set_state(St.set_seconds)
    await utils.safe_edit(
        cb.message,
        "⏱ چند ثانیه بعد از ارسال، فایل‌ها پاک بشن؟ یه عدد بفرست (مثلاً 30).\nبرای لغو: /cancel",
    )
    await cb.answer()


@router.message(StateFilter(St.set_seconds), F.text)
async def settings_seconds_receive(message: Message, state: FSMContext):
    if not access.has_perm(message.from_user.id, "settings"):
        await state.clear()
        return
    t = message.text.strip()
    if not t.isdigit() or int(t) <= 0:
        await message.reply("⚠️ فقط یه عدد صحیح بزرگتر از صفر بفرست.")
        return
    await db.set_setting("delete_timer_seconds", t)
    await state.clear()
    await message.answer(f"✅ مدت زمان روی {t} ثانیه تنظیم شد.")
    await show_settings(message, edit=False)


@router.callback_query(F.data == "own:clearconfirm", access.IsOwner())
async def clear_confirm(cb: CallbackQuery):
    await utils.safe_edit(
        cb.message,
        "⚠️ این کار همه‌ی لینک‌های آپلودشده‌ی قبلی رو از دیتابیس پاک می‌کنه و دیگه قابل بازیابی نیست.\n\n"
        "توجه: فایل‌های اصلی که قبلاً توی چت خودت با ربات فرستاده بودی، جای دیگه‌ای ذخیره نشدن و از اونجا حذف نمیشن؛ "
        "فقط لینک‌های تحویل و رکورد دیتابیس پاک میشه.\n\nادامه بدم؟",
        kb.clear_confirm(),
    )
    await cb.answer()


@router.callback_query(F.data == "own:clear", access.IsOwner())
async def clear_run(cb: CallbackQuery):
    await db.clear_old_files()
    await utils.safe_edit(cb.message, "✅ آرشیو قدیمی پاک شد.", kb.back())
    await cb.answer("پاک شد")


@router.callback_query(F.data.startswith("own:"))  # ادمین معمولی روی دکمه‌های مالک بزنه
async def own_locked(cb: CallbackQuery):
    await cb.answer("🔒 فقط مالک ربات به این بخش دسترسی داره.", show_alert=True)
