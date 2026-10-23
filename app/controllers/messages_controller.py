from fastapi import HTTPException, status

from app.db.config import execute_write, fetch_all, fetch_one, get_sqlite_connection, is_mysql_enabled


async def list_messages(group_id: int, user_id: int):
    if is_mysql_enabled():
        in_group = await fetch_one(
            "SELECT 1 FROM group_members WHERE group_id = %s AND user_id = %s",
            (group_id, user_id),
        )
        if not in_group:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tienes acceso a este grupo")
        rows = await fetch_all(
            """
            SELECT m.*, u.username
            FROM messages m
            JOIN users u ON u.id = m.sender_id
            WHERE m.group_id = %s
            ORDER BY m.sent_at ASC
            """,
            (group_id,),
        )
        return list(rows)

    conn = get_sqlite_connection()
    try:
        in_group = conn.execute(
            "SELECT 1 FROM group_members WHERE group_id = ? AND user_id = ?",
            (group_id, user_id),
        ).fetchone()
        if not in_group:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tienes acceso a este grupo")
        rows = conn.execute(
            """
            SELECT m.*, u.username
            FROM messages m
            JOIN users u ON u.id = m.sender_id
            WHERE m.group_id = ?
            ORDER BY m.sent_at ASC
            """,
            (group_id,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


async def send_message(group_id: int, user_id: int, content: str):
    if is_mysql_enabled():
        in_group = await fetch_one(
            "SELECT 1 FROM group_members WHERE group_id = %s AND user_id = %s",
            (group_id, user_id),
        )
        if not in_group:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tienes acceso a este grupo")
        message_id = await execute_write(
            "INSERT INTO messages (group_id, sender_id, content) VALUES (%s, %s, %s)",
            (group_id, user_id, content.strip()),
        )
        row = await fetch_one(
            "SELECT m.*, u.username FROM messages m JOIN users u ON u.id = m.sender_id WHERE m.id = %s",
            (message_id,),
        )
        return row

    conn = get_sqlite_connection()
    try:
        in_group = conn.execute(
            "SELECT 1 FROM group_members WHERE group_id = ? AND user_id = ?",
            (group_id, user_id),
        ).fetchone()
        if not in_group:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tienes acceso a este grupo")
        message_id = conn.execute(
            "INSERT INTO messages (group_id, sender_id, content) VALUES (?, ?, ?)",
            (group_id, user_id, content.strip()),
        ).lastrowid
        conn.commit()
        row = conn.execute(
            "SELECT m.*, u.username FROM messages m JOIN users u ON u.id = m.sender_id WHERE m.id = ?",
            (message_id,),
        ).fetchone()
        return dict(row)
    finally:
        conn.close()
