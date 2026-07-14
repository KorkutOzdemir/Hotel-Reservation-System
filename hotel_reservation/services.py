"""Business functions for login, booking, billing and reports."""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from types import SimpleNamespace
from typing import Any

from hotel_reservation.config import AppSettings, InvoiceStatus, ReservationStatus, RoomStatus, StaffType
from hotel_reservation.core.database import DatabaseManager
from hotel_reservation.dao import (
    ActivityLogDAO,
    GuestDAO,
    HousekeepingTaskDAO,
    InvoiceDAO,
    MaintenanceTicketDAO,
    NotificationDAO,
    PaymentDAO,
    ReservationDAO,
    RoomDAO,
    StaffMemberDAO,
    UserDAO,
)


class AuthService:
    def __init__(self, user_dao=None):
        # Authentication reads users through a DAO so it stays testable.
        self.user_dao = user_dao or UserDAO()

    def authenticate(self, username: str, password: str):
        # Passwords are plain text in this school/demo app.
        user = self.user_dao.find_by_username(str(username or "").strip())
        if user and int(user["is_active"]) and str(password or "") == str(user["password_hash"] or ""):
            return user
        return None

    def create_user(self, username: str, password: str, full_name: str, role: str = "staff", department: str = "Reception") -> int:
        # Normalize input before checking required fields.
        username = (username or "").strip()
        password = password or ""
        full_name = (full_name or "").strip()
        department = (department or "").strip() or "Reception"
        if not username:
            raise ValueError("Username is required.")
        if len(password) < 6:
            raise ValueError("Password must be at least 6 characters.")
        if not full_name:
            raise ValueError("Full name is required.")
        if role not in {"admin", "staff"}:
            raise ValueError("Role must be admin or staff.")
        if self.user_dao.find_by_username(username):
            raise ValueError("Username already exists.")
        return self.user_dao.insert(
            {
                "username": username,
                "password_hash": password,
                "full_name": full_name,
                "role": role,
                "department": department,
                "is_active": 1,
            }
        )


def validate_national_id(value: str) -> bool:
    #National IDs are stored as 11 digits.
    return len(re.sub(r"\D", "", value or "")) == 11


def validate_phone(value: str) -> bool:
    # Keep phone validation practical instead of country-format strict.
    return len(re.sub(r"[^\d+]", "", value or "")) >= 10


def validate_email(value: str) -> bool:
    # Email is optional, but filled values should look valid.
    return not value or bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", value))


def parse_date(value: str) -> date:
    # Dates are stored and typed as ISO-like YYYY-MM-DD strings.
    return datetime.strptime(str(value or "").strip(), AppSettings.DATE_FORMAT).date()


def validate_date_range(check_in: str, check_out: str) -> tuple[bool, str]:
    # Booking dates must be valid, future-facing and non-empty.
    try:
        start = parse_date(check_in)
        end = parse_date(check_out)
    except ValueError:
        return False, "Dates must use YYYY-MM-DD format."
    if start < date.today():
        return False, "Check-in date cannot be in the past."
    if end <= start:
        return False, "Check-out date must be after check-in date."
    return True, ""


def validate_guest(data: dict[str, Any]) -> list[str]:
    # Return all guest form errors at once for a nicer dialog message.
    errors = []
    if not data.get("full_name", "").strip():
        errors.append("Guest full name is required.")
    if not validate_national_id(data.get("national_id", "")):
        errors.append("National ID must contain 11 digits.")
    if not validate_phone(data.get("phone", "")):
        errors.append("Phone number is too short.")
    if not validate_email(data.get("email", "")):
        errors.append("Email address is invalid.")
    return errors


def validate_staff_member(data: dict[str, Any]) -> list[str]:
    # Staff records need identity plus the operation type they can handle.
    errors = []
    if not str(data.get("employee_number") or "").strip():
        errors.append("Employee ID is required.")
    if not str(data.get("first_name") or "").strip():
        errors.append("First name is required.")
    if not str(data.get("last_name") or "").strip():
        errors.append("Last name is required.")
    if not validate_national_id(data.get("national_id", "")):
        errors.append("National ID must contain 11 digits.")
    if data.get("staff_type") not in StaffType.ALL:
        errors.append("Employee type must be housekeeping or maintenance.")
    return errors


ValidationService = SimpleNamespace(
    validate_national_id=validate_national_id,
    validate_phone=validate_phone,
    validate_email=validate_email,
    parse_date=parse_date,
    validate_date_range=validate_date_range,
    validate_guest=validate_guest,
    validate_staff_member=validate_staff_member,
)


