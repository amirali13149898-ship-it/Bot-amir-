"""دسترسی‌ها: مالک‌ها (از ADMIN_IDS توی env) و ادمین‌هایی که مالک از داخل ربات اضافه می‌کنه.
هر ادمین یه مجموعه دسترسی (perm) جدا داره؛ مالک همیشه به همه چیز دسترسی داره."""
from aiogram.filters import Filter
from aiogram.types import TelegramObject

import config
import db

OWNER_IDS: set[int] = set(config.ADMIN_IDS)
ALL_PERMS = db.ALL_PERMS

_admins: set[int] = set()          # ادمین‌های دیتابیس (کش)
_perms: dict[int, set[str]] = {}   # دسترسی هر ادمین (کش)


async def reload():
    global _admins, _perms
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
