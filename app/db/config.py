import os
import sqlite3
from pathlib import Path

import aiomysql
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

BASE_DIR = Path(__file__).resolve().parents[2]
DB_PATH = Path(os.getenv("DATABASE_PATH", str(BASE_DIR / "data" / "app.db")))
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

def is_mysql_enabled() -> bool:
    required = ("MYSQL_HOST", "MYSQL_PORT", "MYSQL_USER", "MYSQL_DATABASE")
    return all(
        os.getenv(key) is not None and str(os.getenv(key)).strip() != ""
        for key in required
    )


def get_sqlite_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_db_value():
    return os.getenv("MYSQL_" + "CRED", "")


async def get_connection():
    if is_mysql_enabled():
        conn_args = {
            "host": os.getenv("MYSQL_HOST"),
            "port": int(os.getenv("MYSQL_PORT")),
            "user": os.getenv("MYSQL_USER"),
            "db": os.getenv("MYSQL_DATABASE"),
            "autocommit": True,
            "charset": "utf8mb4",
        }
        conn_args["password"] = get_db_value()
        return await aiomysql.connect(**conn_args)
    return get_sqlite_connection()


async def fetch_one(sql: str, params=()):
    if is_mysql_enabled():
        conn = await get_connection()
        try:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(sql, params)
                return await cursor.fetchone()
        finally:
            conn.close()

    conn = get_sqlite_connection()
    try:
        row = conn.execute(sql, params).fetchone()
        return dict(row) if row is not None else None
    finally:
        conn.close()


async def fetch_all(sql: str, params=()):
    if is_mysql_enabled():
        conn = await get_connection()
        try:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(sql, params)
                return await cursor.fetchall()
        finally:
            conn.close()

    conn = get_sqlite_connection()
    try:
        rows = conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


async def execute_write(sql: str, params=()):
    if is_mysql_enabled():
        conn = await get_connection()
        try:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(sql, params)
                return cursor.lastrowid
        finally:
            conn.close()

    conn = get_sqlite_connection()
    try:
        cur = conn.execute(sql, params)
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


async def execute_update(sql: str, params=()):
    if is_mysql_enabled():
        conn = await get_connection()
        try:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(sql, params)
        finally:
            conn.close()
        return

    conn = get_sqlite_connection()
    try:
        conn.execute(sql, params)
        conn.commit()
    finally:
        conn.close()


