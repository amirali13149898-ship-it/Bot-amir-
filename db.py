import secrets
import time

import asyncpg

pool: asyncpg.Pool | None = None

SCHEMA = """
create table if not exists users (
    user_id bigint primary key,
    username text,
    first_name text,
    joined_at timestamptz not null default now(),
    is_blocked boolean not null default false
);
create table if not exists admins (
    user_id bigint primary key,
    added_by bigint,
    perms text[] not null default '{}',
    added_at timestamptz not null default now()
);
alter table admins add column if not exists perms text[] not null default '{}';
create table if not exists settings (
    key text primary key,
    value text
);
create table if not exists channels (
    chat_id bigint primary key,
    title text,
    username text,
    invite_link text,
    added_at timestamptz not null default now()
);
create table if not exists batches (
    id bigserial primary key,
    code text unique not null,
    created_by bigint,
    is_ready boolean not null default false,
    created_at timestamptz not null default now()
);
create table if not exists files (
    id bigserial primary key,
    batch_id bigint not null references batches(id) on delete cascade,
    file_id text not null,
    file_type text not null,
    sort_key bigint not null
);
create index if not exists idx_files_batch on files(batch_id);
create table if not exists downloads (
    id bigserial primary key,
    batch_id bigint references batches(id) on delete cascade,
    user_id bigint not null,
    created_at timestamptz not null default now()
);
create index if not exists idx_downloads_created on downloads(created_at);
alter table users add column if not exists last_name text;
alter table users add column if not exists is_banned boolean not null default false;
alter table users add column if not exists ban_text text;
alter table users add column if not exists banned_at timestamptz;

-- امنیت: جلوگیری از دسترسی از طریق API عمومی سوپابیس (کلید anon). اتصال مستقیم ربات (کاربر postgres) از RLS رد میشه.
alter table users enable row level security;
alter table admins enable row level security;
alter table settings enable row level security;
alter table channels enable row level security;
alter table batches enable row level security;
alter table files enable row level security;
alter table downloads enable row level security;
"""


ALL_PERMS = ["stats", "users", "upload", "channels", "caption", "broadcast", "pin", "settings"]


async def init(dsn: str):
    global pool
    # statement_cache_size=0 برای pooler سوپابیس (pgbouncer) لازمه
    pool = await asyncpg.create_pool(
        dsn, min_size=2, max_size=5, statement_cache_size=0
    )
    async with pool.acquire() as conn:
        await conn.execute(SCHEMA)


async def close():
    if pool:
        await pool.close()


# ---------- users ----------
async def add_user(u):
    await pool.execute(
        """insert into users(user_id, username, first_name, last_name) values($1,$2,$3,$4)
           on conflict (user_id) do update
           set username = excluded.username,
               first_name = excluded.first_name,
               last_name = excluded.last_name,
               is_blocked = false""",
        u.id, u.username, u.first_name, u.last_name,
    )


async def all_user_ids() -> list[int]:
    rows = await pool.fetch("select user_id from users where not is_blocked and not is_banned")
    return [r["user_id"] for r in rows]


async def mark_blocked(user_id: int):
    await pool.execute("update users set is_blocked = true where user_id = $1", user_id)


async def count_users() -> int:
    return await pool.fetchval("select count(*) from users")


async def list_users(limit: int, offset: int):
    return await pool.fetch(
        "select * from users order by joined_at desc, user_id desc limit $1 offset $2",
        limit, offset,
    )


async def get_user(user_id: int):
    return await pool.fetchrow("select * from users where user_id = $1", user_id)


async def list_banned_ids() -> set[int]:
    rows = await pool.fetch("select user_id from users where is_banned")
    return {r["user_id"] for r in rows}


async def get_ban_text(user_id: int) -> str | None:
    return await pool.fetchval("select ban_text from users where user_id = $1", user_id)


async def set_ban(user_id: int, banned: bool, text: str | None = None):
    await pool.execute(
        """update users set is_banned = $2, ban_text = $3,
           banned_at = case when $2 then now() else null end
           where user_id = $1""",
        user_id, banned, text if banned else None,
    )


# ---------- admins ----------
async def list_admin_ids() -> set[int]:
    rows = await pool.fetch("select user_id from admins")
    return {r["user_id"] for r in rows}


async def list_admins():
    return await pool.fetch(
        """select a.user_id, a.perms, u.first_name, u.username
           from admins a left join users u on u.user_id = a.user_id
           order by a.added_at"""
    )


async def add_admin(user_id: int, added_by: int, perms: list[str] | None = None):
    if perms is None:
        perms = []  # کمترین دسترسی؛ مالک خودش از منوی دسترسی‌ها روشن می‌کنه
    await pool.execute(
        "insert into admins(user_id, added_by, perms) values($1,$2,$3) on conflict do nothing",
        user_id, added_by, perms,
    )


