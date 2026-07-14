"""Application screens and data-entry dialogs."""

from __future__ import annotations

import tkinter as tk
from datetime import date, timedelta
from tkinter import ttk
from typing import Any, Callable

from hotel_reservation.config import AppSettings, RoomStatus, StaffType
from hotel_reservation.gui.theme import Theme
from hotel_reservation.gui.widgets import (
    BaseFrame,
    DataTable,
    ModalDialog,
    ModernButton,
    PhotoCard,
    ResortBanner,
    RoomCard,
    SearchHeader,
    StatCard,
)


ROOM_TYPE_CHOICES = [
    "Standard",
    "Accessible",
    "Deluxe",
    "Suite",
    "Family",
    "Family Suite",
    "Executive",
    "Presidential Suite",
    "Group Villa",
]


def _entry(parent, label: str, variable: tk.StringVar, row: int, width: int = 32, show: str | None = None) -> None:
    # Standard label + entry row used by dialogs.
    ttk.Label(parent, text=label, style="Field.TLabel").grid(row=row, column=0, sticky="w", padx=(0, 14), pady=7)
    ttk.Entry(parent, textvariable=variable, width=width, show=show).grid(row=row, column=1, sticky="ew", pady=7)


def _combobox(parent, label: str, variable: tk.StringVar, row: int, values, width: int | None = None):
    # Standard read-only option row used by dialogs.
    ttk.Label(parent, text=label, style="Field.TLabel").grid(row=row, column=0, sticky="w", padx=(0, 14), pady=7)
    options = {"width": width} if width is not None else {}
    box = ttk.Combobox(parent, textvariable=variable, values=values, state="readonly", **options)
    box.grid(row=row, column=1, sticky="ew", pady=7)
    return box


def _selected_int(value: str) -> int:
    # Dialog options start with "id - label", so the first part is the ID.
    return int(value.split(" - ", 1)[0].strip())


def _required_selected_int(value: str, field_name: str) -> int:
    # Convert a selected option into an integer ID with a friendly error.
    if not value.strip():
        raise ValueError(f"Please select {field_name}.")
    try:
        return _selected_int(value)
    except (IndexError, ValueError):
        raise ValueError(f"Invalid {field_name} selection.") from None


def _staff_option(row: Any) -> str:
    # Staff dropdowns show name plus employee number for clarity.
    return f"{row['id']} - {row['first_name']} {row['last_name']} ({row['employee_number']})"


def _select_option(options: list[str], selected_id: int | None = None) -> str:
    # Preselect a specific ID when a dialog opens from a table row.
    if selected_id:
        return next((option for option in options if option.startswith(f"{selected_id} - ")), "")
    return options[0] if options else ""


def _required_int(value: str, field_name: str, minimum: int | None = None) -> int:
    # Parse whole-number fields and enforce optional minimum values.
    try:
        parsed = int(value.strip())
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} must be a whole number.") from None
    if minimum is not None and parsed < minimum:
        raise ValueError(f"{field_name} must be at least {minimum}.")
    return parsed


def _required_float(value: str, field_name: str, minimum: float | None = None) -> float:
    # Parse money and decimal fields with an optional minimum.
    try:
        parsed = float(value.strip())
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} must be a number.") from None
    if minimum is not None and parsed < minimum:
        raise ValueError(f"{field_name} must be at least {minimum:g}.")
    return parsed


def _dialog_actions(
    parent,
    row: int,
    primary_text: str,
    primary_command: Callable[[], None],
    cancel_command: Callable[[], None],
) -> None:
    # Dialog actions always put Cancel on the right and the main action before it.
    actions = ttk.Frame(parent)
    actions.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(14, 0))
    ModernButton(actions, "Cancel", cancel_command, variant="ghost", width=92).pack(side="right")
    ModernButton(actions, primary_text, primary_command, variant="primary").pack(side="right", padx=(0, 8))


def _require_admin(app) -> bool:
    # Admin-only buttons call this before opening destructive actions.
    if app.is_admin():
        return True
    app.show_error("This action is available to administrators only.", title="Access denied")
    return False


