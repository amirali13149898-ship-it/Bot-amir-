"""دسترسی‌ها: مالک‌ها (از ADMIN_IDS توی env) و ادمین‌هایی که مالک از داخل ربات اضافه می‌کنه.
هر ادمین یه مجموعه دسترسی (perm) جدا داره؛ مالک همیشه به همه چیز دسترسی داره."""
import logging

from aiogram import BaseMiddleware
from aiogram.filters import Filter
from aiogram.types import TelegramObject, Update

import config
import db

OWNER_IDS: set[int] = set(config.ADMIN_IDS)
ALL_PERMS = db.ALL_PERMS

_admins: set[int] = set()          # ادمین‌های دیتابیس (کش)
_perms: dict[int, set[str]] = {}   # دسترسی هر ادمین (کش)
_banned: set[int] = set()          # کاربرهای بن‌شده (کش)


async def reload():
    global _admins, _perms, _banned
    _banned = await db.list_banned_ids()
    rows = await db.list_admins()
    _admins = {r["user_id"] for r in rows}
    _perms = {r["user_id"]: set(r["perms"] or []) for r in rows}


def is_owner(user_id: int) -> bool:
    return user_id in OWNER_IDS


def is_admin(user_id: int) -> bool:
    return user_id in OWNER_IDS or user_id in _admins


def perms_of(user_id: int) -> set[str]:
    if is_owner(user_id):
        return set(ALL_PERMS)
    return set(_perms.get(user_id, set()))


def has_perm(user_id: int, perm: str) -> bool:
    return is_owner(user_id) or perm in _perms.get(user_id, set())


class IsAdmin(Filter):
    async def __call__(self, event: TelegramObject) -> bool:
        u = getattr(event, "from_user", None)
        return bool(u) and is_admin(u.id)


class IsOwner(Filter):
    async def __call__(self, event: TelegramObject) -> bool:
        u = getattr(event, "from_user", None)
        return bool(u) and is_owner(u.id)


class HasPerm(Filter):
    def __init__(self, perm: str):
        self.perm = perm

    async def __call__(self, event: TelegramObject) -> bool:
        u = getattr(event, "from_user", None)
        return bool(u) and has_perm(u.id, self.perm)


# ---------- بن ----------
def is_banned(user_id: int) -> bool:
    return user_id in _banned and not is_admin(user_id)


async def ban(user_id: int, text: str | None):
    await db.set_ban(user_id, True, text)
    _banned.add(user_id)


async def unban(user_id: int):
    await db.set_ban(user_id, False)
    _banned.discard(user_id)


class BanMiddleware(BaseMiddleware):
    """هر آپدیتی که از کاربر بن‌شده بیاد قبل از رسیدن به هندلرها متوقف میشه."""

    async def __call__(self, handler, event: Update, data: dict):
        u = data.get("event_from_user")
        if u and is_banned(u.id):
            bot = data["bot"]
            try:
                if event.callback_query:
                    await bot.answer_callback_query(
                        event.callback_query.id,
                        "🚫 شما از استفاده از این ربات محروم شده‌اید.",
                        show_alert=True,
                    )
                elif event.message and event.message.chat.type == "private":
                    msg = "🚫 شما از استفاده از این ربات محروم شده‌اید."
                    extra = await db.get_ban_text(u.id)
                    if extra:
                        msg += "\n\n" + extra
                    await bot.send_message(event.message.chat.id, msg)
            except Exception:
                logging.debug("ban notice failed", exc_info=True)
            return None
        return await handler(event, data)