async def get_admin_perms(user_id: int) -> set[str]:
    row = await pool.fetchrow("select perms from admins where user_id = $1", user_id)
    return set(row["perms"]) if row else set()


async def set_admin_perms(user_id: int, perms: set[str]):
    await pool.execute("update admins set perms = $1 where user_id = $2", list(perms), user_id)


async def del_admin(user_id: int):
    await pool.execute("delete from admins where user_id = $1", user_id)


async def find_user_by_username(username: str) -> int | None:
    return await pool.fetchval(
        "select user_id from users where lower(username) = lower($1)", username
    )


# ---------- settings ----------
_CACHE_TTL = 60.0
_settings_cache: dict[str, tuple[float, str | None]] = {}


async def get_setting(key: str) -> str | None:
    hit = _settings_cache.get(key)
    if hit and time.monotonic() - hit[0] < _CACHE_TTL:
        return hit[1]
    val = await pool.fetchval("select value from settings where key = $1", key)
    _settings_cache[key] = (time.monotonic(), val)
    return val


async def set_setting(key: str, value: str):
    await pool.execute(
        """insert into settings(key, value) values($1,$2)
           on conflict (key) do update set value = excluded.value""",
        key, value,
    )
    _settings_cache.pop(key, None)


async def del_setting(key: str):
    await pool.execute("delete from settings where key = $1", key)
    _settings_cache.pop(key, None)


# ---------- channels ----------
_channels_cache: tuple[float, list] | None = None


async def list_channels():
    global _channels_cache
    if _channels_cache and time.monotonic() - _channels_cache[0] < _CACHE_TTL:
        return _channels_cache[1]
    rows = await pool.fetch("select * from channels order by added_at")
    _channels_cache = (time.monotonic(), rows)
    return rows


def _drop_channels_cache():
    global _channels_cache
    _channels_cache = None


async def add_channel(chat_id: int, title: str, username: str | None, link: str):
    await pool.execute(
        """insert into channels(chat_id, title, username, invite_link) values($1,$2,$3,$4)
           on conflict (chat_id) do update
           set title = excluded.title, username = excluded.username,
               invite_link = excluded.invite_link""",
        chat_id, title, username, link,
    )
    _drop_channels_cache()


async def del_channel(chat_id: int):
    await pool.execute("delete from channels where chat_id = $1", chat_id)
    _drop_channels_cache()


# ---------- batches / files ----------
async def create_batch(admin_id: int) -> tuple[int, str]:
    code = secrets.token_urlsafe(12)  # ~96 بیت؛ قابل حدس زدن نیست
    batch_id = await pool.fetchval(
        "insert into batches(code, created_by) values($1,$2) returning id",
        code, admin_id,
    )
    return batch_id, code


async def add_file(batch_id: int, file_id: str, file_type: str, sort_key: int):
    await pool.execute(
        "insert into files(batch_id, file_id, file_type, sort_key) values($1,$2,$3,$4)",
        batch_id, file_id, file_type, sort_key,
    )


async def finish_batch(batch_id: int) -> int:
    n = await pool.fetchval("select count(*) from files where batch_id = $1", batch_id)
    if n:
        await pool.execute("update batches set is_ready = true where id = $1", batch_id)
    return n


async def delete_batch(batch_id: int):
    await pool.execute("delete from batches where id = $1", batch_id)


async def get_batch(code: str):
    return await pool.fetchrow(
        "select * from batches where code = $1 and is_ready", code
    )


async def get_files(batch_id: int):
    return await pool.fetch(
        "select * from files where batch_id = $1 order by sort_key, id", batch_id
    )


async def log_download(batch_id: int, user_id: int):
    await pool.execute(
        "insert into downloads(batch_id, user_id) values($1,$2)", batch_id, user_id
    )


# ---------- پاکسازی آرشیو ----------
async def clear_old_files():
    await pool.execute("truncate table files, batches restart identity cascade")


# ---------- stats ----------
async def stats() -> dict:
    users = await pool.fetchrow(
        "select count(*) as total, count(*) filter (where is_blocked) as blocked from users"
    )
    dl = await pool.fetchrow(
        """select
             count(*) filter (where created_at >= now() - interval '12 hours') as h12,
             count(*) filter (where created_at >= now() - interval '1 day')    as d1,
             count(*) filter (where created_at >= now() - interval '7 days')   as w1,
             count(*) filter (where created_at >= now() - interval '30 days')  as m1,
             count(*) as total
           from downloads"""
    )
    batches = await pool.fetchval("select count(*) from batches where is_ready")
    return {"users": users, "dl": dl, "batches": batches}
