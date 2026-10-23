from fastapi import HTTPException, status

from app.core.security import create_token, hash_password, verify_password
from app.db.config import execute_write, fetch_one, get_sqlite_connection, is_mysql_enabled
from app.models.user_model import UserCreate, UserLogin


def _user_to_dict(row):
    if row is None:
        return None
    if isinstance(row, dict):
        return {
            "id": row["id"],
            "username": row["username"],
            "email": row["email"],
            "full_name": row["full_name"],
            "created_at": row["created_at"],
        }
    return {
        "id": row["id"],
        "username": row["username"],
        "email": row["email"],
        "full_name": row["full_name"],
        "created_at": row["created_at"],
    }


async def register(user: UserCreate):
    email = user.email.lower()
    username = user.username.lower()

    if is_mysql_enabled():
        existing = await fetch_one("SELECT id FROM users WHERE email = %s OR username = %s", (email, username))
        if existing:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El usuario o el correo ya existe")
        user_id = await execute_write(
            "INSERT INTO users (username, email, password_hash, full_name) VALUES (%s, %s, %s, %s)",
            (username, email, hash_password(user.password), user.full_name.strip()),
        )
        saved = await fetch_one("SELECT * FROM users WHERE id = %s", (user_id,))
        return {"message": "Usuario creado correctamente", "user": _user_to_dict(saved)}

    conn = get_sqlite_connection()
    try:
        existing = conn.execute(
            "SELECT id FROM users WHERE email = ? OR username = ?",
            (email, username),
        ).fetchone()
        if existing:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El usuario o el correo ya existe")

        user_id = conn.execute(
            "INSERT INTO users (username, email, password_hash, full_name) VALUES (?, ?, ?, ?)",
            (username, email, hash_password(user.password), user.full_name.strip()),
        ).lastrowid
        conn.commit()
        saved = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return {"message": "Usuario creado correctamente", "user": _user_to_dict(saved)}
    finally:
        conn.close()


async def login(user_login: UserLogin):
    if is_mysql_enabled():
        row = await fetch_one("SELECT * FROM users WHERE email = %s", (user_login.email.lower(),))
        if not row:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales incorrectas")
        if not verify_password(user_login.password, row["password_hash"]):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales incorrectas")
        token = create_token({"sub": str(row["id"]), "email": row["email"]})
        return {"access_token": token, "token_type": "bearer"}

    conn = get_sqlite_connection()
    try:
        row = conn.execute(
            "SELECT * FROM users WHERE email = ?",
            (user_login.email.lower(),),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales incorrectas")
        if not verify_password(user_login.password, row["password_hash"]):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales incorrectas")

        token = create_token({"sub": str(row["id"]), "email": row["email"]})
        return {"access_token": token, "token_type": "bearer"}
    finally:
        conn.close()


async def get_by_id(user_id: int):
    if is_mysql_enabled():
        row = await fetch_one("SELECT * FROM users WHERE id = %s", (user_id,))
        return _user_to_dict(row)

    conn = get_sqlite_connection()
    try:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return _user_to_dict(row)
    finally:
        conn.close()
