"""Database schema creation and realistic seed data."""

from __future__ import annotations

from hotel_reservation.config import AppSettings, InvoiceStatus, ReservationStatus, RoomStatus, StaffType
from hotel_reservation.core.database import DatabaseManager


class SchemaManager:
    """Creates all SQLite tables and indexes."""

    def __init__(self, db: DatabaseManager) -> None:
        # The schema manager works with the shared application database.
        self.db = db

    def create_schema(self) -> None:
        # Tables are created with IF NOT EXISTS so startup is repeatable.
        statements = [
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                full_name TEXT NOT NULL,
                role TEXT NOT NULL,
                department TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS staff_members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_number TEXT NOT NULL UNIQUE,
                national_id TEXT NOT NULL UNIQUE,
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                staff_type TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                CHECK (staff_type IN ('housekeeping', 'maintenance'))
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS rooms (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                number TEXT NOT NULL UNIQUE,
                floor INTEGER NOT NULL,
                room_type TEXT NOT NULL,
                capacity INTEGER NOT NULL,
                base_price REAL NOT NULL,
                status TEXT NOT NULL DEFAULT 'available',
                amenities TEXT,
                is_deleted INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS guests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                national_id TEXT UNIQUE,
                full_name TEXT NOT NULL,
                phone TEXT NOT NULL,
                email TEXT,
                address TEXT,
                is_deleted INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS reservations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guest_id INTEGER NOT NULL,
                room_id INTEGER NOT NULL,
                check_in TEXT NOT NULL,
                check_out TEXT NOT NULL,
                adults INTEGER NOT NULL DEFAULT 1,
                children INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'confirmed',
                notes TEXT,
                created_by INTEGER,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (guest_id) REFERENCES guests(id) ON DELETE RESTRICT,
                FOREIGN KEY (room_id) REFERENCES rooms(id) ON DELETE RESTRICT,
                FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS invoices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                reservation_id INTEGER NOT NULL UNIQUE,
                subtotal REAL NOT NULL,
                tax REAL NOT NULL,
                discount REAL NOT NULL DEFAULT 0,
                total REAL NOT NULL,
                status TEXT NOT NULL DEFAULT 'open',
                due_date TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (reservation_id) REFERENCES reservations(id) ON DELETE CASCADE
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_id INTEGER NOT NULL,
                amount REAL NOT NULL,
                method TEXT NOT NULL,
                paid_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                reference TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (invoice_id) REFERENCES invoices(id) ON DELETE CASCADE
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS room_service_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                price REAL NOT NULL,
                category TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS room_service_orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                reservation_id INTEGER NOT NULL,
                item_id INTEGER NOT NULL,
                quantity INTEGER NOT NULL DEFAULT 1,
                status TEXT NOT NULL DEFAULT 'ordered',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (reservation_id) REFERENCES reservations(id) ON DELETE CASCADE,
                FOREIGN KEY (item_id) REFERENCES room_service_items(id) ON DELETE RESTRICT
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                title TEXT NOT NULL,
                message TEXT NOT NULL,
                is_read INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS activity_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                action TEXT NOT NULL,
                entity TEXT NOT NULL,
                entity_id INTEGER,
                details TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS housekeeping_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                room_id INTEGER NOT NULL,
                assigned_to INTEGER,
                assigned_staff_id INTEGER,
                task_type TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                notes TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (room_id) REFERENCES rooms(id) ON DELETE CASCADE,
                FOREIGN KEY (assigned_to) REFERENCES users(id) ON DELETE SET NULL,
                FOREIGN KEY (assigned_staff_id) REFERENCES staff_members(id) ON DELETE SET NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS maintenance_tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                room_id INTEGER NOT NULL,
                reported_by INTEGER,
                assigned_staff_id INTEGER,
                issue TEXT NOT NULL,
                priority TEXT NOT NULL DEFAULT 'medium',
                status TEXT NOT NULL DEFAULT 'open',
                opened_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                closed_at TEXT,
                FOREIGN KEY (room_id) REFERENCES rooms(id) ON DELETE CASCADE,
                FOREIGN KEY (reported_by) REFERENCES users(id) ON DELETE SET NULL,
                FOREIGN KEY (assigned_staff_id) REFERENCES staff_members(id) ON DELETE SET NULL
            )
            """,
        ]
        for statement in statements:
            self.db.execute(statement)

        # Small migrations keep older local databases compatible with new code.
        self._add_column_if_missing("housekeeping_tasks", "assigned_staff_id", "INTEGER")
        self._add_column_if_missing("maintenance_tickets", "assigned_staff_id", "INTEGER")
        self._add_column_if_missing("rooms", "is_deleted", "INTEGER NOT NULL DEFAULT 0")
        self._add_column_if_missing("guests", "is_deleted", "INTEGER NOT NULL DEFAULT 0")
        self._drop_housekeeping_due_date_column()

        # Indexes keep dashboard, search and status filters responsive.
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_reservations_dates ON reservations(room_id, check_in, check_out)",
            "CREATE INDEX IF NOT EXISTS idx_reservations_status ON reservations(status)",
            "CREATE INDEX IF NOT EXISTS idx_rooms_status ON rooms(status)",
            "CREATE INDEX IF NOT EXISTS idx_rooms_deleted_status ON rooms(is_deleted, status)",
            "CREATE INDEX IF NOT EXISTS idx_guests_deleted_name ON guests(is_deleted, full_name)",
            "CREATE INDEX IF NOT EXISTS idx_invoices_status ON invoices(status)",
            "CREATE INDEX IF NOT EXISTS idx_logs_created ON activity_logs(created_at)",
            "CREATE INDEX IF NOT EXISTS idx_staff_members_type_active ON staff_members(staff_type, is_active)",
            "CREATE INDEX IF NOT EXISTS idx_housekeeping_staff_status ON housekeeping_tasks(assigned_staff_id, status)",
            "CREATE INDEX IF NOT EXISTS idx_maintenance_staff_status ON maintenance_tickets(assigned_staff_id, status)",
        ]
        for statement in indexes:
            self.db.execute(statement)

    def _add_column_if_missing(self, table: str, column: str, definition: str) -> None:
        # SQLite has no ADD COLUMN IF NOT EXISTS, so we check first.
        columns = {row["name"] for row in self.db.query(f"PRAGMA table_info({table})")}
        if column not in columns:
            self.db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    def _drop_housekeeping_due_date_column(self) -> None:
        # Rebuild the table only if an old due_date column is still present.
        columns = {row["name"] for row in self.db.query("PRAGMA table_info(housekeeping_tasks)")}
        if "due_date" not in columns:
            return
        connection = self.db.connect()
        try:
            # SQLite table rebuilds need foreign keys off during the swap.
            connection.execute("PRAGMA foreign_keys=OFF")
            connection.execute("BEGIN")
            connection.execute(
                """
                CREATE TABLE housekeeping_tasks_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    room_id INTEGER NOT NULL,
                    assigned_to INTEGER,
                    assigned_staff_id INTEGER,
                    task_type TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    notes TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (room_id) REFERENCES rooms(id) ON DELETE CASCADE,
                    FOREIGN KEY (assigned_to) REFERENCES users(id) ON DELETE SET NULL,
                    FOREIGN KEY (assigned_staff_id) REFERENCES staff_members(id) ON DELETE SET NULL
                )
                """
            )
            connection.execute(
                """
                INSERT INTO housekeeping_tasks_new
                    (id, room_id, assigned_to, assigned_staff_id, task_type, status, notes, created_at, updated_at)
                SELECT id, room_id, assigned_to, assigned_staff_id, task_type, status, notes, created_at, updated_at
                FROM housekeeping_tasks
                """
            )
            connection.execute("DROP TABLE housekeeping_tasks")
            connection.execute("ALTER TABLE housekeeping_tasks_new RENAME TO housekeeping_tasks")
            connection.commit()
        except Exception:
            # Roll back the whole rebuild if any step fails.
            connection.rollback()
            raise
        finally:
            # Always restore foreign key checks for normal application work.
            connection.execute("PRAGMA foreign_keys=ON")


class SeedDataLoader:
    """Loads starter users, rooms, guests and operational data once."""

    def __init__(self, db: DatabaseManager) -> None:
        # Seed data uses the same database that the GUI will read from.
        self.db = db

    def seed(self) -> None:
        # Each seed step is idempotent, so app startup can safely call this.
        self._seed_users()
        self._reset_default_passwords()
        self._deactivate_legacy_housekeeping_login()
        self._seed_staff_members()
        self._seed_rooms()
        self._seed_extended_rooms()
        self._seed_guests()
        self._seed_service_items()
        self._seed_sample_reservation()
        self._seed_operations()

    def _table_is_empty(self, table: str) -> bool:
        # Most seed groups run only when their table has no rows yet.
        row = self.db.query_one(f"SELECT COUNT(*) AS total FROM {table}")
        return int(row["total"]) == 0

    def _seed_users(self) -> None:
        # Create the default admin and front desk users for first login.
        if not self._table_is_empty("users"):
            return
        rows = [
            (
                AppSettings.DEFAULT_ADMIN_USERNAME,
                AppSettings.DEFAULT_ADMIN_PASSWORD,
                "System Administrator",
                "admin",
                "Management",
            ),
            (
                AppSettings.DEFAULT_STAFF_USERNAME,
                AppSettings.DEFAULT_STAFF_PASSWORD,
                "Front Desk Staff",
                "staff",
                "Reception",
            ),
        ]
        self.db.executemany(
            """
            INSERT INTO users (username, password_hash, full_name, role, department)
            VALUES (?, ?, ?, ?, ?)
            """,
            rows,
        )

    def _reset_default_passwords(self) -> None:
        # Keep demo credentials predictable while developing locally.
        self.db.executemany(
            "UPDATE users SET password_hash=? WHERE username=?",
            [
                (AppSettings.DEFAULT_ADMIN_PASSWORD, AppSettings.DEFAULT_ADMIN_USERNAME),
                (AppSettings.DEFAULT_STAFF_PASSWORD, AppSettings.DEFAULT_STAFF_USERNAME),
            ],
        )

    def _deactivate_legacy_housekeeping_login(self) -> None:
        # Old databases may still have a login that is no longer used.
        self.db.execute(
            """
            UPDATE users
            SET is_active=0
            WHERE username='housekeeping'
            """
        )

    def _seed_staff_members(self) -> None:
        # Create real employees for housekeeping and maintenance assignment.
        if not self._table_is_empty("staff_members"):
            return
        rows = [
            ("HK-001", "11111111111", "Zeynep", "Arslan", StaffType.HOUSEKEEPING),
            ("HK-002", "22222222222", "Mert", "Celik", StaffType.HOUSEKEEPING),
            ("MT-001", "33333333333", "Burak", "Yildiz", StaffType.MAINTENANCE),
            ("MT-002", "44444444444", "Selin", "Koc", StaffType.MAINTENANCE),
        ]
        self.db.executemany(
            """
            INSERT INTO staff_members (employee_number, national_id, first_name, last_name, staff_type)
            VALUES (?, ?, ?, ?, ?)
            """,
            rows,
        )

    def _seed_rooms(self) -> None:
        # Base room inventory gives the app useful data on first launch.
        if not self._table_is_empty("rooms"):
            return
        rows = [
            ("101", 1, "Standard", 2, 1800.0, RoomStatus.AVAILABLE, "Wi-Fi, TV, minibar"),
            ("102", 1, "Standard", 2, 1800.0, RoomStatus.AVAILABLE, "Wi-Fi, TV, city view"),
            ("103", 1, "Deluxe", 3, 2600.0, RoomStatus.CLEANING, "Wi-Fi, balcony, minibar"),
            ("104", 1, "Accessible", 2, 2000.0, RoomStatus.AVAILABLE, "Wheelchair access, Wi-Fi"),
            ("201", 2, "Standard", 2, 1950.0, RoomStatus.AVAILABLE, "Wi-Fi, TV, work desk"),
            ("202", 2, "Deluxe", 3, 2750.0, RoomStatus.AVAILABLE, "Balcony, espresso, sea view"),
            ("203", 2, "Deluxe", 3, 2750.0, RoomStatus.MAINTENANCE, "Balcony, espresso, sea view"),
            ("204", 2, "Family", 4, 3400.0, RoomStatus.AVAILABLE, "Two beds, crib, bathtub"),
            ("301", 3, "Suite", 4, 5200.0, RoomStatus.AVAILABLE, "Living room, sea view, jacuzzi"),
            ("302", 3, "Suite", 4, 5400.0, RoomStatus.AVAILABLE, "Living room, terrace, jacuzzi"),
            ("303", 3, "Executive", 2, 4100.0, RoomStatus.AVAILABLE, "Lounge access, work area"),
            ("401", 4, "Presidential Suite", 5, 9500.0, RoomStatus.AVAILABLE, "Butler service, terrace, dining room"),
        ]
        self.db.executemany(
            """
            INSERT INTO rooms (number, floor, room_type, capacity, base_price, status, amenities)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )

    def _seed_extended_rooms(self) -> None:
        # Extra large rooms are inserted if they are missing from older data.
        rows = [
            ("501", 5, "Family Suite", 6, 6800.0, RoomStatus.AVAILABLE, "Three beds, two bathrooms, kitchenette"),
            ("502", 5, "Group Villa", 8, 9200.0, RoomStatus.AVAILABLE, "Four bedrooms, private lounge, terrace"),
        ]
        self.db.executemany(
            """
            INSERT OR IGNORE INTO rooms (number, floor, room_type, capacity, base_price, status, amenities)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )

    def _seed_guests(self) -> None:
        # Starter guests make reservations and billing visible immediately.
        if not self._table_is_empty("guests"):
            return
        rows = [
            ("12345678901", "Ayse Demir", "+90 532 111 22 33", "ayse.demir@example.com", "Istanbul"),
            ("23456789012", "Mehmet Kaya", "+90 533 222 33 44", "mehmet.kaya@example.com", "Ankara"),
            ("34567890123", "Elif Yilmaz", "+90 534 333 44 55", "elif.yilmaz@example.com", "Izmir"),
            ("45678901234", "Can Aydin", "+90 535 444 55 66", "can.aydin@example.com", "Bursa"),
        ]
        self.db.executemany(
            """
            INSERT INTO guests (national_id, full_name, phone, email, address)
            VALUES (?, ?, ?, ?, ?)
            """,
            rows,
        )

    def _seed_service_items(self) -> None:
        # Room service items are ready for future ordering features.
        if not self._table_is_empty("room_service_items"):
            return
        rows = [
            ("Breakfast Set", 450.0, "Food"),
            ("Airport Transfer", 1200.0, "Transport"),
            ("Spa Access", 900.0, "Wellness"),
            ("Laundry Express", 350.0, "Service"),
        ]
        self.db.executemany(
            """
            INSERT INTO room_service_items (name, price, category)
            VALUES (?, ?, ?)
            """,
            rows,
        )

    def _seed_sample_reservation(self) -> None:
        # One checked-in stay helps the dashboard and billing screens look alive.
        if not self._table_is_empty("reservations"):
            return
        room = self.db.query_one("SELECT id FROM rooms WHERE number='202'")
        guest = self.db.query_one("SELECT id FROM guests WHERE national_id='12345678901'")
        user = self.db.query_one("SELECT id FROM users WHERE username=?", (AppSettings.DEFAULT_ADMIN_USERNAME,))
        if not room or not guest:
            return
        cursor = self.db.execute(
            """
            INSERT INTO reservations
                (guest_id, room_id, check_in, check_out, adults, children, status, notes, created_by)
            VALUES (?, ?, date('now', 'localtime'), date('now', 'localtime', '+2 day'), 2, 0, ?, ?, ?)
            """,
            (
                guest["id"],
                room["id"],
                ReservationStatus.CHECKED_IN,
                "Seed booking for dashboard demo",
                user["id"] if user else None,
            ),
        )
        reservation_id = cursor.lastrowid
        subtotal = 2 * 2750.0
        tax = round(subtotal * AppSettings.TAX_RATE, 2)
        total = round(subtotal + tax, 2)
        self.db.execute(
            """
            INSERT INTO invoices (reservation_id, subtotal, tax, discount, total, status, due_date)
            VALUES (?, ?, ?, 0, ?, ?, date('now', 'localtime', '+2 day'))
            """,
            (reservation_id, subtotal, tax, total, InvoiceStatus.PARTIAL),
        )
        self.db.execute("UPDATE rooms SET status=? WHERE id=?", (RoomStatus.OCCUPIED, room["id"]))

    def _seed_operations(self) -> None:
        # Add a few operational records only when their tables are empty.
        if self._table_is_empty("notifications"):
            self.db.execute(
                """
                INSERT INTO notifications (title, message)
                VALUES (?, ?)
                """,
                ("Welcome", "System is ready with sample rooms, guests and one active stay."),
            )
        if self._table_is_empty("housekeeping_tasks"):
            room = self.db.query_one("SELECT id FROM rooms WHERE number='103'")
            user = self.db.query_one("SELECT id FROM users WHERE username=?", (AppSettings.DEFAULT_STAFF_USERNAME,))
            staff = self.db.query_one(
                "SELECT id FROM staff_members WHERE staff_type=? ORDER BY id LIMIT 1",
                (StaffType.HOUSEKEEPING,),
            )
            if room:
                self.db.execute(
                    """
                    INSERT INTO housekeeping_tasks
                        (room_id, assigned_to, assigned_staff_id, task_type, status, notes)
                    VALUES (?, ?, ?, 'deep_clean', 'pending', 'Prepare room after minibar refill.')
                    """,
                    (room["id"], user["id"] if user else None, staff["id"] if staff else None),
                )
        if self._table_is_empty("maintenance_tickets"):
            room = self.db.query_one("SELECT id FROM rooms WHERE number='203'")
            user = self.db.query_one("SELECT id FROM users WHERE username=?", (AppSettings.DEFAULT_STAFF_USERNAME,))
            staff = self.db.query_one(
                "SELECT id FROM staff_members WHERE staff_type=? ORDER BY id LIMIT 1",
                (StaffType.MAINTENANCE,),
            )
            if room:
                self.db.execute(
                    """
                    INSERT INTO maintenance_tickets
                        (room_id, reported_by, assigned_staff_id, issue, priority, status)
                    VALUES (?, ?, ?, 'Air conditioner noise inspection required.', 'high', 'open')
                    """,
                    (room["id"], user["id"] if user else None, staff["id"] if staff else None),
                )
