import os
import sqlite3
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "ecoscan.db")

SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS scans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    material_code TEXT NOT NULL,
    object_name TEXT NOT NULL,
    confidence REAL NOT NULL,
    separated_well INTEGER NOT NULL,
    points INTEGER NOT NULL,
    weight_kg REAL NOT NULL,
    co2_kg REAL NOT NULL,
    created_at TEXT NOT NULL,
    photo BLOB,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_scans_user ON scans(user_id, created_at);
"""

POSTGRES_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS users (
        id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        name text NOT NULL,
        email text NOT NULL UNIQUE,
        password_hash text NOT NULL,
        created_at timestamptz NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS scans (
        id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        user_id bigint NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        material_code text NOT NULL,
        object_name text NOT NULL,
        confidence double precision NOT NULL,
        separated_well boolean NOT NULL DEFAULT true,
        points integer NOT NULL DEFAULT 10,
        weight_kg double precision NOT NULL DEFAULT 0,
        co2_kg double precision NOT NULL DEFAULT 0,
        created_at timestamptz NOT NULL DEFAULT now(),
        photo bytea
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_scans_user ON scans (user_id, created_at DESC)",
    "ALTER TABLE scans ADD COLUMN IF NOT EXISTS photo bytea",
]


class Database:
    def __init__(self, raw, postgres: bool) -> None:
        self.raw = raw
        self.postgres = postgres

    def execute(self, sql: str, params: tuple = ()):
        sql = sql.replace("?", "%s") if self.postgres else sql
        if self.postgres:
            cursor = self.raw.cursor()
            cursor.execute(sql, params)
            return cursor
        return self.raw.execute(sql, params)

    def executemany(self, sql: str, rows: list[tuple]) -> None:
        sql = sql.replace("?", "%s") if self.postgres else sql
        if self.postgres:
            with self.raw.cursor() as cursor:
                cursor.executemany(sql, rows)
            return
        self.raw.executemany(sql, rows)

    def commit(self) -> None:
        self.raw.commit()

    def close(self) -> None:
        self.raw.close()


def database_url() -> str:
    return os.environ.get("DATABASE_URL", "").strip()


def get_conn() -> Database:
    url = database_url()
    if url:
        import psycopg
        from psycopg.rows import dict_row

        raw = psycopg.connect(with_ssl(url), row_factory=dict_row)
        return Database(raw, postgres=True)
    os.makedirs(DATA_DIR, exist_ok=True)
    raw = sqlite3.connect(DB_PATH)
    raw.row_factory = sqlite3.Row
    return Database(raw, postgres=False)


def init_db() -> bool:
    try:
        conn = get_conn()
    except Exception as exc:
        print(f"Base de datos no disponible: {exc}")
        return False
    try:
        if conn.postgres:
            for statement in POSTGRES_STATEMENTS:
                conn.execute(statement)
        else:
            conn.raw.executescript(SQLITE_SCHEMA)
            columns = {row[1] for row in conn.raw.execute("PRAGMA table_info(scans)").fetchall()}
            if "photo" not in columns:
                conn.execute("ALTER TABLE scans ADD COLUMN photo BLOB")
        conn.commit()
    finally:
        conn.close()
    return True


def with_ssl(url: str) -> str:
    parsed = urlparse(url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query.setdefault("sslmode", "require")
    return urlunparse(parsed._replace(query=urlencode(query)))