def PriceCalculator():
    # Price rules live together so booking stays focused on workflow.
    def nightly_price(room: dict[str, Any], day: date) -> float:
        # Weekends use a configurable multiplier.
        base = float(room["base_price"])
        if day.weekday() >= 5:
            base *= AppSettings.WEEKEND_MULTIPLIER
        return round(base, 2)

    def billable_guest_units(room: dict[str, Any], adults: int, children: int) -> float:
        # Empty beds count as adult-priced capacity; children count half.
        capacity = max(int(room["capacity"]), 1)
        adults = max(int(adults), 0)
        children = max(int(children), 0)
        empty_slots = max(capacity - adults - children, 0)
        return adults + empty_slots + children * AppSettings.CHILD_PRICE_MULTIPLIER

    def occupancy_adjusted_nightly_price(room: dict[str, Any], day: date, adults: int, children: int) -> float:
        # Split the nightly room price across capacity before guest weighting.
        adult_slot_price = nightly_price(room, day) / max(int(room["capacity"]), 1)
        return round(adult_slot_price * billable_guest_units(room, adults, children), 2)

    def subtotal(room: dict[str, Any], check_in: str, check_out: str, adults: int, children: int) -> float:
        # Sum every night from check-in up to, but not including, check-out.
        start = parse_date(check_in)
        end = parse_date(check_out)
        return round(
            sum(occupancy_adjusted_nightly_price(room, start + timedelta(days=offset), adults, children) for offset in range((end - start).days)),
            2,
        )

    def invoice_totals(room: dict[str, Any], check_in: str, check_out: str, adults: int, children: int, discount: float = 0.0):
        # Discount is applied before tax.
        base_total = subtotal(room, check_in, check_out, adults, children)
        discount = round(max(discount, 0.0), 2)
        if discount > base_total:
            raise ValueError("Discount cannot exceed subtotal.")
        taxable = base_total - discount
        tax = round(taxable * AppSettings.TAX_RATE, 2)
        return {"subtotal": base_total, "discount": discount, "tax": tax, "total": round(taxable + tax, 2)}

    return SimpleNamespace(
        nightly_price=nightly_price,
        billable_guest_units=billable_guest_units,
        occupancy_adjusted_nightly_price=occupancy_adjusted_nightly_price,
        subtotal=subtotal,
        invoice_totals=invoice_totals,
    )


class AppLogger:
    def __init__(self, log_dao=None):
        # The logger is intentionally small: services decide what to record.
        self.log_dao = log_dao or ActivityLogDAO()

    def log(self, action: str, entity: str, entity_id: int | None = None, details: str = "", user_id: int | None = None) -> None:
        # Log failures should not be handled here; callers keep transactions clear.
        self.log_dao.insert({"user_id": user_id, "action": action, "entity": entity, "entity_id": entity_id, "details": details})


def _staff_type_label(staff_type: str) -> str:
    # Convert enum-like values into human-readable words for errors.
    return "housekeeping" if staff_type == StaffType.HOUSEKEEPING else "maintenance"


def _require_available_staff(staff_dao, staff_member_id: int, staff_type: str):
    # Validate both employee type and current workload.
    staff = staff_dao.get(staff_member_id)
    if not staff or int(staff["is_active"]) != 1 or staff["staff_type"] != staff_type:
        raise ValueError(f"Please select an available {_staff_type_label(staff_type)} employee.")
    if not staff_dao.is_available(staff_member_id):
        raise ValueError("Employee is already assigned to an open job.")
    return staff


def _first_available_staff_id(staff_dao, staff_type: str) -> int:
    # Checkout can auto-pick the first free housekeeping employee.
    available = staff_dao.available_for(staff_type)
    if not available:
        raise ValueError(f"No available {_staff_type_label(staff_type)} employee.")
    return int(available[0]["id"])


def _count_rows(db, table: str, where: str = "", params: tuple[Any, ...] = ()) -> int:
    # Tiny query helper used by several business rules.
    sql = f"SELECT COUNT(*) AS total FROM {table}"
    if where:
        sql += f" WHERE {where}"
    row = db.query_one(sql, params)
    return int(row["total"] if row else 0)


