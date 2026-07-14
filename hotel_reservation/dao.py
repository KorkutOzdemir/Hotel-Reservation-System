"""Small database helpers for each table."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Iterable

from hotel_reservation.core.database import DatabaseManager


class BaseDAO:
    def __init__(self, db: DatabaseManager | None = None, table: str = "", columns: tuple[str, ...] = ()) -> None:
        # Every DAO gets the shared database and the columns it may write.
        self.db = db or DatabaseManager()
        self.table = table
        self.columns = columns

    def insert(self, data: dict[str, Any]) -> int:
        # Ignore unknown keys so forms can pass dictionaries safely.
        clean = {key: value for key, value in data.items() if key in self.columns}
        if not clean:
            raise ValueError(f"No valid columns provided for {self.table}.")
        columns = ", ".join(clean.keys())
        placeholders = ", ".join(["?"] * len(clean))
        cursor = self.db.execute(
            f"INSERT INTO {self.table} ({columns}) VALUES ({placeholders})",
            tuple(clean.values()),
        )
        return int(cursor.lastrowid)

    def update(self, record_id: int, data: dict[str, Any]) -> None:
        # Only allowed columns can be updated through this helper.
        clean = {key: value for key, value in data.items() if key in self.columns}
        if not clean:
            return
        assignments = ", ".join(f"{column}=?" for column in clean.keys())
        self.db.execute(f"UPDATE {self.table} SET {assignments} WHERE id=?", (*clean.values(), record_id))

    def delete(self, record_id: int) -> None:
        # Hard deletes are used only where the service layer allows them.
        self.db.execute(f"DELETE FROM {self.table} WHERE id=?", (record_id,))

    def get(self, record_id: int):
        # Fetch one row by primary key.
        return self.db.query_one(f"SELECT * FROM {self.table} WHERE id=?", (record_id,))

    def list(
        self,
        where: str | None = None,
        params: Iterable[Any] | None = None,
        *,
        order_by: str = "id DESC",
        limit: int | None = None,
    ) -> list[Any]:
        # Build simple list queries while keeping parameters separate.
        sql = f"SELECT * FROM {self.table}"
        if where:
            sql += f" WHERE {where}"
        if order_by:
            sql += f" ORDER BY {order_by}"
        if limit:
            sql += f" LIMIT {int(limit)}"
        return self.db.query(sql, params)

    def count(self, where: str | None = None, params: Iterable[Any] | None = None) -> int:
        # Small helper for screens and services that need totals.
        sql = f"SELECT COUNT(*) AS total FROM {self.table}"
        if where:
            sql += f" WHERE {where}"
        row = self.db.query_one(sql, params)
        return int(row["total"] if row else 0)


def _dao(db, table: str, columns: tuple[str, ...]):
    # Factory keeps the individual DAO functions compact.
    return BaseDAO(db, table, columns)


def UserDAO(db: DatabaseManager | None = None):
    # User rows handle login and role checks.
    dao = _dao(db, "users", ("username", "password_hash", "full_name", "role", "department", "is_active"))
    dao.find_by_username = lambda username: dao.db.query_one("SELECT * FROM users WHERE username=?", (username,))
    return dao


def StaffMemberDAO(db: DatabaseManager | None = None):
    # Staff members are assignable workers, not login accounts.
    dao = _dao(db, "staff_members", ("employee_number", "national_id", "first_name", "last_name", "staff_type", "is_active"))
    # Summary marks each employee as available, busy or inactive.
    summary = """
        SELECT s.id, s.employee_number, s.national_id, s.first_name, s.last_name,
               s.first_name || ' ' || s.last_name AS full_name,
               s.staff_type, s.is_active,
               CASE
                   WHEN s.is_active <> 1 THEN 'Inactive'
                   WHEN EXISTS (
                       SELECT 1 FROM housekeeping_tasks h
                       WHERE h.assigned_staff_id=s.id AND h.status <> 'completed'
                   )
                   OR EXISTS (
                       SELECT 1 FROM maintenance_tickets m
                       WHERE m.assigned_staff_id=s.id AND m.status <> 'closed'
                   )
                   THEN 'Busy'
                   ELSE 'Available'
               END AS availability_status,
               s.created_at
        FROM staff_members s
    """

    dao.by_employee_number = lambda employee_number: dao.db.query_one(
        "SELECT * FROM staff_members WHERE employee_number=?", (employee_number,)
    )
    dao.by_national_id = lambda national_id: dao.db.query_one(
        "SELECT * FROM staff_members WHERE national_id=?", (national_id,)
    )
    dao.list_by_type = lambda staff_type: dao.db.query(
        summary + " WHERE s.staff_type=? ORDER BY s.first_name ASC, s.last_name ASC", (staff_type,)
    )

    def available_for(staff_type: str):
        # Return only active workers with no unfinished task or ticket.
        return dao.db.query(
            """
            SELECT s.id, s.employee_number, s.national_id, s.first_name, s.last_name,
                   s.first_name || ' ' || s.last_name AS full_name,
                   s.staff_type, s.is_active
            FROM staff_members s
            WHERE s.staff_type=?
              AND s.is_active=1
              AND NOT EXISTS (
                  SELECT 1 FROM housekeeping_tasks h
                  WHERE h.assigned_staff_id=s.id AND h.status <> 'completed'
              )
              AND NOT EXISTS (
                  SELECT 1 FROM maintenance_tickets m
                  WHERE m.assigned_staff_id=s.id AND m.status <> 'closed'
              )
            ORDER BY s.first_name ASC, s.last_name ASC
            """,
            (staff_type,),
        )

    def is_available(staff_member_id: int) -> bool:
        # A worker is busy if either operations table has open work for them.
        row = dao.db.query_one(
            """
            SELECT
                (SELECT COUNT(*) FROM housekeeping_tasks
                 WHERE assigned_staff_id=? AND status <> 'completed') +
                (SELECT COUNT(*) FROM maintenance_tickets
                 WHERE assigned_staff_id=? AND status <> 'closed') AS total
            """,
            (staff_member_id, staff_member_id),
        )
        return not row or int(row["total"]) == 0

    dao.available_for = available_for
    dao.is_available = is_available
    return dao


def RoomDAO(db: DatabaseManager | None = None):
    # Rooms use soft delete so old reservations keep their history.
    dao = _dao(db, "rooms", ("number", "floor", "room_type", "capacity", "base_price", "status", "amenities", "is_deleted"))

    def list_rooms(where=None, params=None, *, order_by="id DESC", limit=None):
        # Active room lists hide soft-deleted inventory by default.
        where = f"({where}) AND is_deleted=0" if where else "is_deleted=0"
        return BaseDAO.list(dao, where, params, order_by=order_by, limit=limit)

    def by_number(number: str, *, include_deleted: bool = False):
        # Used to prevent duplicate room numbers and restore soft-deleted rooms.
        where = "number=?"
        if not include_deleted:
            where += " AND is_deleted=0"
        return dao.db.query_one(f"SELECT * FROM rooms WHERE {where}", (number,))

    def search(term: str):
        # Search across the fields the front desk naturally remembers.
        wildcard = f"%{term}%"
        return dao.db.query(
            """
            SELECT * FROM rooms
            WHERE is_deleted=0
              AND (number LIKE ? OR room_type LIKE ? OR amenities LIKE ? OR status LIKE ?)
            ORDER BY floor ASC, number ASC
            """,
            (wildcard, wildcard, wildcard, wildcard),
        )

    dao.list = list_rooms
    dao.by_number = by_number
    dao.by_status = lambda status: dao.list("status=?", (status,), order_by="floor ASC, number ASC")
    dao.search = search
    return dao


def GuestDAO(db: DatabaseManager | None = None):
    # Guests also use soft delete to preserve reservation history.
    dao = _dao(db, "guests", ("national_id", "full_name", "phone", "email", "address", "is_deleted"))

    def list_guests(where=None, params=None, *, order_by="id DESC", limit=None):
        # Normal guest lists show only active records.
        where = f"({where}) AND is_deleted=0" if where else "is_deleted=0"
        return BaseDAO.list(dao, where, params, order_by=order_by, limit=limit)

    def get(record_id: int, *, include_deleted: bool = False):
        # Services can include deleted guests when validating history.
        where = "id=?"
        if not include_deleted:
            where += " AND is_deleted=0"
        return dao.db.query_one(f"SELECT * FROM guests WHERE {where}", (record_id,))

    def search(term: str):
        # Search by identity, name or contact details.
        wildcard = f"%{term}%"
        return dao.db.query(
            """
            SELECT * FROM guests
            WHERE is_deleted=0
              AND (national_id LIKE ? OR full_name LIKE ? OR phone LIKE ? OR email LIKE ?)
            ORDER BY full_name ASC
            """,
            (wildcard, wildcard, wildcard, wildcard),
        )

    dao.list = list_guests
    dao.get = get
    dao.delete = lambda record_id: dao.update(record_id, {"is_deleted": 1})
    dao.search = search
    return dao


def ReservationDAO(db: DatabaseManager | None = None):
    # Reservation DAO owns booking rows and their dashboard summaries.
    dao = _dao(
        db,
        "reservations",
        ("guest_id", "room_id", "check_in", "check_out", "adults", "children", "status", "notes", "created_by"),
    )

    def overlapping(room_id: int, check_in: str, check_out: str, exclude_id: int | None = None):
        # Date overlap check prevents double-booking the same room.
        params: list[Any] = [room_id, check_out, check_in]
        exclude = ""
        if exclude_id:
            exclude = " AND id <> ?"
            params.append(exclude_id)
        return dao.db.query(
            f"""
            SELECT * FROM reservations
            WHERE room_id=?
              AND status IN ('confirmed', 'checked_in')
              AND date(check_in) < date(?)
              AND date(check_out) > date(?)
              {exclude}
            """,
            params,
        )

    def detailed(where: str):
        # Join related names so the GUI can render reservation tables directly.
        return dao.db.query(
            f"""
            SELECT r.id, g.full_name AS guest, rooms.number AS room, r.check_in, r.check_out,
                   r.adults, r.children, r.status, COALESCE(i.total, 0) AS total
            FROM reservations r
            JOIN guests g ON g.id = r.guest_id
            JOIN rooms ON rooms.id = r.room_id
            LEFT JOIN invoices i ON i.reservation_id = r.id
            WHERE {where}
            ORDER BY r.created_at DESC
            """
        )

    dao.overlapping = overlapping
    dao.active_detailed = lambda: detailed("r.status IN ('confirmed', 'checked_in')")
    dao.history_detailed = lambda: detailed("r.status IN ('completed', 'cancelled')")
    return dao


def InvoiceDAO(db: DatabaseManager | None = None):
    # Invoices summarize reservation charges and payment balance.
    dao = _dao(db, "invoices", ("reservation_id", "subtotal", "tax", "discount", "total", "status", "due_date"))
    dao.by_reservation = lambda reservation_id: dao.db.query_one(
        "SELECT * FROM invoices WHERE reservation_id=?", (reservation_id,)
    )
    # Billing rows include paid amount and remaining balance in one query.
    dao.detailed = lambda: dao.db.query(
        """
        SELECT i.id, i.reservation_id, g.full_name AS guest,
               rooms.number AS room,
               i.subtotal, i.tax, i.discount, i.total, i.status,
               COALESCE(SUM(p.amount), 0) AS paid,
               CASE
                   WHEN i.status = 'cancelled' THEN 0
                   ELSE ROUND(i.total - COALESCE(SUM(p.amount), 0), 2)
               END AS balance
        FROM invoices i
        JOIN reservations r ON r.id = i.reservation_id
        JOIN guests g ON g.id = r.guest_id
        JOIN rooms ON rooms.id = r.room_id
        LEFT JOIN payments p ON p.invoice_id = i.id
        GROUP BY i.id
        ORDER BY i.created_at DESC
        """
    )
    return dao


def PaymentDAO(db: DatabaseManager | None = None):
    # Payments can be positive charges or negative refund rows.
    dao = _dao(db, "payments", ("invoice_id", "amount", "method", "paid_at", "reference"))
    dao.by_invoice = lambda invoice_id: dao.list("invoice_id=?", (invoice_id,), order_by="paid_at DESC, id DESC")
    dao.record_refund = lambda invoice_id, amount, reference="": dao.insert(
        {"invoice_id": invoice_id, "amount": -abs(round(float(amount), 2)), "method": "Refund", "reference": reference}
    )

    def total_paid(invoice_id: int) -> float:
        # Summing payment rows gives the current paid amount for an invoice.
        row = dao.db.query_one(
            "SELECT COALESCE(SUM(amount), 0) AS total FROM payments WHERE invoice_id=?",
            (invoice_id,),
        )
        return float(row["total"] if row else 0)

    dao.total_paid = total_paid
    return dao


def NotificationDAO(db: DatabaseManager | None = None):
    # Notifications are lightweight messages shown or saved by services.
    return _dao(db, "notifications", ("user_id", "title", "message", "is_read"))


def ActivityLogDAO(db: DatabaseManager | None = None):
    # Activity logs keep a simple audit trail of user actions.
    return _dao(db, "activity_logs", ("user_id", "action", "entity", "entity_id", "details"))


def HousekeepingTaskDAO(db: DatabaseManager | None = None):
    # Housekeeping tasks connect rooms with assigned cleaning staff.
    dao = _dao(db, "housekeeping_tasks", ("room_id", "assigned_to", "assigned_staff_id", "task_type", "status", "notes"))
    # Detailed rows show readable room and employee names for the UI.
    dao.detailed = lambda: dao.db.query(
        """
        SELECT h.id, rooms.number AS room,
               COALESCE(s.first_name || ' ' || s.last_name, u.full_name, '-') AS assigned_to,
               h.task_type, h.status, h.notes
        FROM housekeeping_tasks h
        JOIN rooms ON rooms.id = h.room_id
        LEFT JOIN staff_members s ON s.id = h.assigned_staff_id
        LEFT JOIN users u ON u.id = h.assigned_to
        ORDER BY h.created_at DESC
        """
    )
    return dao


def MaintenanceTicketDAO(db: DatabaseManager | None = None):
    # Maintenance tickets track repairs and their assigned technicians.
    dao = _dao(db, "maintenance_tickets", ("room_id", "reported_by", "assigned_staff_id", "issue", "priority", "status", "closed_at"))
    # Detailed rows flatten joins for the operations screen.
    dao.detailed = lambda: dao.db.query(
        """
        SELECT m.id, rooms.number AS room, COALESCE(u.full_name, '-') AS reported_by,
               COALESCE(s.first_name || ' ' || s.last_name, '-') AS assigned_to,
               m.issue, m.priority, m.status, m.opened_at, COALESCE(m.closed_at, '') AS closed_at
        FROM maintenance_tickets m
        JOIN rooms ON rooms.id = m.room_id
        LEFT JOIN users u ON u.id = m.reported_by
        LEFT JOIN staff_members s ON s.id = m.assigned_staff_id
        ORDER BY m.opened_at DESC
        """
    )
    return dao
