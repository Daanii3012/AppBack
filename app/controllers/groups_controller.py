from fastapi import HTTPException, status

from app.db.config import execute_update, execute_write, fetch_all, fetch_one, get_connection, get_sqlite_connection, is_mysql_enabled


def _normalize_row(row):
    if row is None:
        return None
    return dict(row) if hasattr(row, "keys") else row


def _group_fetch_sqlite(group_id: int):
    conn = get_sqlite_connection()
    try:
        group = conn.execute("SELECT * FROM `groups` WHERE id = ?", (group_id,)).fetchone()
        if not group:
            return None
        members = conn.execute(
            """
            SELECT gm.id, gm.group_id, gm.user_id, u.username, u.full_name, gm.role, gm.participation_percentage
            FROM group_members gm
            JOIN users u ON u.id = gm.user_id
            WHERE gm.group_id = ?
            ORDER BY u.full_name ASC
            """,
            (group_id,),
        ).fetchall()
        return {**dict(group), "members": [dict(row) for row in members]}
    finally:
        conn.close()


async def _group_fetch(group_id: int):
    if is_mysql_enabled():
        group = await fetch_one("SELECT * FROM `groups` WHERE id = %s", (group_id,))
        if not group:
            return None
        members = await fetch_all(
            """
            SELECT gm.id, gm.group_id, gm.user_id, u.username, u.full_name, gm.role, gm.participation_percentage
            FROM group_members gm
            JOIN users u ON u.id = gm.user_id
            WHERE gm.group_id = %s
            ORDER BY u.full_name ASC
            """,
            (group_id,),
        )
        return {**group, "members": list(members)}
    return _group_fetch_sqlite(group_id)