def _room_required_status(db, room_id: int) -> tuple[str, str]:
    # Active bookings, tickets and tasks decide the room's true status.
    checks = (
        ("reservations", "room_id=? AND status IN (?, ?)", (room_id, ReservationStatus.CONFIRMED, ReservationStatus.CHECKED_IN), RoomStatus.OCCUPIED, "an active reservation"),
        ("maintenance_tickets", "room_id=? AND status <> 'closed'", (room_id,), RoomStatus.MAINTENANCE, "an open maintenance ticket"),
        ("housekeeping_tasks", "room_id=? AND status <> 'completed'", (room_id,), RoomStatus.CLEANING, "an open housekeeping task"),
    )
    for table, where, params, status, reason in checks:
        if _count_rows(db, table, where, params):
            return status, reason
    return RoomStatus.AVAILABLE, ""


def _sync_room_status(db, room_dao, room_id: int) -> None:
    # Recalculate room status after reservations or operations change.
    status, _reason = _room_required_status(db, room_id)
    room_dao.update(room_id, {"status": status})


def _room_for_work(room_dao, room_id: int, occupied_message: str):
    # Cleaning and maintenance cannot be opened for occupied rooms.
    room = room_dao.get(room_id)
    if not room or int(room["is_deleted"]) == 1:
        raise ValueError("Room not found.")
    required_status, _reason = _room_required_status(room_dao.db, room_id)
    if room["status"] == RoomStatus.OCCUPIED or required_status == RoomStatus.OCCUPIED:
        raise ValueError(occupied_message)
    return room


