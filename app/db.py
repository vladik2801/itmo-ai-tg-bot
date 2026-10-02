import asyncpg
from pathlib import Path
from app.config import Settings


async def create_pool(settings: Settings) -> asyncpg.Pool:
    # Небольшого пула достаточно для учебной ВМ. Таблицы добавляют студенты.
    pool = await asyncpg.create_pool(
        host=settings.postgres_host,
        port=settings.postgres_port,
        database=settings.postgres_db,
        user=settings.postgres_user,
        password=settings.postgres_password,
        min_size=1,
        max_size=5,
        timeout=5,
        command_timeout=5,
    )
    try:
        await pool.fetchval("SELECT 1", timeout=3)
    except BaseException:
        await pool.close()
        raise
    return pool

async def initialize_bd(pool : asyncpg.Pool) -> None:
    path = Path(__file__).with_name("init.sql")
    sql = path.read_text(encoding="utf-8")
    async with pool.acquire() as connection:
        async with connection.transaction():
            await connection.execute(sql)