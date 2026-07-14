"""Main GUI application window."""

from __future__ import annotations

import tkinter as tk
import traceback
from types import SimpleNamespace

from hotel_reservation.config import AppSettings
from hotel_reservation.core.database import DatabaseManager
from hotel_reservation.core.schema import SchemaManager, SeedDataLoader
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
from hotel_reservation.gui.screens import (
    BillingFrame,
    DashboardFrame,
    GuestsFrame,
    OperationsFrame,
    ReportsFrame,
    ReservationsFrame,
    RoomsFrame,
    StaffFrame,
)
from hotel_reservation.gui.theme import Theme
from hotel_reservation.gui.widgets import LoginForm, ModalDialog, Sidebar
from hotel_reservation.services import (
    AppLogger,
    AuthService,
    BookingEngine,
    GuestRegistryService,
    HousekeepingService,
    MaintenanceService,
    PaymentService,
    PriceCalculator,
    ReportGenerator,
    RoomInventoryService,
    StaffMemberService,
)


class AppWindow(tk.Tk):
    """Main window that wires database, services and pages together."""

    # Page access rules keep staff users away from admin-only screens.
    PAGE_ACCESS = {
        "admin": (
            "dashboard",
            "rooms",
            "guests",
            "reservations",
            "billing",
            "operations",
            "reports",
            "staff",
        ),
        "staff": (
            "dashboard",
            "rooms",
            "guests",
            "reservations",
            "billing",
        ),
        "frontdesk": (
            "dashboard",
            "rooms",
            "guests",
            "reservations",
            "billing",
        ),
    }

    def __init__(self) -> None:
        super().__init__()
        # Window basics are set before building services or screens.
        self.title(AppSettings.APP_NAME)
        self.protocol("WM_DELETE_WINDOW", self.close_application)
        self.geometry("1280x760")
        self.minsize(1100, 680)
        Theme.apply(self)
        # Startup prepares the database and loads starter data if needed.
        self.db = DatabaseManager()
        SchemaManager(self.db).create_schema()
        SeedDataLoader(self.db).seed()
        self._build_services()
        self.current_user = None
        self.sidebar: Sidebar | None = None
        self.content_shell = None
        self.content = None
        self.active_page = ""
        self.show_login()

    def _build_services(self) -> None:
        # DAOs are shared so all services talk to the same database manager.
        self.daos = SimpleNamespace(
            users=UserDAO(self.db),
            rooms=RoomDAO(self.db),
            guests=GuestDAO(self.db),
            reservations=ReservationDAO(self.db),
            invoices=InvoiceDAO(self.db),
            payments=PaymentDAO(self.db),
            notifications=NotificationDAO(self.db),
            logs=ActivityLogDAO(self.db),
            housekeeping=HousekeepingTaskDAO(self.db),
            maintenance=MaintenanceTicketDAO(self.db),
            staff_members=StaffMemberDAO(self.db),
        )
        # Services hold business rules; screens call these instead of SQL.
        self.logger = AppLogger(self.daos.logs)
        self.auth_service = AuthService(self.daos.users)
        self.price_calculator = PriceCalculator()
        self.booking_engine = BookingEngine(
            self.db,
            self.daos.rooms,
            self.daos.reservations,
            self.daos.invoices,
            self.price_calculator,
            self.logger,
            self.daos.notifications,
            self.daos.housekeeping,
            self.daos.staff_members,
        )
        self.guest_registry = GuestRegistryService(self.daos.guests)
        self.staff_member_service = StaffMemberService(self.daos.staff_members)
        self.room_inventory = RoomInventoryService(self.daos.rooms, self.daos.maintenance, self.logger)
        self.payment_service = PaymentService(self.daos.invoices, self.daos.payments, self.logger)
        self.housekeeping_service = HousekeepingService(
            self.daos.housekeeping,
            self.daos.rooms,
            self.daos.staff_members,
            self.logger,
        )
        self.maintenance_service = MaintenanceService(
            self.daos.maintenance,
            self.daos.rooms,
            self.daos.staff_members,
            self.logger,
        )
        self.report_generator = ReportGenerator(self.db)

    def show_login(self) -> None:
        # Reset the whole window back to the login screen.
        self._clear_root()
        login = LoginForm(self, self)
        login.pack(fill="both", expand=True)

    def handle_login(self, username: str, password: str) -> None:
        # Login stores the current user row for role checks and audit logs.
        user = self.auth_service.authenticate(username, password)
        if not user:
            raise ValueError("Invalid username or password.")
        self.current_user = user
        self.logger.log("login", "user", user["id"], "GUI login", user["id"])
        self.show_shell()

    def show_shell(self) -> None:
        # The shell is the sidebar plus a content area for pages.
        self._clear_root()
        self.sidebar = Sidebar(self, self, dict(self.current_user))
        self.sidebar.pack(side="left", fill="y")
        self.content_shell = tk.Frame(self, bg=Theme.BG)
        self.content_shell.pack(side="left", fill="both", expand=True)
        self.content = tk.Frame(self.content_shell, bg=Theme.BG)
        self.content.pack(fill="both", expand=True)
        self.navigate("dashboard")

    def navigate(self, page: str) -> None:
        # Swap the content frame to the requested page.
        if not self.content:
            return
        if not self.can_access_page(page):
            self.show_error("This page is available to administrators only.", title="Access denied")
            return
        self.active_page = page
        if self.sidebar:
            self.sidebar.set_active(page)
        # Destroying old page widgets prevents stale forms from staying alive.
        for child in self.content.winfo_children():
            self._destroy_widget(child)
        pages = {
            "dashboard": DashboardFrame,
            "rooms": RoomsFrame,
            "guests": GuestsFrame,
            "reservations": ReservationsFrame,
            "billing": BillingFrame,
            "operations": OperationsFrame,
            "reports": ReportsFrame,
            "staff": StaffFrame,
        }
        frame_class = pages.get(page, DashboardFrame)
        frame = frame_class(self.content, app=self)
        frame.pack(fill="both", expand=True, padx=28, pady=24)

    def current_role(self) -> str:
        # Empty role means no user is currently logged in.
        return str(self.current_user["role"]) if self.current_user else ""

    def is_admin(self) -> bool:
        # Admin-only actions use this small helper.
        return self.current_role() == "admin"

    def allowed_pages(self) -> tuple[str, ...]:
        # Unknown roles fall back to the staff page set.
        return self.PAGE_ACCESS.get(self.current_role(), self.PAGE_ACCESS["staff"])

    def can_access_page(self, page: str) -> bool:
        # Navigation checks this before creating a page.
        return page in self.allowed_pages()

    def current_user_id(self) -> int | None:
        # Services use the user ID for logs and ownership fields.
        return int(self.current_user["id"]) if self.current_user else None

    def refresh_current(self) -> None:
        # Recreate the active page so tables reload fresh data.
        self.navigate(self.active_page or "dashboard")

    def logout(self) -> None:
        # Logging out clears the user and returns to the login form.
        if self.current_user:
            self.logger.log("logout", "user", self.current_user["id"], "GUI logout", self.current_user["id"])
        self.current_user = None
        self.show_login()

    def close_application(self) -> None:
        # Close cleanly so the SQLite connection is released.
        try:
            if self.current_user:
                self.logger.log("close", "application", None, "GUI window closed", self.current_user["id"])
        except Exception:
            pass
        try:
            self.db.close()
        except Exception:
            pass
        try:
            self.quit()
            self.tk.call("destroy", self._w)
        except tk.TclError:
            pass

    def show_error(self, message: str, title: str = "Error") -> None:
        # Keep error dialogs consistent across screens.
        ModalDialog.error(title, message)

    def show_info(self, message: str, title: str = "Info") -> None:
        # Keep info dialogs consistent across screens.
        ModalDialog.info(title, message)

    def _clear_root(self) -> None:
        # Remove every top-level widget before showing another root layout.
        for child in self.winfo_children():
            self._destroy_widget(child)
        self.sidebar = None
        self.content_shell = None
        self.content = None

    @staticmethod
    def _destroy_widget(widget) -> None:
        # Some Tk variable cleanup can raise harmless widget-like errors.
        try:
            widget.destroy()
        except AttributeError as exc:
            if "'StringVar' object has no attribute 'values'" not in str(exc):
                raise
            widget.tk.call("destroy", widget._w)

    def report_callback_exception(self, exc_type, exc_value, exc_traceback) -> None:
        # Show unexpected Tk callback errors instead of failing silently.
        details = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        try:
            self.show_error(details, title="Application Error")
        except Exception:
            print(details)