def BookingEngine(
    db=None,
    room_dao=None,
    reservation_dao=None,
    invoice_dao=None,
    price_calculator=None,
    logger=None,
    notification_dao=None,
    housekeeping_dao=None,
    staff_dao=None,
    payment_dao=None,
):
    # BookingEngine is a service object built as a namespace of workflow functions.
    db = db or (room_dao.db if room_dao else None) or (reservation_dao.db if reservation_dao else None) or (invoice_dao.db if invoice_dao else None) or DatabaseManager()
    room_dao = room_dao or RoomDAO(db)
    reservation_dao = reservation_dao or ReservationDAO(db)
    invoice_dao = invoice_dao or InvoiceDAO(db)
    price_calculator = price_calculator or PriceCalculator()
    logger = logger or AppLogger(ActivityLogDAO(db))
    notification_dao = notification_dao or NotificationDAO(db)
    housekeeping_dao = housekeeping_dao or HousekeepingTaskDAO(db)
    staff_dao = staff_dao or StaffMemberDAO(db)
    payment_dao = payment_dao or PaymentDAO(db)

    def reservation_or_error(reservation_id: int):
        # Central lookup gives consistent errors for reservation actions.
        reservation = reservation_dao.get(reservation_id)
        if not reservation:
            raise ValueError("Reservation not found.")
        return reservation

    def require_status(reservation, allowed: tuple[str, ...], action: str) -> None:
        # State transitions are strict so bookings cannot skip steps.
        if reservation["status"] not in allowed:
            readable = ", ".join(status.replace("_", " ") for status in allowed)
            raise ValueError(f"Only {readable} reservations can be {action}.")

    def is_available(room_id: int, check_in: str, check_out: str, exclude_reservation_id: int | None = None) -> tuple[bool, str]:
        # Availability checks date rules, room status and overlapping bookings.
        valid, message = validate_date_range(check_in, check_out)
        if not valid:
            return False, message
        room = room_dao.get(room_id)
        if not room:
            return False, "Room not found."
        if int(room["is_deleted"]) == 1:
            return False, "Room has been deleted from active inventory."
        if room["status"] in RoomStatus.BOOKING_BLOCKED:
            return False, f"Room is not available because it is {str(room['status']).replace('_', ' ')}."
        if reservation_dao.overlapping(room_id, check_in, check_out, exclude_reservation_id):
            return False, "Room already has a reservation in this date range."
        return True, ""

    def create_reservation(guest_id: int, room_id: int, check_in: str, check_out: str, adults: int, children: int, notes: str = "", created_by: int | None = None, discount: float = 0.0) -> int:
        # Creating a reservation also creates its first invoice.
        if adults < 1:
            raise ValueError("At least one adult guest is required.")
        if children < 0:
            raise ValueError("Children count cannot be negative.")
        if not db.query_one("SELECT id FROM guests WHERE id=? AND is_deleted=0", (guest_id,)):
            raise ValueError("Guest not found.")
        available, message = is_available(room_id, check_in, check_out)
        if not available:
            raise ValueError(message)
        room = room_dao.get(room_id)
        guest_count = adults + children
        capacity = int(room["capacity"])
        if guest_count > capacity:
            raise ValueError(f"Guest count exceeds room capacity ({guest_count}/{capacity}).")
        totals = price_calculator.invoice_totals(room, check_in, check_out, adults, children, discount)
        with db.transaction():
            # Keep reservation, invoice and room status changes atomic.
            reservation_id = reservation_dao.insert(
                {
                    "guest_id": guest_id,
                    "room_id": room_id,
                    "check_in": check_in,
                    "check_out": check_out,
                    "adults": adults,
                    "children": children,
                    "status": ReservationStatus.CONFIRMED,
                    "notes": notes,
                    "created_by": created_by,
                }
            )
            invoice_dao.insert(
                {
                    "reservation_id": reservation_id,
                    "subtotal": totals["subtotal"],
                    "tax": totals["tax"],
                    "discount": totals["discount"],
                    "total": totals["total"],
                    "status": InvoiceStatus.OPEN,
                    "due_date": check_out,
                }
            )
            room_dao.update(room_id, {"status": RoomStatus.OCCUPIED})
        logger.log("create", "reservation", reservation_id, f"Room {room['number']}", created_by)
        notification_dao.insert({"title": "New reservation", "message": f"Reservation #{reservation_id} has been created.", "is_read": 0})
        return reservation_id

    def check_in(reservation_id: int, user_id: int | None = None) -> None:
        # Check-in moves a confirmed reservation into the active stay state.
        reservation = reservation_or_error(reservation_id)
        require_status(reservation, (ReservationStatus.CONFIRMED,), "checked in")
        with db.transaction():
            reservation_dao.update(reservation_id, {"status": ReservationStatus.CHECKED_IN})
            room_dao.update(reservation["room_id"], {"status": RoomStatus.OCCUPIED})
        logger.log("check_in", "reservation", reservation_id, "", user_id)

    def check_out(reservation_id: int, user_id: int | None = None, assigned_staff_id: int | None = None) -> None:
        # Checkout requires full payment and then creates a cleaning task.
        reservation = reservation_or_error(reservation_id)
        require_status(reservation, (ReservationStatus.CHECKED_IN,), "checked out")
        invoice = invoice_dao.by_reservation(reservation_id)
        if not invoice:
            raise ValueError("Invoice not found.")
        balance = round(float(invoice["total"]) - payment_dao.total_paid(invoice["id"]), 2)
        if balance > 0:
            raise ValueError(f"Invoice must be fully paid before check-out. Remaining balance: {balance:.2f}.")
        assigned_staff_id = assigned_staff_id or _first_available_staff_id(staff_dao, StaffType.HOUSEKEEPING)
        _require_available_staff(staff_dao, assigned_staff_id, StaffType.HOUSEKEEPING)
        with db.transaction():
            # Mark the stay complete and move the room into cleaning.
            reservation_dao.update(reservation_id, {"status": ReservationStatus.COMPLETED})
            room_dao.update(reservation["room_id"], {"status": RoomStatus.CLEANING})
            housekeeping_dao.insert(
                {
                    "room_id": reservation["room_id"],
                    "assigned_to": None,
                    "assigned_staff_id": assigned_staff_id,
                    "task_type": "checkout_clean",
                    "status": "pending",
                    "notes": f"Generated after reservation #{reservation_id} checkout.",
                }
            )
        logger.log("check_out", "reservation", reservation_id, "", user_id)

    def cancel(reservation_id: int, user_id: int | None = None) -> None:
        # Only confirmed reservations can be cancelled from the front desk flow.
        reservation = reservation_or_error(reservation_id)
        require_status(reservation, (ReservationStatus.CONFIRMED,), "cancelled")
        with db.transaction():
            # Refund any payment rows and mark the invoice cancelled.
            reservation_dao.update(reservation_id, {"status": ReservationStatus.CANCELLED})
            invoice = invoice_dao.by_reservation(reservation_id)
            if invoice:
                paid = payment_dao.total_paid(invoice["id"])
                if paid > 0:
                    payment_dao.record_refund(invoice["id"], paid, "Reservation cancelled before check-in")
                invoice_dao.update(invoice["id"], {"status": InvoiceStatus.CANCELLED})
            _sync_room_status(db, room_dao, reservation["room_id"])
        logger.log("cancel", "reservation", reservation_id, "", user_id)

    return SimpleNamespace(is_available=is_available, create_reservation=create_reservation, check_in=check_in, check_out=check_out, cancel=cancel)