async def ensure_mysql_views():
    if not is_mysql_enabled():
        return

    conn = await aiomysql.connect(
        host=os.getenv("MYSQL_HOST"),
        port=int(os.getenv("MYSQL_PORT")),
        user=os.getenv("MYSQL_USER"),
        password=get_db_value(),
        db=os.getenv("MYSQL_DATABASE"),
        autocommit=True,
        charset="utf8mb4",
    )
    try:
        async with conn.cursor() as cursor:
            view_sql = [
                    """CREATE OR REPLACE VIEW `groups` AS
                    SELECT id,
                           creador_id AS creator_id,
                           titulo AS title,
                           descripcion AS description,
                           objetivo AS objective,
                           fecha_creacion AS created_at
                    FROM `grupos`;""",
                    """CREATE OR REPLACE VIEW `group_members` AS
                    SELECT id,
                           grupo_id AS group_id,
                           usuario_id AS user_id,
                           CASE rol WHEN 'propietario' THEN 'owner' WHEN 'miembro' THEN 'member' ELSE rol END AS role,
                           porcentaje_participacion AS participation_percentage,
                           fecha_union AS joined_at
                    FROM `miembros_grupo`;""",
                    """CREATE OR REPLACE VIEW `group_invitations` AS
                    SELECT id,
                           grupo_id AS group_id,
                           remitente_id AS sender_id,
                           destinatario_id AS recipient_id,
                           CASE estado WHEN 'pendiente' THEN 'pending' WHEN 'aceptada' THEN 'accepted' WHEN 'rechazada' THEN 'rejected' WHEN 'cancelada' THEN 'cancelled' ELSE estado END AS status,
                           fecha_creacion AS created_at,
                           fecha_respuesta AS responded_at
                    FROM `invitaciones_grupo`;""",
                    """CREATE OR REPLACE VIEW `expenses` AS
                    SELECT id,
                           grupo_id AS group_id,
                           creado_por_id AS created_by_id,
                           pagado_por_id AS paid_by_id,
                           titulo AS title,
                           descripcion AS description,
                           cantidad AS amount,
                           categoria AS category,
                           fecha_gasto AS expense_date,
                           fecha_creacion AS created_at
                    FROM `gastos`;""",
                    """CREATE OR REPLACE VIEW `expense_shares` AS
                    SELECT id,
                           gasto_id AS expense_id,
                           usuario_id AS user_id,
                           porcentaje_participacion AS percentage,
                           cantidad_deuda AS amount_due
                    FROM `desglose_gastos`;""",
                    """CREATE OR REPLACE VIEW `messages` AS
                    SELECT id,
                           grupo_id AS group_id,
                           remitente_id AS sender_id,
                           contenido AS content,
                           fecha_envio AS sent_at
                    FROM `mensajes_grupo`;""",
                    """CREATE OR REPLACE VIEW `payments` AS
                    SELECT id,
                           grupo_id AS group_id,
                           pagador_id AS payer_id,
                           receptor_id AS receiver_id,
                           cantidad AS amount,
                           fecha_pago AS paid_at,
                           descripcion AS description
                    FROM `pagos`;""",
            ]
            for sql in view_sql:
                await cursor.execute(sql)
    finally:
        conn.close()


async def init_db():
    if is_mysql_enabled():
        await ensure_mysql_views()
        return

    schema_sql = """
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        email TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        full_name TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS groups (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        creator_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        description TEXT NOT NULL,
        objective TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (creator_id) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS group_members (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        group_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        role TEXT NOT NULL DEFAULT 'member' CHECK(role IN ('owner','member')),
        participation_percentage REAL NOT NULL DEFAULT 0.0,
        joined_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(group_id, user_id),
        FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE CASCADE,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS group_invitations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        group_id INTEGER NOT NULL,
        sender_id INTEGER NOT NULL,
        recipient_id INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','accepted','rejected','cancelled')),
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        responded_at TEXT,
        UNIQUE(group_id, recipient_id),
        FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE CASCADE,
        FOREIGN KEY (sender_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY (recipient_id) REFERENCES users(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS expenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        group_id INTEGER NOT NULL,
        created_by_id INTEGER NOT NULL,
        paid_by_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        description TEXT,
        amount REAL NOT NULL CHECK(amount > 0),
        category TEXT,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        expense_date TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE CASCADE,
        FOREIGN KEY (created_by_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY (paid_by_id) REFERENCES users(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS expense_shares (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        expense_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        percentage REAL NOT NULL DEFAULT 0.0,
        amount_due REAL NOT NULL DEFAULT 0.0,
        UNIQUE(expense_id, user_id),
        FOREIGN KEY (expense_id) REFERENCES expenses(id) ON DELETE CASCADE,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        group_id INTEGER NOT NULL,
        sender_id INTEGER NOT NULL,
        content TEXT NOT NULL,
        sent_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE CASCADE,
        FOREIGN KEY (sender_id) REFERENCES users(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        group_id INTEGER NOT NULL,
        payer_id INTEGER NOT NULL,
        receiver_id INTEGER NOT NULL,
        amount REAL NOT NULL CHECK(amount > 0),
        paid_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        description TEXT,
        FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE CASCADE,
        FOREIGN KEY (payer_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY (receiver_id) REFERENCES users(id) ON DELETE CASCADE
    );
    """
    conn = get_sqlite_connection()
    try:
        conn.executescript(schema_sql)
        conn.commit()
    finally:
        conn.close()