class DashboardFrame(BaseFrame):
    """Dashboard page with live operational metrics."""

    def __init__(self, master, app) -> None:
        super().__init__(master, app=app)
        # The dashboard gives a quick operational snapshot after login.
        ResortBanner(
            self,
            "Grand Vista Operations",
            "Sunset reservations, live room status and front-desk revenue control.",
        ).pack(fill="x", pady=(0, 18))
        stats = self.app.report_generator.dashboard_stats()

        # Top cards show the most important counts and revenue.
        cards = ttk.Frame(self)
        cards.pack(fill="x", pady=(0, 20))
        values = [
            ("Total Rooms", stats["rooms"], Theme.SIDEBAR_ACTIVE),
            ("Available", stats["available"], Theme.SUCCESS),
            ("Occupied", stats["occupied"], Theme.CORAL),
            ("Month Revenue", Theme.money(stats["monthly_revenue"]), Theme.GOLD),
            ("Total Arrivals", stats["total_arrivals"], Theme.ACCENT),
        ]
        for index, (title, value, accent) in enumerate(values):
            cards.columnconfigure(index, weight=1)
            StatCard(cards, title, str(value), accent).grid(row=0, column=index, sticky="ew", padx=(0 if index == 0 else 10, 0))

        # The lower area combines upcoming arrivals with visual room status.
        body = ttk.Frame(self)
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=2)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(1, weight=1)

        ttk.Label(body, text="Upcoming Arrivals", style="Section.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 8))
        self.arrivals = DataTable(
            body,
            [
                ("id", "ID", 60),
                ("guest", "Guest", 180),
                ("room", "Room", 90),
                ("check_in", "Check-in", 110),
                ("check_out", "Check-out", 110),
            ],
        )
        self.arrivals.grid(row=1, column=0, sticky="nsew", padx=(0, 18))
        self.arrivals.populate(self.app.report_generator.upcoming_arrivals())

        ttk.Label(body, text="Resort Highlight", style="Section.TLabel").grid(row=0, column=1, sticky="w", pady=(0, 8))
        right = ttk.Frame(body)
        right.grid(row=1, column=1, sticky="nsew")
        PhotoCard(
            right,
            "dashboard_room_card.png",
            "Premium Room View",
            "Bright guest rooms with balcony views support a polished front-desk presentation.",
        ).grid(row=0, column=0, columnspan=2, sticky="ew", padx=4, pady=(0, 10))

        ttk.Label(right, text="Room Status", style="Section.TLabel").grid(row=1, column=0, columnspan=2, sticky="w", padx=4, pady=(0, 6))
        rooms = self.app.daos.rooms.list(order_by="floor ASC, number ASC", limit=8)
        for index, room in enumerate(rooms):
            # Room cards are compact, so only the first few rooms are shown.
            card = RoomCard(right, dict(room))
            card.grid(row=2 + index // 2, column=index % 2, sticky="ew", padx=4, pady=4)
            right.columnconfigure(index % 2, weight=1)


class RoomsFrame(BaseFrame):
    """Room inventory screen."""

    def __init__(self, master, app) -> None:
        super().__init__(master, app=app)
        # Room inventory is where staff inspect availability and operations.
        self.page_title("Rooms", "Manage room inventory, availability and maintenance state.")
        actions = [
            ("Cleaning", self.assign_cleaning),
            ("Maintenance", self.open_maintenance),
        ]
        if self.app.is_admin():
            actions.insert(0, ("Add Room", self.add_room))
            actions.insert(1, ("Delete Room", self.delete_room))
        self.header = SearchHeader(self, "Search rooms", self.search, actions)
        self.header.pack(fill="x", pady=(0, 12))
        self.table = DataTable(
            self,
            [
                ("id", "ID", 60),
                ("number", "Number", 90),
                ("floor", "Floor", 70),
                ("room_type", "Type", 150),
                ("capacity", "Cap.", 80),
                ("base_price", "Base Price", 110),
                ("status", "Status", 120),
                ("amenities", "Amenities", 260),
            ],
        )
        self.table.pack(fill="both", expand=True)
        self.search("")

    def search(self, term: str) -> None:
        # Empty search shows every active room.
        term = term.strip()
        rows = self.app.daos.rooms.search(term) if term else self.app.daos.rooms.list(order_by="floor ASC, number ASC")
        self.table.populate(rows)

    def selected_room_id(self) -> int | None:
        # Most room actions need one selected table row.
        room_id = self.table.selected_id()
        if not room_id:
            ModalDialog.info("Select room", "Please select a room first.")
        return room_id

    def add_room(self) -> None:
        # Only admins can add inventory records.
        if not _require_admin(self.app):
            return
        RoomEditorDialog(self, self.app, on_saved=self.app.refresh_current)

    def delete_room(self) -> None:
        # Room deletion is guarded by the service layer.
        if not _require_admin(self.app):
            return
        room_id = self.selected_room_id()
        if not room_id:
            return
        if not ModalDialog.confirm("Delete room", "Delete the selected room?"):
            return
        try:
            self.app.room_inventory.delete_room(room_id, self.app.current_user_id())
            self.search("")
        except ValueError as exc:
            self.app.show_error(str(exc))

    def assign_cleaning(self) -> None:
        # Open the cleaning dialog for the selected room.
        room_id = self.selected_room_id()
        if room_id:
            HousekeepingDialog(self, self.app, on_saved=self.app.refresh_current, room_id=room_id)

    def open_maintenance(self) -> None:
        # Open the maintenance dialog for the selected room.
        room_id = self.selected_room_id()
        if room_id:
            MaintenanceDialog(self, self.app, on_saved=self.app.refresh_current, room_id=room_id)


class GuestsFrame(BaseFrame):
    """Guest registry screen."""

    def __init__(self, master, app) -> None:
        super().__init__(master, app=app)
        # Guest registry keeps contact and identity data searchable.
        self.page_title("Guests", "Register guests and keep contact information clean.")
        actions = [("Add Guest", self.add_guest)]
        if self.app.is_admin():
            actions.append(("Delete Guest", self.delete_guest))
        self.header = SearchHeader(self, "Search guests", self.search, actions)
        self.header.pack(fill="x", pady=(0, 12))
        self.table = DataTable(
            self,
            [
                ("id", "ID", 60),
                ("national_id", "National ID", 120),
                ("full_name", "Full Name", 180),
                ("phone", "Phone", 150),
                ("email", "Email", 220),
                ("address", "Address", 220),
            ],
        )
        self.table.pack(fill="both", expand=True)
        self.search("")

    def search(self, term: str) -> None:
        # Empty search shows all active guests alphabetically.
        term = term.strip()
        rows = self.app.daos.guests.search(term) if term else self.app.daos.guests.list(order_by="full_name ASC")
        self.table.populate(rows)

    def add_guest(self) -> None:
        # Guest creation is available to front desk staff.
        GuestEditorDialog(self, self.app, on_saved=self.app.refresh_current)

    def selected_guest_id(self) -> int | None:
        # Delete needs a selected guest row.
        guest_id = self.table.selected_id()
        if not guest_id:
            ModalDialog.info("Select guest", "Please select a guest first.")
        return guest_id

    def delete_guest(self) -> None:
        # Admins can remove guests when no active reservation blocks it.
        if not _require_admin(self.app):
            return
        guest_id = self.selected_guest_id()
        if not guest_id:
            return
        if not ModalDialog.confirm("Delete guest", "Delete the selected guest?"):
            return
        try:
            self.app.guest_registry.delete(guest_id)
            self.search("")
        except ValueError as exc:
            self.app.show_error(str(exc))


class ReservationsFrame(BaseFrame):
    """Reservation workflow screen."""

    def __init__(self, master, app) -> None:
        super().__init__(master, app=app)
        self._reservation_form: ReservationForm | None = None
        # Reservations are split into active work and historical records.
        self.page_title("Reservations", "Create bookings and manage check-in, check-out and cancellation.")
        toolbar = ttk.Frame(self, style="Toolbar.TFrame")
        toolbar.pack(fill="x", pady=(0, 12))
        ModernButton(toolbar, "New Reservation", self.new_reservation, variant="primary", width=148).pack(side="left")
        ModernButton(toolbar, "Check In", self.check_in, variant="secondary", width=104).pack(side="left", padx=(8, 0))
        ModernButton(toolbar, "Check Out", self.check_out, variant="secondary", width=110).pack(side="left", padx=(8, 0))
        ModernButton(toolbar, "Cancel Selected", self.cancel, variant="danger", width=138).pack(side="left", padx=(8, 0))

        ttk.Label(self, text="Active Reservations", style="Section.TLabel").pack(anchor="w", pady=(0, 8))
        columns = [
            ("id", "ID", 60),
            ("guest", "Guest", 180),
            ("room", "Room", 80),
            ("check_in", "Check-in", 110),
            ("check_out", "Check-out", 110),
            ("adults", "Adults", 80),
            ("children", "Children", 80),
            ("status", "Status", 120),
            ("total", "Total", 120),
        ]
        self.active_table = DataTable(
            self,
            columns,
            on_select=lambda _item_id: self.history_table.clear_selection(),
        )
        self.active_table.pack(fill="both", expand=True, pady=(0, 14))
        self.table = self.active_table

        ttk.Label(self, text="Reservation History", style="Section.TLabel").pack(anchor="w", pady=(0, 8))
        self.history_table = DataTable(
            self,
            columns,
            on_select=lambda _item_id: self.active_table.clear_selection(),
        )
        self.history_table.pack(fill="both", expand=True)
        self.load()

    def load(self) -> None:
        # Reload both active and history tables from the database.
        self.active_table.populate(self.app.daos.reservations.active_detailed())
        self.history_table.populate(self.app.daos.reservations.history_detailed())

    def selected_reservation_id(self) -> int | None:
        # Check-in, checkout and cancel work only on active reservations.
        reservation_id = self.active_table.selected_id()
        if not reservation_id:
            ModalDialog.info("Select reservation", "Please select an active reservation first.")
        return reservation_id

    def new_reservation(self) -> None:
        # Reuse the open reservation form instead of opening duplicates.
        if self._reservation_form and self._reservation_form.winfo_exists():
            self._reservation_form.tkraise()
            self._reservation_form.focus_first()
            return
        self._reservation_form = ReservationForm(
            self,
            self.app,
            on_saved=self._reservation_saved,
            on_closed=self._reservation_closed,
        )
        self._reservation_form.focus_first()

    def _reservation_saved(self, reservation_id: int) -> None:
        # After save, refresh tables and confirm the new reservation ID.
        self.load()
        self.app.show_info(f"Reservation #{reservation_id} created.")

    def _reservation_closed(self) -> None:
        # Forget the form reference after the dialog closes.
        self._reservation_form = None

    def check_in(self) -> None:
        # Check-in delegates rules to the booking engine.
        reservation_id = self.selected_reservation_id()
        if reservation_id:
            try:
                self.app.booking_engine.check_in(reservation_id, self.app.current_user_id())
                self.load()
            except ValueError as exc:
                self.app.show_error(str(exc))

    def check_out(self) -> None:
        # Checkout asks which housekeeper should clean the room next.
        reservation_id = self.selected_reservation_id()
        if reservation_id:
            CheckoutCleaningDialog(self, self.app, reservation_id, on_saved=self.load)

    def cancel(self) -> None:
        # Cancellation is confirmed before changing reservation state.
        reservation_id = self.selected_reservation_id()
        if reservation_id and ModalDialog.confirm("Cancel reservation", "Cancel the selected reservation?"):
            self.app.booking_engine.cancel(reservation_id, self.app.current_user_id())
            self.load()


class BillingFrame(BaseFrame):
    """Invoice and payment screen."""

    def __init__(self, master, app) -> None:
        super().__init__(master, app=app)
        # Billing shows invoice balances and the selected invoice's payments.
        self.page_title("Billing", "Track invoices, partial payments and remaining balances.")
        toolbar = ttk.Frame(self, style="Toolbar.TFrame")
        toolbar.pack(fill="x", pady=(0, 12))
        ModernButton(toolbar, "Record Payment", self.record_payment, variant="primary", width=142).pack(side="left")
        ModernButton(toolbar, "Refresh", self.load, variant="secondary", width=96).pack(side="left", padx=(8, 0))
        self.table = DataTable(
            self,
            [
                ("id", "Invoice", 80),
                ("reservation_id", "Reservation", 90),
                ("guest", "Guest", 180),
                ("room", "Room", 80),
                ("subtotal", "Subtotal", 110),
                ("discount", "Discount", 100),
                ("tax", "Tax", 90),
                ("total", "Total", 110),
                ("paid", "Paid", 110),
                ("balance", "Balance", 110),
                ("status", "Status", 100),
            ],
            on_select=self.load_payments,
        )
        self.table.pack(fill="both", expand=True, pady=(0, 12))
        ttk.Label(self, text="Payment History", style="Section.TLabel").pack(anchor="w", pady=(0, 8))
        self.payment_table = DataTable(
            self,
            [
                ("id", "Payment", 80),
                ("paid_at", "Date", 160),
                ("method", "Method", 130),
                ("amount", "Amount", 110),
                ("reference", "Reference", 220),
            ],
        )
        self.payment_table.pack(fill="both", expand=True)
        self.load()

    def load(self) -> None:
        # Reload invoices and clear payment history until a row is selected.
        self.table.populate(self.app.daos.invoices.detailed())
        self.payment_table.populate([])

    def load_payments(self, invoice_id: int | None) -> None:
        # Selecting an invoice fills the lower payment history table.
        rows = self.app.daos.payments.by_invoice(invoice_id) if invoice_id else []
        invoice = self.app.daos.invoices.get(invoice_id) if invoice_id else None
        if invoice and invoice["status"] == "cancelled" and not rows:
            rows = [
                {
                    "id": "-",
                    "paid_at": "",
                    "method": "Cancelled",
                    "amount": "",
                    "reference": "Reservation cancelled before check-in; no payment to refund",
                }
            ]
        self.payment_table.populate(rows)

    def record_payment(self) -> None:
        # Payment entry starts from the selected invoice row.
        invoice_id = self.table.selected_id()
        if not invoice_id:
            ModalDialog.info("Select invoice", "Please select an invoice first.")
            return
        PaymentDialog(self, self.app, invoice_id, on_saved=lambda: self._payment_saved(invoice_id))

    def _payment_saved(self, invoice_id: int) -> None:
        # Refresh both tables after a successful payment.
        self.load()
        self.load_payments(invoice_id)


class OperationsFrame(BaseFrame):
    """Housekeeping and maintenance operations."""

    def __init__(self, master, app) -> None:
        super().__init__(master, app=app)
        # Operations groups cleaning tasks and repair tickets on one page.
        self.page_title("Operations", "Coordinate cleaning tasks and maintenance tickets.")
        grid = ttk.Frame(self)
        grid.pack(fill="both", expand=True)
        grid.columnconfigure(0, weight=1)
        grid.rowconfigure(1, weight=1)
        grid.rowconfigure(3, weight=1)

        left_toolbar = ttk.Frame(grid, style="Toolbar.TFrame")
        left_toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        ttk.Label(left_toolbar, text="Housekeeping", style="Section.TLabel").pack(side="left")
        ModernButton(left_toolbar, "Complete Task", self.complete_task, variant="secondary", width=132).pack(side="right")
        ModernButton(left_toolbar, "Assign Cleaning", self.assign_cleaning, variant="primary", width=136).pack(side="right", padx=(0, 8))
        self.housekeeping_table = DataTable(
            grid,
            [
                ("id", "ID", 45),
                ("room", "Room", 60),
                ("assigned_to", "Employee", 150),
                ("task_type", "Task", 140),
                ("status", "Status", 120),
                ("notes", "Notes", 320),
            ],
            on_select=lambda _item_id: self.maintenance_table.clear_selection(),
        )
        self.housekeeping_table.grid(row=1, column=0, sticky="nsew")

        right_toolbar = ttk.Frame(grid, style="Toolbar.TFrame")
        right_toolbar.grid(row=2, column=0, sticky="ew", pady=(14, 8))
        ttk.Label(right_toolbar, text="Maintenance", style="Section.TLabel").pack(side="left")
        ModernButton(right_toolbar, "Open Ticket", self.open_ticket, variant="primary", width=112).pack(side="right")
        ModernButton(right_toolbar, "Close Ticket", self.complete_task, variant="secondary", width=120).pack(side="right", padx=(0, 8))
        self.maintenance_table = DataTable(
            grid,
            [
                ("id", "ID", 45),
                ("room", "Room", 60),
                ("assigned_to", "Employee", 140),
                ("issue", "Issue", 360),
                ("priority", "Priority", 120),
                ("status", "Status", 120),
            ],
            on_select=lambda _item_id: self.housekeeping_table.clear_selection(),
        )
        self.maintenance_table.grid(row=3, column=0, sticky="nsew")
        self.load()

    def load(self) -> None:
        # Reload both operational queues from their detailed DAO queries.
        self.housekeeping_table.populate(self.app.daos.housekeeping.detailed())
        self.maintenance_table.populate(self.app.daos.maintenance.detailed())

    def complete_task(self) -> None:
        # Complete whichever operations row is currently selected.
        task_id = self.housekeeping_table.selected_id()
        ticket_id = self.maintenance_table.selected_id()
        if not task_id and not ticket_id:
            ModalDialog.info("Select task", "Please select a housekeeping or maintenance task first.")
            return
        try:
            if task_id:
                self.app.housekeeping_service.complete_task(task_id, self.app.current_user_id())
            else:
                self.app.maintenance_service.close_ticket(ticket_id, self.app.current_user_id())
            self.load()
        except ValueError as exc:
            self.app.show_error(str(exc))

    def assign_cleaning(self) -> None:
        # Open a cleaning assignment without a preselected room.
        HousekeepingDialog(self, self.app, on_saved=self.load)

    def open_ticket(self) -> None:
        # Open a maintenance ticket without a preselected room.
        MaintenanceDialog(self, self.app, on_saved=self.load)


class ReportsFrame(BaseFrame):
    """Report screen."""

    def __init__(self, master, app) -> None:
        super().__init__(master, app=app)
        # Reports are text-based summaries for quick review.
        self.page_title("Reports", "Financial and occupancy summaries.")
        self.text = tk.Text(self, height=20, bg=Theme.SURFACE, fg=Theme.TEXT, relief="flat", padx=16, pady=14, font=("Consolas", 10))
        self.text.pack(fill="both", expand=True)
        self.load()

    def load(self) -> None:
        # Pull every report section from the read-only report generator.
        stats = self.app.report_generator.dashboard_stats()
        occupancy = self.app.report_generator.occupancy_by_type()
        revenue = self.app.report_generator.revenue_summary()
        methods = self.app.report_generator.payment_method_summary()
        lines = [
            "Hotel Reservation System Report",
            "",
            f"Total rooms: {stats['rooms']}",
            f"Available rooms: {stats['available']}",
            f"Occupied rooms: {stats['occupied']}",
            f"Current month revenue: {Theme.money(stats['monthly_revenue'])}",
            f"Total checked-in arrivals: {stats['total_arrivals']}",
            "",
            "Occupancy by type:",
        ]
        for row in occupancy:
            # Calculate the percentage in Python to keep the SQL simple.
            total = int(row["total"])
            occupied = int(row["occupied"] or 0)
            ratio = (occupied / total * 100) if total else 0
            lines.append(f"- {row['room_type']}: {occupied}/{total} occupied ({ratio:.1f}%)")
        lines.append("")
        lines.append("Last revenue days:")
        if revenue:
            for row in revenue:
                lines.append(f"- {row['day']}: {Theme.money(row['revenue'])}")
        else:
            lines.append("- No payment data yet.")
        lines.append("")
        lines.append("Revenue by payment method:")
        if methods:
            for row in methods:
                lines.append(f"- {row['method']}: {row['payments']} payments, {Theme.money(row['revenue'])}")
        else:
            lines.append("- No payment method data yet.")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", "\n".join(lines))


class StaffFrame(BaseFrame):
    """Operational employee management screen."""

    def __init__(self, master, app) -> None:
        super().__init__(master, app=app)
        # Staff records are split by the type of work they can receive.
        self.page_title("Employees", "Create housekeeping and maintenance employees for room operations.")
        toolbar = ttk.Frame(self, style="Toolbar.TFrame")
        toolbar.pack(fill="x", pady=(0, 12))
        ModernButton(toolbar, "Add Employee", self.add_staff, variant="primary", width=128).pack(side="left")
        ModernButton(toolbar, "Delete Employee", self.delete_staff, variant="danger", width=142).pack(side="left", padx=(8, 0))

        grid = ttk.Frame(self)
        grid.pack(fill="both", expand=True)
        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)
        grid.rowconfigure(1, weight=1)
        ttk.Label(grid, text="Housekeeping", style="Section.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 10), pady=(0, 8))
        ttk.Label(grid, text="Maintenance", style="Section.TLabel").grid(row=0, column=1, sticky="w", padx=(10, 0), pady=(0, 8))

        columns = [
            ("id", "ID", 60),
            ("employee_number", "Employee ID", 120),
            ("national_id", "National ID", 120),
            ("first_name", "First Name", 130),
            ("last_name", "Last Name", 130),
            ("availability_status", "Status", 90),
        ]
        self.housekeeping_table = DataTable(
            grid,
            columns,
            on_select=lambda _item_id: self.maintenance_table.clear_selection(),
        )
        self.housekeeping_table.grid(row=1, column=0, sticky="nsew", padx=(0, 10))
        self.maintenance_table = DataTable(
            grid,
            columns,
            on_select=lambda _item_id: self.housekeeping_table.clear_selection(),
        )
        self.maintenance_table.grid(row=1, column=1, sticky="nsew", padx=(10, 0))
        self.load()

    def load(self) -> None:
        # Each table shows one operational staff type.
        self.housekeeping_table.populate(self.app.daos.staff_members.list_by_type(StaffType.HOUSEKEEPING))
        self.maintenance_table.populate(self.app.daos.staff_members.list_by_type(StaffType.MAINTENANCE))

    def add_staff(self) -> None:
        # Create a new housekeeping or maintenance employee.
        StaffDialog(self, self.app, on_saved=self.load)

    def selected_staff_id(self) -> int | None:
        # Delete can come from either staff table.
        staff_id = self.housekeeping_table.selected_id() or self.maintenance_table.selected_id()
        if not staff_id:
            ModalDialog.info("Select employee", "Please select an employee first.")
        return staff_id

    def delete_staff(self) -> None:
        # The service blocks deletion when the employee has open work.
        staff_id = self.selected_staff_id()
        if not staff_id:
            return
        if not ModalDialog.confirm("Delete employee", "Delete the selected employee?"):
            return
        try:
            self.app.staff_member_service.delete(staff_id)
            self.load()
        except ValueError as exc:
            self.app.show_error(str(exc))


class BaseDialog(tk.Toplevel):
    """Base dialog with reliable close behavior and modal focus."""

    def __init__(
        self,
        master,
        app,
        title: str,
        on_saved: Callable[[], None] | None = None,
        on_closed: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(master)
        # Dialogs share the same modal lifecycle and centering behavior.
        self.app = app
        self.on_saved = on_saved
        self.on_closed = on_closed
        self._parent_window = master.winfo_toplevel()
        self._is_closing = False
        self.title(title)
        self.resizable(False, False)
        self.transient(self._parent_window)
        self.protocol("WM_DELETE_WINDOW", self.cancel)
        self.bind("<Escape>", self.cancel)
        self.after_idle(self._activate)

    def _activate(self) -> None:
        # Activate after layout so geometry calculations are accurate.
        if not self.winfo_exists():
            return
        self.update_idletasks()
        self._center_over_parent()
        self.lift()
        self.grab_set()
        self.focus_set()

    def _center_over_parent(self) -> None:
        # Center the dialog over the main application window.
        parent_width = max(self._parent_window.winfo_width(), 1)
        parent_height = max(self._parent_window.winfo_height(), 1)
        x = self._parent_window.winfo_rootx() + max((parent_width - self.winfo_width()) // 2, 0)
        y = self._parent_window.winfo_rooty() + max((parent_height - self.winfo_height()) // 2, 0)
        self.geometry(f"+{x}+{y}")

    def cancel(self, _event=None) -> str:
        # Escape and window close both use the same safe close path.
        self.close()
        return "break"

    def close(self) -> None:
        # Release modal grab before destroying the dialog.
        if self._is_closing:
            return
        self._is_closing = True
        on_closed = self.on_closed
        try:
            if self.grab_current() is self:
                self.grab_release()
        except tk.TclError:
            pass
        self.destroy()
        if on_closed:
            on_closed()

    def finish(self) -> None:
        # Close first, then let callers refresh their screen.
        on_saved = self.on_saved
        self.close()
        if on_saved:
            on_saved()

    def body(self, padding: int = 24) -> ttk.Frame:
        # Dialog content uses a white surface to stand apart from the page.
        self.configure(bg=Theme.SURFACE)
        frame = ttk.Frame(self, style="Dialog.TFrame", padding=padding)
        frame.pack(fill="both", expand=True)
        return frame


def RoomEditorDialog(master, app, on_saved: Callable[[], None]):
    # Dialog for adding or restoring a room in inventory.
    dialog = BaseDialog(master, app, "Add Room", on_saved)
    frame = dialog.body()
    dialog.number = tk.StringVar()
    dialog.floor = tk.StringVar(value="1")
    dialog.room_type = tk.StringVar(value="Standard")
    dialog.capacity = tk.StringVar(value="2")
    dialog.price = tk.StringVar(value="1800")
    dialog.status = tk.StringVar(value=RoomStatus.AVAILABLE)
    dialog.amenities = tk.StringVar(value="Wi-Fi, TV")
    _entry(frame, "Room number", dialog.number, 0)
    _entry(frame, "Floor", dialog.floor, 1)
    _combobox(frame, "Room type", dialog.room_type, 2, ROOM_TYPE_CHOICES)
    _entry(frame, "Capacity", dialog.capacity, 3)
    _entry(frame, "Base price", dialog.price, 4)
    _combobox(frame, "Status", dialog.status, 5, RoomStatus.MANUAL_CHOICES)
    _entry(frame, "Amenities", dialog.amenities, 6)
    frame.columnconfigure(1, weight=1)

    def save() -> None:
        # Validate form values before sending them to the room service.
        try:
            app.room_inventory.add_room(
                {
                    "number": dialog.number.get().strip(),
                    "floor": _required_int(dialog.floor.get(), "Floor", 1),
                    "room_type": dialog.room_type.get(),
                    "capacity": _required_int(dialog.capacity.get(), "Capacity", 1),
                    "base_price": _required_float(dialog.price.get(), "Base price", 0.01),
                    "status": dialog.status.get(),
                    "amenities": dialog.amenities.get().strip(),
                }
            )
            dialog.finish()
        except Exception as exc:
            app.show_error(str(exc))

    dialog.save = save
    _dialog_actions(frame, 7, "Save Room", dialog.save, dialog.cancel)
    return dialog


def GuestEditorDialog(master, app, on_saved: Callable[[], None]):
    # Dialog for creating a guest profile.
    dialog = BaseDialog(master, app, "Add Guest", on_saved)
    frame = dialog.body()
    dialog.national_id = tk.StringVar()
    dialog.full_name = tk.StringVar()
    dialog.phone = tk.StringVar()
    dialog.email = tk.StringVar()
    dialog.address = tk.StringVar()
    _entry(frame, "National ID", dialog.national_id, 0)
    _entry(frame, "Full name", dialog.full_name, 1)
    _entry(frame, "Phone", dialog.phone, 2)
    _entry(frame, "Email", dialog.email, 3)
    _entry(frame, "Address", dialog.address, 4)
    frame.columnconfigure(1, weight=1)

    def save() -> None:
        # Guest service handles validation and duplicate national IDs.
        try:
            app.guest_registry.register(
                {
                    "national_id": dialog.national_id.get().strip(),
                    "full_name": dialog.full_name.get().strip(),
                    "phone": dialog.phone.get().strip(),
                    "email": dialog.email.get().strip(),
                    "address": dialog.address.get().strip(),
                }
            )
            dialog.finish()
        except Exception as exc:
            app.show_error(str(exc))

    dialog.save = save
    _dialog_actions(frame, 5, "Save Guest", dialog.save, dialog.cancel)
    return dialog


def ReservationForm(master, app, on_saved: Callable[[int], None], on_closed: Callable[[], None]):
    # Dialog for creating a new reservation and invoice together.
    dialog = BaseDialog(master, app, "New Reservation", on_saved=None, on_closed=on_closed)
    frame = dialog.body()
    today = date.today()
    dialog.guest = tk.StringVar()
    dialog.room = tk.StringVar()
    dialog.check_in = tk.StringVar(value=today.isoformat())
    dialog.check_out = tk.StringVar(value=(today + timedelta(days=1)).isoformat())
    dialog.adults = tk.StringVar(value="2")
    dialog.children_count = tk.StringVar(value="0")
    dialog.discount = tk.StringVar(value="0")
    dialog.notes = tk.StringVar()
    guests = [f"{row['id']} - {row['full_name']}" for row in app.daos.guests.list(order_by="full_name ASC")]
    rooms = [
        # Only book rooms that are not blocked by status.
        f"{row['id']} - {row['number']} {row['room_type']} ({row['status']})"
        for row in app.daos.rooms.list(order_by="floor ASC, number ASC")
        if row["status"] not in RoomStatus.BOOKING_BLOCKED
    ]
    first_widget = _combobox(frame, "Guest", dialog.guest, 0, guests, width=42)
    _combobox(frame, "Room", dialog.room, 1, rooms, width=42)
    _entry(frame, "Check-in", dialog.check_in, 2)
    _entry(frame, "Check-out", dialog.check_out, 3)
    _entry(frame, "Adults", dialog.adults, 4)
    _entry(frame, "Children", dialog.children_count, 5)
    _entry(frame, "Discount", dialog.discount, 6)
    _entry(frame, "Notes", dialog.notes, 7)
    frame.columnconfigure(1, weight=1)
    if guests:
        dialog.guest.set(guests[0])
    if rooms:
        dialog.room.set(rooms[0])
    dialog.focus_first = lambda: first_widget.focus_set()

    def save() -> None:
        # Booking engine owns availability, pricing and invoice creation.
        try:
            reservation_id = app.booking_engine.create_reservation(
                guest_id=_required_selected_int(dialog.guest.get(), "a guest"),
                room_id=_required_selected_int(dialog.room.get(), "a room"),
                check_in=dialog.check_in.get(),
                check_out=dialog.check_out.get(),
                adults=_required_int(dialog.adults.get(), "Adults", 1),
                children=_required_int(dialog.children_count.get(), "Children", 0),
                notes=dialog.notes.get().strip(),
                created_by=app.current_user_id(),
                discount=_required_float(dialog.discount.get(), "Discount", 0.0),
            )
            dialog.close()
            on_saved(reservation_id)
        except Exception as exc:
            app.show_error(str(exc))

    dialog.save = save
    _dialog_actions(frame, 8, "Create Reservation", dialog.save, dialog.cancel)
    return dialog


def PaymentDialog(master, app, invoice_id: int, on_saved: Callable[[], None]):
    # Dialog for recording a payment against one invoice.
    dialog = BaseDialog(master, app, "Record Payment", on_saved)
    frame = dialog.body()
    dialog.amount = tk.StringVar()
    dialog.method = tk.StringVar(value="Cash")
    dialog.reference = tk.StringVar()
    _entry(frame, "Amount", dialog.amount, 0)
    _combobox(frame, "Method", dialog.method, 1, AppSettings.PAYMENT_METHODS)
    _entry(frame, "Reference", dialog.reference, 2)
    frame.columnconfigure(1, weight=1)

    def save() -> None:
        # Payment service prevents overpayment and updates invoice status.
        try:
            app.payment_service.record_payment(
                invoice_id,
                _required_float(dialog.amount.get(), "Amount", 0.01),
                dialog.method.get(),
                dialog.reference.get().strip(),
                app.current_user_id(),
            )
            dialog.finish()
        except Exception as exc:
            app.show_error(str(exc))

    dialog.save = save
    _dialog_actions(frame, 3, "Save Payment", dialog.save, dialog.cancel)
    return dialog


def CheckoutCleaningDialog(master, app, reservation_id: int, on_saved: Callable[[], None]):
    # Checkout asks for the employee who will receive the cleaning task.
    dialog = BaseDialog(master, app, "Assign Checkout Cleaning", on_saved)
    frame = dialog.body()
    dialog.staff = tk.StringVar()
    staff = [_staff_option(row) for row in app.daos.staff_members.available_for(StaffType.HOUSEKEEPING)]
    _combobox(frame, "Housekeeping employee", dialog.staff, 0, staff, width=42)
    frame.columnconfigure(1, weight=1)
    if staff:
        dialog.staff.set(staff[0])

    def save() -> None:
        # Checkout requires full payment before this service call succeeds.
        try:
            app.booking_engine.check_out(
                reservation_id,
                app.current_user_id(),
                _required_selected_int(dialog.staff.get(), "an available housekeeping employee"),
            )
            dialog.finish()
        except Exception as exc:
            app.show_error(str(exc))

    dialog.save = save
    _dialog_actions(frame, 1, "Check Out", dialog.save, dialog.cancel)
    return dialog


def HousekeepingDialog(master, app, on_saved: Callable[[], None], room_id: int | None = None):
    # Dialog for assigning a housekeeping task to a room.
    dialog = BaseDialog(master, app, "Assign Cleaning Task", on_saved)
    frame = dialog.body()
    dialog.room = tk.StringVar()
    dialog.staff = tk.StringVar()
    dialog.task_type = tk.StringVar(value="standard_clean")
    dialog.notes = tk.StringVar()
    rooms = [f"{row['id']} - {row['number']} {row['room_type']}" for row in app.daos.rooms.list(order_by="floor ASC, number ASC")]
    staff = [_staff_option(row) for row in app.daos.staff_members.available_for(StaffType.HOUSEKEEPING)]
    _combobox(frame, "Room", dialog.room, 0, rooms, width=42)
    _combobox(frame, "Housekeeping employee", dialog.staff, 1, staff, width=42)
    _combobox(frame, "Task type", dialog.task_type, 2, ["standard_clean", "checkout_clean", "deep_clean"])
    _entry(frame, "Notes", dialog.notes, 3, width=42)
    frame.columnconfigure(1, weight=1)
    dialog.room.set(_select_option(rooms, room_id))
    dialog.staff.set(_select_option(staff))

    def save() -> None:
        # The housekeeping service updates the room status to cleaning.
        try:
            app.housekeeping_service.assign_task(
                _required_selected_int(dialog.room.get(), "a room"),
                _required_selected_int(dialog.staff.get(), "an available housekeeping employee"),
                dialog.task_type.get(),
                dialog.notes.get().strip(),
                app.current_user_id(),
            )
            dialog.finish()
        except Exception as exc:
            app.show_error(str(exc))

    dialog.save = save
    _dialog_actions(frame, 4, "Assign Cleaning", dialog.save, dialog.cancel)
    return dialog


def MaintenanceDialog(master, app, on_saved: Callable[[], None], room_id: int | None = None):
    # Dialog for opening a maintenance ticket.
    dialog = BaseDialog(master, app, "Open Maintenance Ticket", on_saved)
    frame = dialog.body()
    dialog.room = tk.StringVar()
    dialog.staff = tk.StringVar()
    dialog.issue = tk.StringVar()
    dialog.priority = tk.StringVar(value="medium")
    rooms = [f"{row['id']} - {row['number']} {row['room_type']}" for row in app.daos.rooms.list(order_by="floor ASC, number ASC")]
    staff = [_staff_option(row) for row in app.daos.staff_members.available_for(StaffType.MAINTENANCE)]
    _combobox(frame, "Room", dialog.room, 0, rooms, width=42)
    _combobox(frame, "Maintenance employee", dialog.staff, 1, staff, width=42)
    _entry(frame, "Issue", dialog.issue, 2, width=42)
    _combobox(frame, "Priority", dialog.priority, 3, ["low", "medium", "high", "critical"])
    frame.columnconfigure(1, weight=1)
    dialog.room.set(_select_option(rooms, room_id))
    dialog.staff.set(_select_option(staff))

    def save() -> None:
        # The maintenance service assigns staff and blocks the room.
        try:
            app.maintenance_service.open_ticket(
                _required_selected_int(dialog.room.get(), "a room"),
                dialog.issue.get().strip(),
                dialog.priority.get(),
                app.current_user_id(),
                assigned_staff_id=_required_selected_int(dialog.staff.get(), "an available maintenance employee"),
            )
            dialog.finish()
        except Exception as exc:
            app.show_error(str(exc))

    dialog.save = save
    _dialog_actions(frame, 4, "Open Ticket", dialog.save, dialog.cancel)
    return dialog


def StaffDialog(master, app, on_saved: Callable[[], None]):
    # Dialog for adding an operational employee.
    dialog = BaseDialog(master, app, "Add Employee", on_saved)
    frame = dialog.body()
    dialog.employee_number = tk.StringVar()
    dialog.national_id = tk.StringVar()
    dialog.first_name = tk.StringVar()
    dialog.last_name = tk.StringVar()
    dialog.staff_type = tk.StringVar(value=StaffType.HOUSEKEEPING)
    _entry(frame, "Employee ID", dialog.employee_number, 0)
    _entry(frame, "National ID", dialog.national_id, 1)
    _entry(frame, "First name", dialog.first_name, 2)
    _entry(frame, "Last name", dialog.last_name, 3)
    _combobox(frame, "Employee type", dialog.staff_type, 4, list(StaffType.ALL))
    frame.columnconfigure(1, weight=1)

    def save() -> None:
        # Staff service checks identity fields and duplicate values.
        try:
            app.staff_member_service.register(
                {
                    "employee_number": dialog.employee_number.get().strip(),
                    "national_id": dialog.national_id.get().strip(),
                    "first_name": dialog.first_name.get().strip(),
                    "last_name": dialog.last_name.get().strip(),
                    "staff_type": dialog.staff_type.get(),
                }
            )
            dialog.finish()
        except Exception as exc:
            app.show_error(str(exc))

    dialog.save = save
    _dialog_actions(frame, 5, "Create Employee", dialog.save, dialog.cancel)
    return dialog