class GuestRegistryService:
    def __init__(self, guest_dao=None):
        # Guest service owns validation and soft-delete restore behavior.
        self.guest_dao = guest_dao or GuestDAO()

    def register(self, data: dict[str, Any]) -> int:
        # Clean form data before validation and database writes.
        data = dict(data)
        data["national_id"] = re.sub(r"\D", "", str(data.get("national_id") or ""))
        data["full_name"] = str(data.get("full_name") or "").strip()
        data["phone"] = str(data.get("phone") or "").strip()
        data["email"] = str(data.get("email") or "").strip()
        data["address"] = str(data.get("address") or "").strip()
        errors = validate_guest(data)
        if errors:
            raise ValueError("\n".join(errors))
        existing = self.guest_dao.db.query_one("SELECT id, is_deleted FROM guests WHERE national_id=?", (data["national_id"],))
        if existing:
            # Reuse the same guest if the national ID already exists.
            if int(existing["is_deleted"]) == 1:
                self.guest_dao.update(int(existing["id"]), {**data, "is_deleted": 0})
            return int(existing["id"])
        return self.guest_dao.insert(data)

    def delete(self, guest_id: int) -> None:
        # Guests with active stays cannot be deleted from active records.
        if not self.guest_dao.get(guest_id, include_deleted=True):
            raise ValueError("Guest not found.")
        if _count_rows(self.guest_dao.db, "reservations", "guest_id=? AND status IN (?, ?)", (guest_id, ReservationStatus.CONFIRMED, ReservationStatus.CHECKED_IN)):
            raise ValueError("Guest has active reservations and cannot be deleted.")
        self.guest_dao.delete(guest_id)


class StaffMemberService:
    def __init__(self, staff_dao=None):
        # Staff service manages operational employees.
        self.staff_dao = staff_dao or StaffMemberDAO()

    def register(self, data: dict[str, Any]) -> int:
        # Normalize identity fields before duplicate checks.
        data = dict(data)
        data["employee_number"] = str(data.get("employee_number") or "").strip()
        data["national_id"] = re.sub(r"\D", "", str(data.get("national_id") or ""))
        data["first_name"] = str(data.get("first_name") or "").strip()
        data["last_name"] = str(data.get("last_name") or "").strip()
        data["staff_type"] = str(data.get("staff_type") or "").strip()
        data["is_active"] = 1
        errors = validate_staff_member(data)
        if errors:
            raise ValueError("\n".join(errors))
        if self.staff_dao.by_employee_number(data["employee_number"]):
            raise ValueError("Employee ID already exists.")
        if self.staff_dao.by_national_id(data["national_id"]):
            raise ValueError("National ID already exists.")
        return self.staff_dao.insert(data)

    def delete(self, staff_member_id: int) -> None:
        # Employees assigned to open work must stay in the system.
        if not self.staff_dao.get(staff_member_id):
            raise ValueError("Employee not found.")
        if not self.staff_dao.is_available(staff_member_id):
            raise ValueError("Employee is assigned to an open job and cannot be deleted.")
        self.staff_dao.delete(staff_member_id)