async def list_for_user(user_id: int):
    if is_mysql_enabled():
        rows = await fetch_all(
            """
            SELECT g.*
            FROM `groups` g
            INNER JOIN group_members gm ON gm.group_id = g.id
            WHERE gm.user_id = %s
            ORDER BY g.created_at DESC
            """,
            (user_id,),
        )
        return list(rows)

    conn = get_sqlite_connection()
    try:
        rows = conn.execute(
            """
            SELECT g.*
            FROM `groups` g
            INNER JOIN group_members gm ON gm.group_id = g.id
            WHERE gm.user_id = ?
            ORDER BY g.created_at DESC
            """,
            (user_id,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


async def create_group(user_id: int, group_data):
    if is_mysql_enabled():
        conn = await get_connection()
        committed = False
        try:
            await conn.begin()
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "INSERT INTO grupos (creador_id, titulo, descripcion, objetivo) VALUES (%s, %s, %s, %s)",
                    (user_id, group_data.title.strip(), group_data.description.strip(), group_data.objective.strip()),
                )
                group_id = cursor.lastrowid
                await cursor.execute(
                    "INSERT INTO miembros_grupo (grupo_id, usuario_id, rol, porcentaje_participacion) VALUES (%s, %s, 'propietario', 100.0)",
                    (group_id, user_id),
                )
            await conn.commit()
            committed = True
        finally:
            if not committed:
                await conn.rollback()
            conn.close()
        return await _group_fetch(group_id)

    conn = get_sqlite_connection()
    try:
        group_id = conn.execute(
            "INSERT INTO `groups` (creator_id, title, description, objective) VALUES (?, ?, ?, ?)",
            (user_id, group_data.title.strip(), group_data.description.strip(), group_data.objective.strip()),
        ).lastrowid
        conn.execute(
            "INSERT INTO group_members (group_id, user_id, role, participation_percentage) VALUES (?, ?, 'owner', 100.0)",
            (group_id, user_id),
        )
        conn.commit()
        return _group_fetch_sqlite(group_id)
    finally:
        conn.close()


async def get_group(group_id: int, user_id: int):
    group = await _group_fetch(group_id)
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Grupo no encontrado")
    membership = group["members"]
    if not any(member["user_id"] == user_id for member in membership):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tienes acceso a este grupo")
    return group


async def invite_user(group_id: int, sender_id: int, email: str):
    if is_mysql_enabled():
        group = await fetch_one("SELECT * FROM `groups` WHERE id = %s", (group_id,))
        if not group:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Grupo no encontrado")
        if group["creator_id"] != sender_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo el creador puede invitar usuarios")
        recipient = await fetch_one("SELECT * FROM users WHERE email = %s", (email.lower(),))
        if not recipient:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")
        if recipient["id"] == sender_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No puedes invitarte a ti mismo")
        exists_member = await fetch_one(
            "SELECT 1 FROM group_members WHERE group_id = %s AND user_id = %s",
            (group_id, recipient["id"]),
        )
        if exists_member:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El usuario ya es miembro del grupo")
        invitation = await fetch_one(
            "SELECT * FROM group_invitations WHERE group_id = %s AND recipient_id = %s",
            (group_id, recipient["id"]),
        )
        if invitation:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ya existe una invitación pendiente")
        invitation_id = await execute_write(
            "INSERT INTO invitaciones_grupo (grupo_id, remitente_id, destinatario_id, estado) VALUES (%s, %s, %s, 'pendiente')",
            (group_id, sender_id, recipient["id"]),
        )
        created = await fetch_one("SELECT * FROM group_invitations WHERE id = %s", (invitation_id,))
        return {**created, "recipient_email": recipient["email"]}

    conn = get_sqlite_connection()
    try:
        group = conn.execute("SELECT * FROM `groups` WHERE id = ?", (group_id,)).fetchone()
        if not group:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Grupo no encontrado")
        if group["creator_id"] != sender_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo el creador puede invitar usuarios")
        recipient = conn.execute("SELECT * FROM users WHERE email = ?", (email.lower(),)).fetchone()
        if not recipient:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")
        if recipient["id"] == sender_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No puedes invitarte a ti mismo")
        exists_member = conn.execute(
            "SELECT 1 FROM group_members WHERE group_id = ? AND user_id = ?",
            (group_id, recipient["id"]),
        ).fetchone()
        if exists_member:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El usuario ya es miembro del grupo")
        invitation = conn.execute(
            "SELECT * FROM group_invitations WHERE group_id = ? AND recipient_id = ?",
            (group_id, recipient["id"]),
        ).fetchone()
        if invitation:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ya existe una invitación pendiente")
        invitation_id = conn.execute(
            "INSERT INTO group_invitations (group_id, sender_id, recipient_id, status) VALUES (?, ?, ?, 'pending')",
            (group_id, sender_id, recipient["id"]),
        ).lastrowid
        conn.commit()
        created = conn.execute("SELECT * FROM group_invitations WHERE id = ?", (invitation_id,)).fetchone()
        return {**dict(created), "recipient_email": recipient["email"]}
    finally:
        conn.close()


async def respond_invitation(invitation_id: int, user_id: int, status_value: str):
    if is_mysql_enabled():
        invitation = await fetch_one("SELECT * FROM group_invitations WHERE id = %s", (invitation_id,))
        if not invitation:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invitación no encontrada")
        if invitation["recipient_id"] != user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No puedes responder a esta invitación")
        if status_value not in {"accepted", "rejected", "cancelled"}:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Estado no válido")
        await execute_update(
            "UPDATE invitaciones_grupo SET estado = %s, fecha_respuesta = CURRENT_TIMESTAMP WHERE id = %s",
            ({
                "accepted": "aceptada",
                "rejected": "rechazada",
                "cancelled": "cancelada",
            }[status_value], invitation_id),
        )
        if status_value == "accepted":
            existing = await fetch_one(
                "SELECT 1 FROM group_members WHERE group_id = %s AND user_id = %s",
                (invitation["group_id"], invitation["recipient_id"]),
            )
            if not existing:
                await execute_write(
                    "INSERT INTO miembros_grupo (grupo_id, usuario_id, rol, porcentaje_participacion) VALUES (%s, %s, 'miembro', 0.0)",
                    (invitation["group_id"], invitation["recipient_id"]),
                )
        return {"message": f"Invitación {status_value} correctamente"}

    conn = get_sqlite_connection()
    try:
        invitation = conn.execute("SELECT * FROM group_invitations WHERE id = ?", (invitation_id,)).fetchone()
        if not invitation:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invitación no encontrada")
        if invitation["recipient_id"] != user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No puedes responder a esta invitación")
        if status_value not in {"accepted", "rejected", "cancelled"}:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Estado no válido")
        conn.execute(
            "UPDATE group_invitations SET status = ?, responded_at = CURRENT_TIMESTAMP WHERE id = ?",
            (status_value, invitation_id),
        )
        if status_value == "accepted":
            existing = conn.execute(
                "SELECT 1 FROM group_members WHERE group_id = ? AND user_id = ?",
                (invitation["group_id"], invitation["recipient_id"]),
            ).fetchone()
            if not existing:
                conn.execute(
                    "INSERT INTO group_members (group_id, user_id, role, participation_percentage) VALUES (?, ?, 'member', 0.0)",
                    (invitation["group_id"], invitation["recipient_id"]),
                )
        conn.commit()
        return {"message": f"Invitación {status_value} correctamente"}
    finally:
        conn.close()


async def list_invitations(user_id: int):
    if is_mysql_enabled():
        rows = await fetch_all(
            """
            SELECT gi.*, u.email AS recipient_email
            FROM group_invitations gi
            JOIN users u ON u.id = gi.recipient_id
            WHERE gi.recipient_id = %s
            ORDER BY gi.created_at DESC
            """,
            (user_id,),
        )
        return list(rows)

    conn = get_sqlite_connection()
    try:
        rows = conn.execute(
            """
            SELECT gi.*, u.email AS recipient_email
            FROM group_invitations gi
            JOIN users u ON u.id = gi.recipient_id
            WHERE gi.recipient_id = ?
            ORDER BY gi.created_at DESC
            """,
            (user_id,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


async def balance(group_id: int, user_id: int):
    group = await _group_fetch(group_id)
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Grupo no encontrado")
    if not any(member["user_id"] == user_id for member in group["members"]):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tienes acceso a este grupo")

    if is_mysql_enabled():
        members = await fetch_all(
            """
            SELECT gm.user_id, u.username,
                   COALESCE(SUM(es.amount_due), 0) AS total_owed,
                   COALESCE(SUM(CASE WHEN e.paid_by_id = gm.user_id THEN e.amount ELSE 0 END), 0) AS total_paid
            FROM group_members gm
            JOIN users u ON u.id = gm.user_id
            LEFT JOIN expense_shares es ON es.user_id = gm.user_id
            LEFT JOIN expenses e ON e.id = es.expense_id AND e.group_id = %s
            WHERE gm.group_id = %s
            GROUP BY gm.user_id, u.username
            ORDER BY u.username ASC
            """,
            (group_id, group_id),
        )
    else:
        conn = get_sqlite_connection()
        try:
            members = conn.execute(
                """
                SELECT gm.user_id, u.username,
                       COALESCE(SUM(es.amount_due), 0) AS total_owed,
                       COALESCE(SUM(CASE WHEN e.paid_by_id = gm.user_id THEN e.amount ELSE 0 END), 0) AS total_paid
                FROM group_members gm
                JOIN users u ON u.id = gm.user_id
                LEFT JOIN expense_shares es ON es.user_id = gm.user_id
                LEFT JOIN expenses e ON e.id = es.expense_id AND e.group_id = ?
                WHERE gm.group_id = ?
                GROUP BY gm.user_id, u.username
                ORDER BY u.username ASC
                """,
                (group_id, group_id),
            ).fetchall()
        finally:
            conn.close()

    result = []
    for member in members:
        total_paid = float(member["total_paid"] or 0)
        total_owed = float(member["total_owed"] or 0)
        result.append({
            "user_id": member["user_id"],
            "username": member["username"],
            "total_owed": round(total_owed, 2),
            "total_paid": round(total_paid, 2),
            "balance": round(total_paid - total_owed, 2),
        })
    return result
