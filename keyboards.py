from aiogram.types import InlineKeyboardButton as B
from aiogram.types import InlineKeyboardMarkup as M
from aiogram.types import KeyboardButton as KB
from aiogram.types import ReplyKeyboardMarkup as RM

# ---------- کیبورد پایین صفحه (Reply Keyboard) ----------
BTN_STATS = "📊 آمار ربات"
BTN_UPLOAD = "📥 آپلود گروهی"
BTN_CHANNELS = "🔒 جوین اجباری"
BTN_CAPTION = "🖊 کپشن پیشفرض"
BTN_BROADCAST = "📨 ارسال همگانی"
BTN_PIN = "📌 سنجاق پیام"
BTN_ADMINS = "👑 مدیریت ادمین‌ها"  # فقط مالک


def admin_reply(is_owner: bool) -> RM:
    rows = [
        [KB(text=BTN_STATS)],
        [KB(text=BTN_UPLOAD), KB(text=BTN_CHANNELS)],
        [KB(text=BTN_CAPTION)],
        [KB(text=BTN_BROADCAST), KB(text=BTN_PIN)],
    ]
    if is_owner:
        rows.append([KB(text=BTN_ADMINS)])
    return RM(keyboard=rows, resize_keyboard=True, is_persistent=True)


# ---------- پنل شیشه‌ای (Inline) ----------
def admin_panel(is_owner: bool = False) -> M:
    rows = [
        [B(text="📊 آمار ربات", callback_data="adm:stats")],
        [B(text="📥 آپلود گروهی", callback_data="adm:upload"),
         B(text="🔒 جوین اجباری", callback_data="adm:channels")],
        [B(text="🖊 کپشن پیشفرض", callback_data="adm:caption")],
        [B(text="📨 ارسال همگانی", callback_data="adm:broadcast"),
         B(text="📌 سنجاق پیام", callback_data="adm:pin")],
    ]
    if is_owner:
        rows.append([B(text="👑 مدیریت ادمین‌ها", callback_data="own:admins")])
    return M(inline_keyboard=rows)


def back() -> M:
    return M(inline_keyboard=[[B(text="🔙 بازگشت", callback_data="adm:home")]])


def admins_menu(admins) -> M:
    rows = []
    for a in admins:
        name = a["first_name"] or (f"@{a['username']}" if a["username"] else str(a["user_id"]))
        rows.append([B(text=f"❌ {name} ({a['user_id']})", callback_data=f"own:del:{a['user_id']}")])
    rows.append([B(text="➕ افزودن ادمین", callback_data="own:add")])
    rows.append([B(text="🔙 بازگشت", callback_data="adm:home")])
    return M(inline_keyboard=rows)


def upload_controls() -> M:
    return M(inline_keyboard=[
        [B(text="✅ پایان و ساخت لینک", callback_data="adm:upload_done")],
        [B(text="❌ لغو", callback_data="adm:upload_cancel")],
    ])


def channels_menu(channels) -> M:
    rows = [
        [B(text=f"❌ {c['title']}", callback_data=f"adm:chdel:{c['chat_id']}")]
        for c in channels
    ]
    rows.append([B(text="➕ افزودن کانال", callback_data="adm:chadd")])
    rows.append([B(text="🔙 بازگشت", callback_data="adm:home")])
    return M(inline_keyboard=rows)


def caption_menu(has_caption: bool) -> M:
    rows = [[B(text="✏️ تغییر کپشن", callback_data="adm:capset")]]
    if has_caption:
        rows.append([B(text="🗑 حذف کپشن", callback_data="adm:capdel")])
    rows.append([B(text="🔙 بازگشت", callback_data="adm:home")])
    return M(inline_keyboard=rows)


def join_kb(channels, code: str) -> M:
    rows = [[B(text=f"📢 {c['title']}", url=c["invite_link"])] for c in channels]
    rows.append([B(text="✅ عضو شدم", callback_data=f"chk:{code}")])
    return M(inline_keyboard=rows)