class RoomInventoryService:
    def __init__(self, room_dao=None, maintenance_dao=None, logger=None):
        # Room service protects inventory status and deletion rules.
        self.room_dao = room_dao or RoomDAO(maintenance_dao.db if maintenance_dao else None)
        self.maintenance_dao = maintenance_dao or MaintenanceTicketDAO(self.room_dao.db)
        self.logger = logger or AppLogger(ActivityLogDAO(self.room_dao.db))

    def set_status(self, room_id: int, status: str, user_id: int | None = None) -> None:
        # Manual status changes cannot override active bookings or open work.
        if status not in RoomStatus.ALL:
            raise ValueError("Invalid room status.")
        room = self.room_dao.get(room_id)
        if not room or int(room["is_deleted"]) == 1:
            raise ValueError("Room not found.")
        required_status, reason = _room_required_status(self.room_dao.db, room_id)
        if required_status != RoomStatus.AVAILABLE and status != required_status:
            raise ValueError(f"Room cannot be marked {status.replace('_', ' ')} while it has {reason}.")
        if status == RoomStatus.OCCUPIED and required_status != RoomStatus.OCCUPIED:
            raise ValueError("Room can only be marked occupied by check-in.")
        self.room_dao.update(room_id, {"status": status})
        self.logger.log("status_change", "room", room_id, status, user_id)

    def add_room(self, data: dict[str, Any]) -> int:
        # Room numbers are unique, even across soft-deleted records.
        data = dict(data)
        data["number"] = str(data.get("number") or "").strip()
        data["room_type"] = str(data.get("room_type") or "").strip() or "Standard"
        data["amenities"] = str(data.get("amenities") or "").strip()
        data["status"] = data.get("status") or RoomStatus.AVAILABLE
        if not data["number"]:
            raise ValueError("Room number is required.")
        try:
            data["floor"] = int(data.get("floor", 0))
            data["capacity"] = int(data.get("capacity", 0))
            data["base_price"] = float(data.get("base_price", 0))
        except (TypeError, ValueError):
            raise ValueError("Floor, capacity and base price must be numeric.") from None
        if data["floor"] <= 0:
            raise ValueError("Floor must be positive.")
        if data["base_price"] <= 0:
            raise ValueError("Base price must be positive.")
        if data["capacity"] <= 0:
            raise ValueError("Capacity must be positive.")
        if data.get("status") not in RoomStatus.ALL:
            raise ValueError("Invalid room status.")
        existing = self.room_dao.by_number(data["number"], include_deleted=True)
        if existing and int(existing["is_deleted"]) == 0:
            raise ValueError("Room number already exists.")
        if existing:
            # Restore a soft-deleted room instead of creating a duplicate number.
            self.room_dao.update(existing["id"], {**data, "is_deleted": 0})
            self.logger.log("restore", "room", existing["id"], data["number"], None)
            return int(existing["id"])
        return self.room_dao.insert(data)

    def delete_room(self, room_id: int, user_id: int | None = None) -> None:
        # Delete safely: block active work and preserve historical links.
        room = self.room_dao.get(room_id)
        if not room or int(room["is_deleted"]) == 1:
            raise ValueError("Room not found.")
        checks = (
            ("reservations", "room_id=? AND status IN ('confirmed', 'checked_in')", "Room has active reservations and cannot be deleted."),
            ("housekeeping_tasks", "room_id=? AND status <> 'completed'", "Room has an open housekeeping task and cannot be deleted."),
            ("maintenance_tickets", "room_id=? AND status <> 'closed'", "Room has an open maintenance ticket and cannot be deleted."),
        )
        for table, where, message in checks:
            if _count_rows(self.room_dao.db, table, where, (room_id,)):
                raise ValueError(message)
        history = sum(_count_rows(self.room_dao.db, table, "room_id=?", (room_id,)) for table in ("reservations", "housekeeping_tasks", "maintenance_tickets"))
        if history:
            # Soft delete keeps old reports and reservations readable.
            self.room_dao.update(room_id, {"is_deleted": 1, "status": RoomStatus.AVAILABLE})
        else:
            self.room_dao.delete(room_id)
        self.logger.log("delete", "room", room_id, "", user_id)


class PaymentService:
    def __init__(self, invoice_dao=None, payment_dao=None, logger=None):
        # Payment service updates both payments and invoice status.
        self.invoice_dao = invoice_dao or InvoiceDAO(payment_dao.db if payment_dao else None)
        self.payment_dao = payment_dao or PaymentDAO(self.invoice_dao.db)
        self.logger = logger or AppLogger(ActivityLogDAO(self.invoice_dao.db))

    def record_payment(self, invoice_id: int, amount: float, method: str, reference: str = "", user_id: int | None = None) -> int:
        # Payments cannot exceed the invoice's remaining balance.
        invoice = self.invoice_dao.get(invoice_id)
        if not invoice:
            raise ValueError("Invoice not found.")
        try:
            amount = round(float(amount), 2)
        except (TypeError, ValueError):
            raise ValueError("Payment amount must be numeric.") from None
        if amount <= 0:
            raise ValueError("Payment amount must be positive.")
        if invoice["status"] == InvoiceStatus.CANCELLED:
            raise ValueError("Cancelled invoices cannot receive payments.")
        if invoice["status"] == InvoiceStatus.PAID:
            raise ValueError("Invoice is already fully paid.")
        method = (method or "").strip()
        reference = (reference or "").strip()
        if not method:
            raise ValueError("Payment method is required.")
        if method not in AppSettings.PAYMENT_METHODS:
            raise ValueError("Invalid payment method.")
        with self.invoice_dao.db.transaction():
            # Insert payment and refresh invoice status together.
            paid_before = self.payment_dao.total_paid(invoice_id)
            balance = round(float(invoice["total"]) - paid_before, 2)
            if amount > balance:
                raise ValueError(f"Payment exceeds remaining balance ({balance:.2f}).")
            payment_id = self.payment_dao.insert({"invoice_id": invoice_id, "amount": amount, "method": method, "reference": reference})
            paid = round(paid_before + amount, 2)
            status = InvoiceStatus.PAID if paid >= round(float(invoice["total"]), 2) else InvoiceStatus.PARTIAL
            self.invoice_dao.update(invoice_id, {"status": status})
            self.logger.log("payment", "invoice", invoice_id, f"{amount:.2f} via {method}", user_id)
        return payment_id


