from aiogram.types import InlineKeyboardButton as B
from aiogram.types import InlineKeyboardMarkup as M


def admin_panel() -> M:
    return M(inline_keyboard=[
        [B(text="📊 آمار ربات", callback_data="adm:stats")],
        [B(text="📥 آپلود گروهی", callback_data="adm:upload"),
         B(text="🔒 جوین اجباری", callback_data="adm:channels")],
        [B(text="🖊 کپشن پیشفرض", callback_data="adm:caption")],
        [B(text="📨 ارسال همگانی", callback_data="adm:broadcast"),
         B(text="📌 سنجاق پیام", callback_data="adm:pin")],
    ])


def back() -> M:
    return M(inline_keyboard=[[B(text="🔙 بازگشت", callback_data="adm:home")]])


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
