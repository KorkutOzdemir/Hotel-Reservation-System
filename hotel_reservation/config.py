"""Application configuration values."""

from pathlib import Path
from types import SimpleNamespace


ROOT_DIR = Path(__file__).resolve().parents[1]

# AppSettings keeps project-wide constants in one easy-to-find place.
AppSettings = SimpleNamespace(
    APP_NAME="Grand Vista Hotel Reservation System",
    VERSION="1.0.0",
    ROOT_DIR=ROOT_DIR,
    ASSET_DIR=ROOT_DIR / "assets",
    DATA_DIR=ROOT_DIR / "data",
    DOCS_DIR=ROOT_DIR / "docs",
    DB_PATH=ROOT_DIR / "data" / "hotel_reservation.sqlite3",
    TAX_RATE=0.08,
    WEEKEND_MULTIPLIER=1.25,
    CHILD_PRICE_MULTIPLIER=0.5,
    PAYMENT_METHODS=("Cash", "Credit Card", "Bank Transfer", "Online"),
    DEFAULT_ADMIN_USERNAME="admin",
    DEFAULT_ADMIN_PASSWORD="admin123",
    DEFAULT_STAFF_USERNAME="frontdesk",
    DEFAULT_STAFF_PASSWORD="frontdesk123",
    DATE_FORMAT="%Y-%m-%d",
)

# Room status values are shared by booking, housekeeping and maintenance.
RoomStatus = SimpleNamespace(
    AVAILABLE="available",
    OCCUPIED="occupied",
    CLEANING="cleaning",
    MAINTENANCE="maintenance",
)
RoomStatus.ALL = (RoomStatus.AVAILABLE, RoomStatus.OCCUPIED, RoomStatus.CLEANING, RoomStatus.MAINTENANCE)
RoomStatus.MANUAL_CHOICES = (RoomStatus.AVAILABLE, RoomStatus.CLEANING, RoomStatus.MAINTENANCE)
RoomStatus.BOOKING_BLOCKED = (RoomStatus.OCCUPIED, RoomStatus.CLEANING, RoomStatus.MAINTENANCE)

# Staff members are split by the type of operational work they can receive.
StaffType = SimpleNamespace(HOUSEKEEPING="housekeeping", MAINTENANCE="maintenance")
StaffType.ALL = (StaffType.HOUSEKEEPING, StaffType.MAINTENANCE)

# Reservation statuses describe the lifecycle from booking to checkout.
ReservationStatus = SimpleNamespace(
    CONFIRMED="confirmed",
    CHECKED_IN="checked_in",
    COMPLETED="completed",
    CANCELLED="cancelled",
)
ReservationStatus.ACTIVE = (ReservationStatus.CONFIRMED, ReservationStatus.CHECKED_IN)

# Invoice statuses control whether payments can still be recorded.
InvoiceStatus = SimpleNamespace(OPEN="open", PAID="paid", PARTIAL="partial", CANCELLED="cancelled")
InvoiceStatus.PAYABLE = (InvoiceStatus.OPEN, InvoiceStatus.PARTIAL)