class HousekeepingService:
    def __init__(self, task_dao=None, room_dao=None, staff_dao=None, logger=None):
        # Housekeeping service assigns and completes cleaning tasks.
        self.task_dao = task_dao or HousekeepingTaskDAO(room_dao.db if room_dao else None)
        self.room_dao = room_dao or RoomDAO(self.task_dao.db)
        self.staff_dao = staff_dao or StaffMemberDAO(self.task_dao.db)
        self.logger = logger or AppLogger(ActivityLogDAO(self.task_dao.db))

    def assign_task(self, room_id: int, assigned_staff_id: int, task_type: str = "standard_clean", notes: str = "", user_id: int | None = None) -> int:
        # A room can have only one open housekeeping task at a time.
        _room_for_work(self.room_dao, room_id, "Occupied rooms cannot receive cleaning tasks.")
        _require_available_staff(self.staff_dao, assigned_staff_id, StaffType.HOUSEKEEPING)
        if _count_rows(self.task_dao.db, "housekeeping_tasks", "room_id=? AND status <> 'completed'", (room_id,)):
            raise ValueError("Room already has an open housekeeping task.")
        task_type = (task_type or "").strip() or "standard_clean"
        with self.task_dao.db.transaction():
            # Creating a cleaning task also marks the room as cleaning.
            task_id = self.task_dao.insert(
                {
                    "room_id": room_id,
                    "assigned_to": None,
                    "assigned_staff_id": assigned_staff_id,
                    "task_type": task_type,
                    "status": "pending",
                    "notes": notes.strip(),
                }
            )
            self.room_dao.update(room_id, {"status": RoomStatus.CLEANING})
        self.logger.log("assign", "housekeeping_task", task_id, task_type, user_id)
        return task_id

    def complete_task(self, task_id: int, user_id: int | None = None) -> None:
        # Completing work lets the room status return to its required state.
        task = self.task_dao.get(task_id)
        if not task:
            raise ValueError("Housekeeping task not found.")
        if task["status"] == "completed":
            raise ValueError("Housekeeping task is already completed.")
        with self.task_dao.db.transaction():
            self.task_dao.update(task_id, {"status": "completed"})
            _sync_room_status(self.task_dao.db, self.room_dao, task["room_id"])
        self.logger.log("complete", "housekeeping_task", task_id, "", user_id)


