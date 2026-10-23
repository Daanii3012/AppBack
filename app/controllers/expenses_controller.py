from fastapi import HTTPException, status

from app.db.config import execute_update, execute_write, fetch_all, fetch_one, get_sqlite_connection, is_mysql_enabled


def _ensure_group_member(conn, group_id: int, user_id: int):
    row = conn.execute(
        "SELECT 1 FROM group_members WHERE group_id = ? AND user_id = ?",
        (group_id, user_id),
    ).fetchone()
    if not row:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El usuario no pertenece al grupo")


async def create_expense(group_id: int, user_id: int, expense_data):
    if is_mysql_enabled():
        group = await fetch_one("SELECT * FROM `groups` WHERE id = %s", (group_id,))
        if not group:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Grupo no encontrado")
        if group["creator_id"] != user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo el creador puede registrar gastos")
        member = await fetch_one("SELECT 1 FROM group_members WHERE group_id = %s AND user_id = %s", (group_id, user_id))
        paid_member = await fetch_one("SELECT 1 FROM group_members WHERE group_id = %s AND user_id = %s", (group_id, expense_data.paid_by_id))
        if not member or not paid_member:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El usuario no pertenece al grupo")

        members = await fetch_all(
            "SELECT user_id, participation_percentage FROM group_members WHERE group_id = %s ORDER BY user_id ASC",
            (group_id,),
        )
        if not members:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El grupo no tiene miembros")

        specified = {item.user_id: item.percentage for item in expense_data.shares}
        if not specified:
            total = 100.0
            for member_row in members:
                share = member_row["participation_percentage"] if member_row["participation_percentage"] else (100.0 / len(members))
                specified[member_row["user_id"]] = share
            total = sum(specified.values())
            if total == 0:
                total = 100.0
            if total != 100:
                for member_id in specified:
                    specified[member_id] = (specified[member_id] / total) * 100.0
        else:
            total_percentage = sum(specified.values())
            if abs(total_percentage - 100.0) > 0.001:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La suma de porcentajes debe ser 100")

        for member_row in members:
            if member_row["user_id"] not in specified:
                specified[member_row["user_id"]] = 0.0

        expense_id = await execute_write(
            "INSERT INTO expenses (group_id, created_by_id, paid_by_id, title, description, amount, category, expense_date) VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)",
            (group_id, user_id, expense_data.paid_by_id, expense_data.title.strip(), expense_data.description, expense_data.amount, expense_data.category),
        )

        inserted = []
        for member_row in members:
            pct = float(specified.get(member_row["user_id"], 0.0))
            amount_due = round((expense_data.amount * pct / 100.0), 2)
            await execute_write(
                "INSERT INTO expense_shares (expense_id, user_id, percentage, amount_due) VALUES (%s, %s, %s, %s)",
                (expense_id, member_row["user_id"], pct, amount_due),
            )
            inserted.append({"user_id": member_row["user_id"], "percentage": pct, "amount_due": amount_due})
        return {"message": "Gasto registrado correctamente", "expense_id": expense_id, "shares": inserted}

    conn = get_sqlite_connection()
    try:
        group = conn.execute("SELECT * FROM `groups` WHERE id = ?", (group_id,)).fetchone()
        if not group:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Grupo no encontrado")
        if group["creator_id"] != user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo el creador puede registrar gastos")
        _ensure_group_member(conn, group_id, user_id)
        _ensure_group_member(conn, group_id, expense_data.paid_by_id)

        members = conn.execute(
            "SELECT user_id, participation_percentage FROM group_members WHERE group_id = ? ORDER BY user_id ASC",
            (group_id,),
        ).fetchall()
        if not members:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El grupo no tiene miembros")

        specified = {item.user_id: item.percentage for item in expense_data.shares}
        if not specified:
            total = 100.0
            for member in members:
                share = member["participation_percentage"] if member["participation_percentage"] else (100.0 / len(members))
                specified[member["user_id"]] = share
            total = sum(specified.values())
            if total == 0:
                total = 100.0
            if total != 100:
                for member_id in specified:
                    specified[member_id] = (specified[member_id] / total) * 100.0
        else:
            total_percentage = sum(specified.values())
            if abs(total_percentage - 100.0) > 0.001:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La suma de porcentajes debe ser 100")

        for member in members:
            if member["user_id"] not in specified:
                specified[member["user_id"]] = 0.0

        expense_id = conn.execute(
            "INSERT INTO expenses (group_id, created_by_id, paid_by_id, title, description, amount, category, expense_date) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
            (group_id, user_id, expense_data.paid_by_id, expense_data.title.strip(), expense_data.description, expense_data.amount, expense_data.category),
        ).lastrowid

        inserted = []
        for member in members:
            pct = float(specified.get(member["user_id"], 0.0))
            amount_due = round((expense_data.amount * pct / 100.0), 2)
            conn.execute(
                "INSERT INTO expense_shares (expense_id, user_id, percentage, amount_due) VALUES (?, ?, ?, ?)",
                (expense_id, member["user_id"], pct, amount_due),
            )
            inserted.append({"user_id": member["user_id"], "percentage": pct, "amount_due": amount_due})
        conn.commit()
        return {"message": "Gasto registrado correctamente", "expense_id": expense_id, "shares": inserted}
    finally:
        conn.close()


async def list_expenses(group_id: int, user_id: int):
    if is_mysql_enabled():
        group_member = await fetch_one(
            "SELECT 1 FROM group_members WHERE group_id = %s AND user_id = %s",
            (group_id, user_id),
        )
        if not group_member:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tienes acceso a este grupo")
        rows = await fetch_all(
            """
            SELECT e.*, u.username AS paid_by_username
            FROM expenses e
            JOIN users u ON u.id = e.paid_by_id
            WHERE e.group_id = %s
            ORDER BY e.created_at DESC
            """,
            (group_id,),
        )
        expenses = []
        for row in rows:
            shares = await fetch_all(
                "SELECT user_id, percentage, amount_due FROM expense_shares WHERE expense_id = %s ORDER BY user_id ASC",
                (row["id"],),
            )
            expenses.append({**row, "shares": list(shares)})
        return expenses

    conn = get_sqlite_connection()
    try:
        group_member = conn.execute(
            "SELECT 1 FROM group_members WHERE group_id = ? AND user_id = ?",
            (group_id, user_id),
        ).fetchone()
        if not group_member:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tienes acceso a este grupo")
        rows = conn.execute(
            """
            SELECT e.*, u.username AS paid_by_username
            FROM expenses e
            JOIN users u ON u.id = e.paid_by_id
            WHERE e.group_id = ?
            ORDER BY e.created_at DESC
            """,
            (group_id,),
        ).fetchall()
        expenses = []
        for row in rows:
            shares = conn.execute(
                "SELECT user_id, percentage, amount_due FROM expense_shares WHERE expense_id = ? ORDER BY user_id ASC",
                (row["id"],),
            ).fetchall()
            expenses.append({**dict(row), "shares": [dict(item) for item in shares]})
        return expenses
    finally:
        conn.close()
