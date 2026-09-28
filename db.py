import secrets

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
"""


async def init(dsn: str):
    global pool
    # statement_cache_size=0 برای pooler سوپابیس (pgbouncer) لازمه
    pool = await asyncpg.create_pool(
        dsn, min_size=1, max_size=5, statement_cache_size=0
    )
    async with pool.acquire() as conn:
        await conn.execute(SCHEMA)


async def close():
    if pool:
        await pool.close()


# ---------- users ----------
async def add_user(u):
    await pool.execute(
        """insert into users(user_id, username, first_name) values($1,$2,$3)
           on conflict (user_id) do update
           set username = excluded.username,
               first_name = excluded.first_name,
               is_blocked = false""",
        u.id, u.username, u.first_name,
    )


async def all_user_ids() -> list[int]:
    rows = await pool.fetch("select user_id from users where not is_blocked")
    return [r["user_id"] for r in rows]


async def mark_blocked(user_id: int):
    await pool.execute("update users set is_blocked = true where user_id = $1", user_id)


# ---------- settings ----------
async def get_setting(key: str) -> str | None:
    return await pool.fetchval("select value from settings where key = $1", key)


async def set_setting(key: str, value: str):
    await pool.execute(
        """insert into settings(key, value) values($1,$2)
           on conflict (key) do update set value = excluded.value""",
        key, value,
    )


async def del_setting(key: str):
    await pool.execute("delete from settings where key = $1", key)


# ---------- channels ----------
async def list_channels():
    return await pool.fetch("select * from channels order by added_at")


async def add_channel(chat_id: int, title: str, username: str | None, link: str):
    await pool.execute(
        """insert into channels(chat_id, title, username, invite_link) values($1,$2,$3,$4)
           on conflict (chat_id) do update
           set title = excluded.title, username = excluded.username,
               invite_link = excluded.invite_link""",
        chat_id, title, username, link,
    )


async def del_channel(chat_id: int):
    await pool.execute("delete from channels where chat_id = $1", chat_id)


# ---------- batches / files ----------
async def create_batch(admin_id: int) -> tuple[int, str]:
    code = secrets.token_urlsafe(6)
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