class MaintenanceService:
    def __init__(self, ticket_dao=None, room_dao=None, staff_dao=None, logger=None):
        # Maintenance service manages repair tickets and room status.
        self.ticket_dao = ticket_dao or MaintenanceTicketDAO(room_dao.db if room_dao else None)
        self.room_dao = room_dao or RoomDAO(self.ticket_dao.db)
        self.staff_dao = staff_dao or StaffMemberDAO(self.ticket_dao.db)
        self.logger = logger or AppLogger(ActivityLogDAO(self.ticket_dao.db))

    def open_ticket(self, room_id: int, issue: str, priority: str = "medium", user_id: int | None = None, assigned_staff_id: int | None = None) -> int:
        # Opening a ticket blocks the room for maintenance.
        _room_for_work(self.room_dao, room_id, "Occupied rooms cannot receive maintenance tickets.")
        issue = (issue or "").strip()
        if not issue:
            raise ValueError("Maintenance issue is required.")
        if priority not in {"low", "medium", "high", "critical"}:
            raise ValueError("Invalid maintenance priority.")
        assigned_staff_id = assigned_staff_id or _first_available_staff_id(self.staff_dao, StaffType.MAINTENANCE)
        _require_available_staff(self.staff_dao, assigned_staff_id, StaffType.MAINTENANCE)
        with self.ticket_dao.db.transaction():
            # Create the ticket and mark the room unavailable in one transaction.
            ticket_id = self.ticket_dao.insert(
                {"room_id": room_id, "reported_by": user_id, "assigned_staff_id": assigned_staff_id, "issue": issue, "priority": priority, "status": "open"}
            )
            self.room_dao.update(room_id, {"status": RoomStatus.MAINTENANCE})
        self.logger.log("open", "maintenance_ticket", ticket_id, issue, user_id)
        return ticket_id

    def close_ticket(self, ticket_id: int, user_id: int | None = None) -> None:
        # Closing the ticket recalculates whether the room is available again.
        ticket = self.ticket_dao.get(ticket_id)
        if not ticket:
            raise ValueError("Maintenance ticket not found.")
        if ticket["status"] == "closed":
            raise ValueError("Maintenance ticket is already closed.")
        with self.ticket_dao.db.transaction():
            self.ticket_dao.update(ticket_id, {"status": "closed", "closed_at": datetime.now().isoformat(timespec="seconds")})
            _sync_room_status(self.ticket_dao.db, self.room_dao, ticket["room_id"])
        self.logger.log("close", "maintenance_ticket", ticket_id, "", user_id)


def ReportGenerator(db=None):
    # Report queries are read-only summaries for dashboard and reports pages.
    db = db or DatabaseManager()

    def dashboard_stats() -> dict[str, Any]:
        # Main counters shown at the top of the dashboard.
        row = db.query_one(
            """
            SELECT COUNT(*) AS rooms,
                   COALESCE(SUM(CASE WHEN status=? THEN 1 ELSE 0 END), 0) AS occupied,
                   COALESCE(SUM(CASE WHEN status=? THEN 1 ELSE 0 END), 0) AS available,
                   (SELECT COALESCE(SUM(amount), 0)
                    FROM payments
                    WHERE date(paid_at) >= date('now', 'localtime', 'start of month')) AS monthly_revenue,
                   (SELECT COUNT(*)
                    FROM reservations
                    WHERE status IN ('checked_in', 'completed')) AS total_arrivals
            FROM rooms
            WHERE is_deleted=0
            """,
            (RoomStatus.OCCUPIED, RoomStatus.AVAILABLE),
        )
        return {
            "rooms": int(row["rooms"]),
            "occupied": int(row["occupied"]),
            "available": int(row["available"]),
            "monthly_revenue": float(row["monthly_revenue"]),
            "total_arrivals": int(row["total_arrivals"]),
            "today_arrivals": int(row["total_arrivals"]),
        }

    def occupancy_by_type():
        # Occupancy grouped by room type for the text report.
        return db.query(
            """
            SELECT room_type,
                   COUNT(*) AS total,
                   SUM(CASE WHEN status='occupied' THEN 1 ELSE 0 END) AS occupied
            FROM rooms
            WHERE is_deleted=0
            GROUP BY room_type
            ORDER BY room_type
            """
        )

    def revenue_summary():
        # Daily revenue is based on recorded payment rows.
        return db.query(
            """
            SELECT date(paid_at) AS day, COALESCE(SUM(amount), 0) AS revenue
            FROM payments
            GROUP BY date(paid_at)
            ORDER BY day DESC
            LIMIT 30
            """
        )

    def payment_method_summary():
        # Show which payment methods bring in revenue.
        return db.query(
            """
            SELECT method,
                   COUNT(*) AS payments,
                   COALESCE(SUM(amount), 0) AS revenue
            FROM payments
            GROUP BY method
            ORDER BY revenue DESC, method ASC
            """
        )

    def upcoming_arrivals():
        # Dashboard list of confirmed future arrivals.
        return db.query(
            """
            SELECT r.id, g.full_name AS guest, rooms.number AS room, r.check_in, r.check_out
            FROM reservations r
            JOIN guests g ON g.id = r.guest_id
            JOIN rooms ON rooms.id = r.room_id
            WHERE r.status='confirmed' AND date(r.check_in) >= date('now', 'localtime')
            ORDER BY r.check_in ASC
            LIMIT 8
            """
        )

    return SimpleNamespace(
        dashboard_stats=dashboard_stats,
        occupancy_by_type=occupancy_by_type,
        revenue_summary=revenue_summary,
        payment_method_summary=payment_method_summary,
        upcoming_arrivals=upcoming_arrivals,
    )
