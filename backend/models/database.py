import os
import aiosqlite

DB_PATH = os.path.join("..", "projects", "conduit.db")

async def get_db() -> aiosqlite.Connection:
    """Return an async aiosqlite connection with WAL mode enabled."""
    # check_same_thread=False is required because aiosqlite manages its own
    # thread pool internally. Each call creates a new connection, and SQLite
    # WAL mode handles concurrency safely.
    conn = await aiosqlite.connect(DB_PATH, check_same_thread=False)
    await conn.execute("PRAGMA journal_mode=WAL")
    return conn

async def apply_migrations(conn: aiosqlite.Connection) -> None:
    """Check current schema version and apply any pending migrations."""
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER PRIMARY KEY,
            applied_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            uuid TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            state TEXT NOT NULL DEFAULT 'created',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            voiceover_path TEXT,
            script_path TEXT
        );
    """)

    await conn.execute("""
        INSERT OR IGNORE INTO schema_version (version) VALUES (1);
    """)

    await conn.commit()

async def init_db() -> None:
    """Create the projects directory and apply database migrations."""
    db_dir = os.path.dirname(DB_PATH)
    os.makedirs(db_dir, exist_ok=True)

    conn = await get_db()
    try:
        await apply_migrations(conn)
    finally:
        await conn.close()
