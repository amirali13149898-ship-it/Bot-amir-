"""دسترسی‌ها: مالک‌ها (از ADMIN_IDS توی env) و ادمین‌هایی که مالک از داخل ربات اضافه می‌کنه."""
from aiogram.filters import Filter
from aiogram.types import TelegramObject

import config
import db

OWNER_IDS: set[int] = set(config.ADMIN_IDS)
_admins: set[int] = set()  # ادمین‌های دیتابیس (کش)


async def reload():
    global _admins
    _admins = await db.list_admin_ids()


def is_owner(user_id: int) -> bool:
    return user_id in OWNER_IDS


def is_admin(user_id: int) -> bool:
    return user_id in OWNER_IDS or user_id in _admins


class IsAdmin(Filter):
    async def __call__(self, event: TelegramObject) -> bool:
        u = getattr(event, "from_user", None)
        return bool(u) and is_admin(u.id)


class IsOwner(Filter):
    async def __call__(self, event: TelegramObject) -> bool:
        u = getattr(event, "from_user", None)
        return bool(u) and is_owner(u.id)
