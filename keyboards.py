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
BTN_SETTINGS = "⏱ تنظیمات"
BTN_ADMINS = "👑 مدیریت ادمین‌ها"  # فقط مالک

PERM_LABELS = {
    "stats": ("📊 آمار", BTN_STATS),
    "upload": ("📥 آپلود گروهی", BTN_UPLOAD),
    "channels": ("🔒 جوین اجباری", BTN_CHANNELS),
    "caption": ("🖊 کپشن پیشفرض", BTN_CAPTION),
    "broadcast": ("📨 ارسال همگانی", BTN_BROADCAST),
    "pin": ("📌 سنجاق پیام", BTN_PIN),
    "settings": ("⏱ تنظیمات", BTN_SETTINGS),
}


def admin_reply(perms: set[str], is_owner: bool) -> RM:
    rows = []
    if "stats" in perms:
        rows.append([KB(text=BTN_STATS)])
    row = [KB(text=BTN_UPLOAD)] if "upload" in perms else []
    if "channels" in perms:
        row.append(KB(text=BTN_CHANNELS))
    if row:
        rows.append(row)
    if "caption" in perms:
        rows.append([KB(text=BTN_CAPTION)])
    row = [KB(text=BTN_BROADCAST)] if "broadcast" in perms else []
    if "pin" in perms:
        row.append(KB(text=BTN_PIN))
    if row:
        rows.append(row)
    if "settings" in perms:
        rows.append([KB(text=BTN_SETTINGS)])
    if is_owner:
        rows.append([KB(text=BTN_ADMINS)])
    if not rows:
        rows = [[KB(text="ℹ️ فعلاً دسترسی‌ای نداری")]]
    return RM(keyboard=rows, resize_keyboard=True, is_persistent=True)


# ---------- پنل شیشه‌ای (Inline) ----------
def admin_panel(perms: set[str], is_owner: bool = False) -> M:
    rows = []
    if "stats" in perms:
        rows.append([B(text="📊 آمار ربات", callback_data="adm:stats")])
    row = []
    if "upload" in perms:
        row.append(B(text="📥 آپلود گروهی", callback_data="adm:upload"))
    if "channels" in perms:
        row.append(B(text="🔒 جوین اجباری", callback_data="adm:channels"))
    if row:
        rows.append(row)
    if "caption" in perms:
        rows.append([B(text="🖊 کپشن پیشفرض", callback_data="adm:caption")])
    row = []
    if "broadcast" in perms:
        row.append(B(text="📨 ارسال همگانی", callback_data="adm:broadcast"))
    if "pin" in perms:
        row.append(B(text="📌 سنجاق پیام", callback_data="adm:pin"))
    if row:
        rows.append(row)
    if "settings" in perms:
        rows.append([B(text="⏱ تنظیمات", callback_data="adm:settings")])
    if is_owner:
        rows.append([B(text="👑 مدیریت ادمین‌ها", callback_data="own:admins")])
    return M(inline_keyboard=rows)


def back() -> M:
    return M(inline_keyboard=[[B(text="🔙 بازگشت", callback_data="adm:home")]])


def locked() -> M:
    return M(inline_keyboard=[[B(text="🔙 بازگشت", callback_data="adm:home")]])


def admins_menu(admins) -> M:
    rows = []
    for a in admins:
        name = a["first_name"] or (f"@{a['username']}" if a["username"] else str(a["user_id"]))
        rows.append([
            B(text=f"⚙️ {name}", callback_data=f"own:perm:{a['user_id']}"),
            B(text="❌ حذف", callback_data=f"own:del:{a['user_id']}"),
        ])
    rows.append([B(text="➕ افزودن ادمین", callback_data="own:add")])
    rows.append([B(text="🔙 بازگشت", callback_data="adm:home")])
    return M(inline_keyboard=rows)


def perms_menu(uid: int, current: set[str]) -> M:
    rows = []
    for key, (label, _btn) in PERM_LABELS.items():
        mark = "✅" if key in current else "❌"
        rows.append([B(text=f"{mark} {label}", callback_data=f"own:permtg:{uid}:{key}")])
    rows.append([B(text="🔙 بازگشت", callback_data="own:admins")])
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


# ---------- تنظیمات (تایمر حذف خودکار) ----------
def settings_menu(enabled: bool, seconds: int) -> M:
    toggle_text = "✅ فعاله" if enabled else "❌ خاموشه"
    rows = [
        [B(text=f"تایمر حذف خودکار: {toggle_text}", callback_data="set:toggle")],
        [B(text=f"⏱ مدت زمان: {seconds} ثانیه (تغییر)", callback_data="set:seconds")],
        [B(text="🧹 پاکسازی آرشیو قدیمی", callback_data="own:clearconfirm")],
        [B(text="🔙 بازگشت", callback_data="adm:home")],
    ]
    return M(inline_keyboard=rows)


def clear_confirm() -> M:
    return M(inline_keyboard=[
        [B(text="⚠️ مطمئنم، همه‌شون رو پاک کن", callback_data="own:clear")],
        [B(text="🔙 انصراف", callback_data="adm:settings")],
    ])
