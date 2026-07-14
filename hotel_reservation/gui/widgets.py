"""Reusable widgets for the hotel reservation GUI."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from types import SimpleNamespace
from tkinter import font as tkfont
from tkinter import messagebox, ttk
from typing import Any, Callable

from hotel_reservation.config import AppSettings
from hotel_reservation.gui.theme import Theme


def _load_photo(image_path: Path) -> tk.PhotoImage | None:
    # Return None when an image asset is missing so widgets can draw a fallback.
    try:
        return tk.PhotoImage(file=str(image_path))
    except tk.TclError:
        return None


class BaseFrame(ttk.Frame):
    """Common frame with small helpers for page layout."""

    def __init__(self, master, app=None, **kwargs) -> None:
        super().__init__(master, **kwargs)
        # Pages keep a reference to the main app for services and navigation.
        self.app = app

    def clear(self) -> None:
        # Remove every child widget from this frame.
        for child in self.winfo_children():
            child.destroy()

    def page_title(self, title: str, subtitle: str = "") -> None:
        # Common page header used across all screens.
        ttk.Label(self, text=title, style="Title.TLabel").pack(anchor="w")
        if subtitle:
            ttk.Label(self, text=subtitle, style="Muted.TLabel").pack(anchor="w", pady=(4, 16))
        else:
            ttk.Frame(self, height=12).pack(fill="x")


class ImageCanvas(tk.Canvas):
    """Canvas that paints a centered PNG image behind other Tk widgets."""

    def __init__(
        self,
        master,
        image_path: Path,
        fallback: str = Theme.SIDEBAR,
        **kwargs,
    ) -> None:
        super().__init__(master, highlightthickness=0, bd=0, **kwargs)
        # The canvas owns the PhotoImage reference to prevent garbage collection.
        self.image_path = image_path
        self.fallback = fallback
        self.photo = _load_photo(image_path)
        self.bind("<Configure>", self._redraw)

    def _redraw(self, _event=None) -> None:
        # Recenter the image whenever the canvas changes size.
        self.delete("image-scene")
        width = max(self.winfo_width(), 1)
        height = max(self.winfo_height(), 1)
        if self.photo:
            x = (width - self.photo.width()) // 2
            y = (height - self.photo.height()) // 2
            self.create_image(x, y, image=self.photo, anchor="nw", tags="image-scene")
        else:
            self.create_rectangle(0, 0, width, height, outline="", fill=self.fallback, tags="image-scene")
        self.tag_lower("image-scene")


class ResortBackdrop(ImageCanvas):
    """PNG-backed exotic hotel backdrop."""

    def __init__(self, master, compact: bool = False, **kwargs) -> None:
        # Login and shell screens use different background crops.
        filename = "resort_workspace.png" if compact else "resort_login.png"
        super().__init__(
            master,
            AppSettings.ASSET_DIR / "images" / filename,
            fallback=Theme.SIDEBAR,
            **kwargs,
        )


class ResortBanner(tk.Canvas):
    """Dashboard banner backed by a PNG image asset."""

    def __init__(self, master, title: str, subtitle: str, **kwargs) -> None:
        super().__init__(master, height=150, highlightthickness=0, bd=0, **kwargs)
        # Store text and image so redraws can rebuild the banner.
        self.title = title
        self.subtitle = subtitle
        self.photo = _load_photo(AppSettings.ASSET_DIR / "images" / "dashboard_banner.png")
        self.bind("<Configure>", self._redraw)

    def _redraw(self, _event=None) -> None:
        # Draw image first, then readable text on top.
        self.delete("all")
        width = max(self.winfo_width(), 1)
        height = max(self.winfo_height(), 1)
        if self.photo:
            x = (width - self.photo.width()) // 2
            y = (height - self.photo.height()) // 2
            self.create_image(x, y, image=self.photo, anchor="nw")
        else:
            self.create_rectangle(0, 0, width, height, outline="", fill=Theme.SIDEBAR)
        self.create_text(28, 38, text=self.title, anchor="w", fill="#fff8ec", font=("Segoe UI Semibold", 22))
        self.create_text(30, 80, text=self.subtitle, anchor="w", fill="#dbeafe", font=("Segoe UI", 10), width=int(width * 0.48))


class PhotoCard(tk.Frame):
    """Small photographic card for premium dashboard context."""

    def __init__(self, master, image_name: str, title: str, subtitle: str) -> None:
        super().__init__(master, bg=Theme.SURFACE, highlightbackground=Theme.BORDER, highlightthickness=1)
        # Photo cards tolerate missing images by showing only text.
        self.configure(padx=0, pady=0)
        self.photo = _load_photo(AppSettings.ASSET_DIR / "images" / image_name)

        if self.photo:
            image = tk.Label(self, image=self.photo, bg=Theme.SURFACE, bd=0)
            image.pack(fill="x")

        body = tk.Frame(self, bg=Theme.SURFACE, padx=14, pady=12)
        body.pack(fill="x")
        tk.Label(body, text=title, bg=Theme.SURFACE, fg=Theme.TEXT, font=("Segoe UI Semibold", 12)).pack(anchor="w")
        tk.Label(body, text=subtitle, bg=Theme.SURFACE, fg=Theme.MUTED, font=("Segoe UI", 9), wraplength=330, justify="left").pack(anchor="w", pady=(4, 0))


ModalDialog = SimpleNamespace(
    # Messagebox wrappers keep dialog calls short in the screens.
    info=messagebox.showinfo,
    error=messagebox.showerror,
    confirm=lambda title, message: bool(messagebox.askyesno(title, message)),
)


def _rounded_rect(canvas: tk.Canvas, x1: int, y1: int, x2: int, y2: int, radius: int, **kwargs) -> None:
    # Tkinter has no rounded rectangle primitive, so draw a smoothed polygon.
    points = [
        x1 + radius,
        y1,
        x2 - radius,
        y1,
        x2,
        y1,
        x2,
        y1 + radius,
        x2,
        y2 - radius,
        x2,
        y2,
        x2 - radius,
        y2,
        x1 + radius,
        y2,
        x1,
        y2,
        x1,
        y2 - radius,
        x1,
        y1 + radius,
        x1,
        y1,
    ]
    canvas.create_polygon(points, smooth=True, **kwargs)


class ModernButton(tk.Canvas):
    """Rounded button with primary, secondary and danger variants."""

    # Button variants map semantic names to colors.
    VARIANTS = {
        "primary": {
            "fill": Theme.SIDEBAR_ACTIVE,
            "hover": "#1d4ed8",
            "outline": Theme.SIDEBAR_ACTIVE,
            "text": "#ffffff",
        },
        "secondary": {
            "fill": Theme.SURFACE,
            "hover": "#eef2f7",
            "outline": Theme.BORDER,
            "text": Theme.TEXT,
        },
        "danger": {
            "fill": Theme.DANGER,
            "hover": "#b91c1c",
            "outline": Theme.DANGER,
            "text": "#ffffff",
        },
        "ghost": {
            "fill": Theme.BG,
            "hover": "#e8eef7",
            "outline": Theme.BORDER,
            "text": Theme.TEXT,
        },
        "glass": {
            "fill": "#1f2937",
            "hover": "#334155",
            "outline": "#475569",
            "text": "#e5e7eb",
        },
    }

    def __init__(
        self,
        master,
        text: str,
        command: Callable[[], None],
        *,
        variant: str = "secondary",
        width: int | None = None,
        height: int = 40,
    ) -> None:
        # Measure the label so buttons fit their text by default.
        self.text = text
        self.command = command
        self.variant = variant if variant in self.VARIANTS else "secondary"
        self.height = height
        button_font = tkfont.Font(family="Segoe UI", size=9, weight="bold")
        calculated_width = button_font.measure(text) + 34
        self.width = width or max(92, calculated_width)
        super().__init__(
            master,
            width=self.width,
            height=self.height,
            bg=master.cget("background") if "background" in master.keys() else Theme.BG,
            highlightthickness=0,
            bd=0,
            cursor="hand2",
        )
        self.button_font = button_font
        self._is_hovered = False
        self.bind("<Button-1>", self._click)
        self.bind("<Enter>", self._enter)
        self.bind("<Leave>", self._leave)
        self.bind("<Configure>", self._resize)
        self.bind("<ButtonRelease-1>", lambda _event: self._draw())
        self._draw()

    def _palette(self) -> dict[str, str]:
        # Resolve the current color set for drawing.
        return self.VARIANTS[self.variant]

    def _draw(self) -> None:
        # Redraw the full canvas because hover changes the shape and colors.
        self.delete("all")
        palette = self._palette()
        fill = palette["hover"] if self._is_hovered else palette["fill"]
        inset = 1 if self._is_hovered else 2
        radius = min(24, self.height // 2)
        _rounded_rect(
            self,
            inset,
            inset,
            self.width - inset,
            self.height - inset,
            radius,
            fill=fill,
            outline=palette["outline"],
            width=1,
        )
        if self._is_hovered and self.variant in {"primary", "danger"}:
            _rounded_rect(
                self,
                5,
                5,
                self.width - 5,
                self.height - 5,
                radius - 4,
                fill="",
                outline="#ffffff",
                width=1,
            )
        self.create_text(
            self.width // 2,
            self.height // 2,
            text=self.text,
            fill=palette["text"],
            font=self.button_font,
        )

    def _enter(self, _event) -> None:
        # Hover state gives quick visual feedback.
        self._is_hovered = True
        self._draw()

    def _leave(self, _event) -> None:
        # Leaving the button returns it to its normal palette.
        self._is_hovered = False
        self._draw()

    def _click(self, _event) -> None:
        # Canvas buttons call the supplied command on click.
        if self.command:
            self.command()

    def _resize(self, event) -> None:
        # Keep drawing dimensions aligned with actual widget width.
        if event.width != self.width:
            self.width = event.width
            self._draw()


class NavButton(tk.Canvas):
    """Sidebar navigation button with rounded active state."""

    def __init__(self, master, text: str, command: Callable[[], None], width: int = 224) -> None:
        # Sidebar buttons draw their own active and hover states.
        super().__init__(
            master,
            width=width,
            height=42,
            bg=Theme.SIDEBAR,
            highlightthickness=0,
            bd=0,
            cursor="hand2",
        )
        self.text = text
        self.command = command
        self.width = width
        self.active = False
        self.hover = False
        self.font = tkfont.Font(family="Segoe UI", size=10, weight="bold")
        self.bind("<Enter>", self._enter)
        self.bind("<Leave>", self._leave)
        self.bind("<Button-1>", self._click)
        self._draw()

    def set_active(self, active: bool) -> None:
        # Navigation calls this when the current page changes.
        self.active = active
        self._draw()

    def _draw(self) -> None:
        # Active pages get a blue background and a small left marker.
        self.delete("all")
        fill = Theme.SIDEBAR_ACTIVE if self.active else ("#22304a" if self.hover else Theme.SIDEBAR)
        text = "#ffffff" if self.active or self.hover else "#e5e7eb"
        _rounded_rect(self, 0, 2, self.width, 40, 14, fill=fill, outline=fill)
        if self.active:
            _rounded_rect(self, 8, 13, 12, 29, 4, fill="#bfdbfe", outline="#bfdbfe")
        self.create_text(28, 21, text=self.text, anchor="w", fill=text, font=self.font)

    def _enter(self, _event) -> None:
        # Hover highlights inactive navigation items.
        self.hover = True
        self._draw()

    def _leave(self, _event) -> None:
        # Clear hover when the pointer leaves.
        self.hover = False
        self._draw()

    def _click(self, _event) -> None:
        # Navigate through the command passed by Sidebar.
        self.command()


class StatCard(tk.Frame):
    """Dashboard metric card."""

    def __init__(self, master, title: str, value: str, accent: str = Theme.SIDEBAR_ACTIVE) -> None:
        # Small dashboard card with a colored accent rule.
        super().__init__(master, bg=Theme.SURFACE, highlightbackground=Theme.BORDER, highlightthickness=1)
        self.configure(padx=18, pady=14)
        tk.Label(self, text=title, bg=Theme.SURFACE, fg=Theme.MUTED, font=("Segoe UI", 9)).pack(anchor="w")
        tk.Label(self, text=value, bg=Theme.SURFACE, fg=Theme.TEXT, font=("Segoe UI Semibold", 22)).pack(anchor="w", pady=(6, 0))
        tk.Frame(self, bg=accent, height=3).pack(fill="x", pady=(12, 0))


class Sidebar(tk.Frame):
    """Left navigation sidebar."""

    def __init__(self, master, app, user: dict[str, Any]) -> None:
        # Sidebar owns navigation buttons and the logged-in user label.
        super().__init__(master, width=252, bg=Theme.SIDEBAR)
        self.app = app
        self.buttons: dict[str, NavButton] = {}
        self.pack_propagate(False)
        header = tk.Canvas(self, height=136, bg=Theme.SIDEBAR, highlightthickness=0, bd=0)
        header.pack(fill="x", padx=0, pady=(0, 8))
        self.sidebar_photo = None
        self.sidebar_photo = _load_photo(AppSettings.ASSET_DIR / "images" / "sidebar_header.png")
        if self.sidebar_photo:
            header.create_image(-85, -72, image=self.sidebar_photo, anchor="nw")
        else:
            header.create_rectangle(0, 0, 252, 136, outline="", fill=Theme.SIDEBAR_DARK)
        header.create_text(22, 28, text="Grand Vista", anchor="w", fill="#ffffff", font=("Segoe UI Semibold", 18))
        header.create_text(
            22,
            55,
            text="Luxury Resort Suite",
            anchor="w",
            fill="#bfdbfe",
            font=("Segoe UI", 9),
        )
        tk.Label(
            self,
            text=f"{user['full_name']} - {user['role']}",
            bg=Theme.SIDEBAR,
            fg="#dbeafe",
            font=("Segoe UI", 9),
            wraplength=190,
            justify="left",
        ).pack(anchor="w", padx=22, pady=(0, 16))
        tk.Label(
            self,
            text="Navigation",
            bg=Theme.SIDEBAR,
            fg="#93c5fd",
            font=("Segoe UI Semibold", 9),
            justify="left",
        ).pack(anchor="w", padx=22, pady=(0, 8))

        items = [
            # Page keys match AppWindow.navigate().
            ("dashboard", "Dashboard"),
            ("rooms", "Rooms"),
            ("guests", "Guests"),
            ("reservations", "Reservations"),
            ("billing", "Billing"),
            ("operations", "Operations"),
            ("reports", "Reports"),
            ("staff", "Employees"),
        ]
        for key, label in items:
            # Hide pages the current role cannot access.
            if hasattr(app, "can_access_page") and not app.can_access_page(key):
                continue
            button = NavButton(self, label, command=lambda page=key: self.app.navigate(page))
            button.pack(fill="x", padx=14, pady=3)
            self.buttons[key] = button

        NavButton(self, "Logout", command=self.app.logout).pack(side="bottom", fill="x", padx=14, pady=18)

    def set_active(self, key: str) -> None:
        # Update every nav button after navigation.
        for page, button in self.buttons.items():
            button.set_active(page == key)


class SearchHeader(ttk.Frame):
    """Search box with optional action buttons."""

    def __init__(
        self,
        master,
        placeholder: str,
        on_search: Callable[[str], None],
        actions: list[tuple[str, Callable[[], None]]] | None = None,
    ) -> None:
        super().__init__(master, style="Toolbar.TFrame")
        # SearchHeader combines one search input with optional page actions.
        self.on_search = on_search
        self.placeholder = placeholder
        self.search_var = tk.StringVar()
        self.entry = ttk.Entry(self, textvariable=self.search_var, width=34)
        self.entry.insert(0, placeholder)
        self.entry.pack(side="left", padx=(0, 8))
        self.entry.bind("<FocusIn>", self._clear_placeholder)
        self.entry.bind("<Return>", lambda _event: self.submit())
        ModernButton(self, "Search", self.submit, variant="secondary", width=92).pack(side="left")
        ModernButton(self, "Reset", self.reset, variant="ghost", width=86).pack(side="left", padx=(8, 16))
        for label, command in actions or []:
            ModernButton(self, label, command, variant="primary").pack(side="left", padx=(0, 8))

    def _clear_placeholder(self, _event) -> None:
        # Clear the helper text the first time the user focuses the field.
        if self.search_var.get() == self.placeholder:
            self.search_var.set("")

    def submit(self) -> None:
        # Treat the untouched placeholder as an empty search.
        value = "" if self.search_var.get() == self.placeholder else self.search_var.get()
        self.on_search(value)

    def reset(self) -> None:
        # Reset returns the table to its full dataset.
        self.search_var.set("")
        self.on_search("")


class DataTable(tk.Frame):
    """Simple scrollable data table."""

    # These columns are styled as labels instead of plain text.
    STATUS_KEYS = {"status", "is_active", "priority", "availability_status"}
    # Status colors keep meaning consistent across all screens.
    STATUS_COLORS = {
        "available": Theme.SUCCESS,
        "completed": Theme.SUCCESS,
        "paid": Theme.SUCCESS,
        "occupied": Theme.SIDEBAR_ACTIVE,
        "confirmed": Theme.SIDEBAR_ACTIVE,
        "checked_in": Theme.SIDEBAR_ACTIVE,
        "open": Theme.SIDEBAR_ACTIVE,
        "pending": Theme.WARNING,
        "partial": Theme.WARNING,
        "cleaning": Theme.WARNING,
        "maintenance": Theme.DANGER,
        "cancelled": Theme.DANGER,
        "closed": Theme.MUTED,
        "Available": Theme.SUCCESS,
        "Busy": Theme.WARNING,
        "Inactive": Theme.MUTED,
        "1": Theme.SUCCESS,
        "0": Theme.DANGER,
    }

    def __init__(
        self,
        master,
        columns: list[tuple[str, str, int]],
        id_key: str = "id",
        on_select: Callable[[int | None], None] | None = None,
    ) -> None:
        super().__init__(master, bg=Theme.SURFACE, highlightbackground=Theme.BORDER, highlightthickness=1)
        # Columns are tuples of data key, header label and relative width.
        self.columns = columns
        self.id_key = id_key
        self.on_select = on_select
        self._selected_id: int | None = None
        self._row_frames: dict[str, tk.Frame] = {}
        self._row_indexes: dict[str, int] = {}

        # The header is a fixed row above the scrollable body.
        self.header = tk.Frame(self, bg=Theme.SURFACE_ALT, padx=8, pady=8)
        self.header.grid(row=0, column=0, sticky="ew")
        self._configure_columns(self.header)
        for index, (_key, label, _width) in enumerate(columns):
            tk.Label(
                self.header,
                text=label,
                bg=Theme.SURFACE_ALT,
                fg=Theme.MUTED,
                font=("Segoe UI Semibold", 9),
                anchor="w",
            ).grid(row=0, column=index, sticky="ew", padx=4)

        # A canvas makes the table body vertically scrollable.
        self.canvas = tk.Canvas(self, bg=Theme.SURFACE, highlightthickness=0, bd=0)
        self.body = tk.Frame(self.canvas, bg=Theme.SURFACE)
        self.v_scroll = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.v_scroll.set)
        self.canvas_window = self.canvas.create_window((0, 0), window=self.body, anchor="nw")
        self.canvas.grid(row=1, column=0, sticky="nsew")
        self.v_scroll.grid(row=1, column=1, sticky="ns")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        self._configure_columns(self.body)
        self.body.bind("<Configure>", self._sync_scroll_region)
        self.canvas.bind("<Configure>", self._sync_canvas_width)
        self._bind_scroll(self)
        self._bind_scroll(self.header)
        self._bind_scroll(self.canvas)
        self._bind_scroll(self.body)

    def _configure_columns(self, frame: tk.Frame) -> None:
        # Use relative weights so each row lines up with the header.
        for index, (_key, _label, width) in enumerate(self.columns):
            frame.columnconfigure(index, weight=max(width, 60), uniform="table")

    def _sync_scroll_region(self, _event=None) -> None:
        # Update the scrollable area after rows are added or removed.
        try:
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        except tk.TclError:
            return

    def _sync_canvas_width(self, event) -> None:
        # Make the embedded body frame match the canvas width.
        try:
            self.canvas.itemconfigure(self.canvas_window, width=event.width)
        except tk.TclError:
            return

    def _bind_scroll(self, widget: tk.Widget) -> None:
        # Allow mouse wheel scrolling from any table child.
        widget.bind("<MouseWheel>", self._on_mousewheel, add="+")

    def _bind_cell_events(self, widget: tk.Widget, item_id: str) -> None:
        # Clicking any cell selects the whole row.
        widget.bind("<Button-1>", lambda _event, iid=item_id: self._select(iid))
        self._bind_scroll(widget)

    def _on_mousewheel(self, event) -> None:
        # Ignore scroll events if the table was destroyed during navigation.
        try:
            if not self.winfo_exists() or not self.canvas.winfo_exists():
                return
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        except tk.TclError:
            return

    def populate(self, rows: list[Any]) -> None:
        # Rebuild rows from scratch; datasets are small and this keeps state simple.
        for child in self.body.winfo_children():
            child.destroy()
        self._selected_id = None
        self._row_frames.clear()
        self._row_indexes.clear()

        for index, row in enumerate(rows):
            # sqlite3.Row and dictionaries both become plain dicts here.
            data = dict(row) if hasattr(row, "keys") else row
            item_id = str(data.get(self.id_key, f"row-{index}"))
            row_bg = "#ffffff" if index % 2 == 0 else "#f9fafb"
            row_frame = tk.Frame(self.body, bg=row_bg, padx=8, pady=9)
            row_frame.grid(row=index, column=0, columnspan=len(self.columns), sticky="ew", pady=(0, 1))
            self._configure_columns(row_frame)
            self._row_frames[item_id] = row_frame
            self._row_indexes[item_id] = index
            self._bind_cell_events(row_frame, item_id)

            for column_index, (key, _label, _width) in enumerate(self.columns):
                # Each cell is a frame so row background changes can recurse.
                cell = tk.Frame(row_frame, bg=row_bg)
                cell.grid(row=0, column=column_index, sticky="ew", padx=4)
                self._bind_cell_events(cell, item_id)
                self._render_cell(cell, key, data.get(key, ""), row_bg, item_id)

        self._sync_scroll_region()

    def _render_cell(self, parent: tk.Frame, key: str, value: Any, bg: str, item_id: str) -> None:
        # Format values and style status-like fields.
        text = self._format(value)
        font = ("Segoe UI", 10)
        color = Theme.TEXT
        if key in self.STATUS_KEYS:
            text = text.replace("_", " ").title()
            font = ("Segoe UI Semibold", 9)
            color = self.STATUS_COLORS.get(str(value), Theme.TEXT)

        label = tk.Label(
            parent,
            text=text,
            bg=bg,
            fg=color,
            font=font,
            anchor="w",
            justify="left",
        )
        label.pack(side="left", fill="x", expand=True)
        self._bind_cell_events(label, item_id)

    def _select(self, item_id: str) -> None:
        # Store the selected database ID and notify the page if needed.
        self._selected_id = int(item_id) if item_id.isdigit() else None
        self._paint_selection(item_id)
        if self.on_select:
            self.on_select(self._selected_id)

    def clear_selection(self) -> None:
        # Used when two tables share the same page and selection should be exclusive.
        self._selected_id = None
        self._paint_selection("")

    def _paint_selection(self, item_id: str) -> None:
        # Repaint every row so only the selected row is highlighted.
        for iid, frame in self._row_frames.items():
            selected = iid == item_id
            row_index = self._row_indexes.get(iid, 0)
            bg = "#e0f2fe" if selected else ("#ffffff" if row_index % 2 == 0 else "#f9fafb")
            self._set_row_bg(frame, bg)

    def _set_row_bg(self, widget: tk.Widget, bg: str) -> None:
        # Recursively set background on the row and all nested cell widgets.
        try:
            widget.configure(bg=bg)
        except tk.TclError:
            return
        for child in widget.winfo_children():
            self._set_row_bg(child, bg)

    def selected_id(self) -> int | None:
        # Pages call this before opening dialogs or service actions.
        return self._selected_id

    @staticmethod
    def _format(value: Any) -> str:
        # Keep money and date-like values readable in table cells.
        if isinstance(value, float):
            return f"{value:,.2f}"
        if isinstance(value, str) and len(value) >= 10 and value[4:5] == "-" and value[7:8] == "-":
            return value[:10]
        return "" if value is None else str(value)


class RoomCard(tk.Frame):
    """Compact visual room summary used on the dashboard."""

    STATUS_COLORS = {
        "available": Theme.SUCCESS,
        "occupied": Theme.SIDEBAR_ACTIVE,
        "cleaning": Theme.WARNING,
        "maintenance": Theme.DANGER,
    }

    def __init__(self, master, room: dict[str, Any]) -> None:
        # Room cards show a tiny inventory snapshot on the dashboard.
        status = room.get("status", "available")
        super().__init__(master, bg=Theme.SURFACE, padx=12, pady=10, highlightbackground=Theme.BORDER, highlightthickness=1)
        tk.Label(self, text=f"Room {room.get('number')}", bg=Theme.SURFACE, fg=Theme.TEXT, font=("Segoe UI Semibold", 12)).pack(anchor="w")
        tk.Label(self, text=room.get("room_type", ""), bg=Theme.SURFACE, fg=Theme.MUTED, font=("Segoe UI", 9)).pack(anchor="w")
        tk.Label(
            self,
            text=status.title(),
            bg=Theme.SURFACE,
            fg=self.STATUS_COLORS.get(status, Theme.MUTED),
            font=("Segoe UI Semibold", 9),
        ).pack(anchor="w", pady=(8, 0))



class GlassEntry(tk.Frame):
    """Rounded entry shell used by the login form."""

    def __init__(
        self,
        master,
        variable: tk.StringVar,
        *,
        show: str | None = None,
        bg: str,
        font: tuple[str, int] = ("Segoe UI", 12),
    ) -> None:
        super().__init__(master, bg=bg, height=50)
        # GlassEntry draws a rounded shell behind a normal tk.Entry.
        self.shell_bg = bg
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0)
        self.canvas.place(x=0, y=0, relwidth=1, relheight=1)
        self.entry = tk.Entry(
            self,
            textvariable=variable,
            show=show,
            bg="#edf5f8",
            fg="#252a30",
            insertbackground="#252a30",
            relief="flat",
            bd=0,
            font=font,
        )
        self.entry.place(x=18, y=11, relwidth=1, width=-36, height=28)
        self.is_focused = False
        self.bind("<Configure>", self._draw)
        self.entry.bind("<FocusIn>", self._focus_in)
        self.entry.bind("<FocusOut>", self._focus_out)
        self._draw()

    def bind_entry(self, sequence: str, func: Callable[..., Any]) -> None:
        # Expose binding on the inner Entry for Return key handling.
        self.entry.bind(sequence, func)

    def focus_set(self) -> None:
        # Focus should land inside the real entry, not the decorative frame.
        self.entry.focus_set()

    def _focus_in(self, _event=None) -> None:
        # Focus changes the outline color.
        self.is_focused = True
        self._draw()

    def _focus_out(self, _event=None) -> None:
        # Restore the normal outline when focus leaves.
        self.is_focused = False
        self._draw()

    def _draw(self, _event=None) -> None:
        # Redraw the rounded input background at the current size.
        self.canvas.delete("all")
        width = max(self.winfo_width(), 1)
        height = max(self.winfo_height(), 1)
        outline = "#6f8ea8" if self.is_focused else "#b6c8d5"
        _rounded_rect(self.canvas, 5, 9, width - 3, height - 3, 8, fill="#bfccd6", outline="")
        _rounded_rect(self.canvas, 2, 3, width - 4, height - 8, 8, fill="#edf5f8", outline=outline, width=1)
        _rounded_rect(self.canvas, 3, 4, width - 5, height - 9, 7, fill="", outline="#f8fbfd", width=1)


class LoginForm(BaseFrame):
    """Centered frosted-glass login screen."""

    CARD_BG = "#dbe7ed"
    CARD_BORDER = "#aebfca"
    CARD_MIN_WIDTH = 430
    CARD_MAX_WIDTH = 560

    def __init__(self, master, app) -> None:
        super().__init__(master, app=app)
        # Login screen sits on top of a photo backdrop.
        self.configure(style="TFrame")
        self.backdrop = ResortBackdrop(self)
        self.backdrop.place(x=0, y=0, relwidth=1, relheight=1)
        self.backdrop.bind("<Configure>", self._layout_card, add="+")
        self.bind("<Configure>", self._layout_card, add="+")

        self.container = tk.Frame(self, bg=self.CARD_BG, highlightthickness=0)

        # The center card keeps the resort branding and login form together.
        self._build_anniversary_badge(self.container).pack(anchor="center", pady=(0, 8))
        tk.Label(
            self.container,
            text="Grand Vista",
            bg=self.CARD_BG,
            fg="#20242a",
            font=("Segoe UI", 30),
        ).pack(anchor="center")
        tk.Label(
            self.container,
            text="25 Years of Service - Quality Tradition",
            bg=self.CARD_BG,
            fg="#2f343b",
            font=("Segoe UI", 12),
        ).pack(anchor="center", pady=(6, 22))

        form = tk.Frame(self.container, bg=self.CARD_BG)
        form.pack(fill="x", padx=30)

        tk.Label(
            form,
            text="Username",
            bg=self.CARD_BG,
            fg="#252a30",
            font=("Segoe UI", 12),
        ).pack(anchor="w", pady=(0, 5))

        self.username_var = tk.StringVar()
        username_entry = GlassEntry(form, self.username_var, bg=self.CARD_BG)
        username_entry.pack(fill="x", pady=(0, 14))

        tk.Label(
            form,
            text="Password",
            bg=self.CARD_BG,
            fg="#252a30",
            font=("Segoe UI", 12),
        ).pack(anchor="w", pady=(0, 5))
        self.password_var = tk.StringVar()
        password_entry = GlassEntry(form, self.password_var, show="*", bg=self.CARD_BG)
        password_entry.pack(fill="x", pady=(0, 18))
        password_entry.bind_entry("<Return>", lambda _event: self.submit())

        # Login and exit controls sit below the credential fields.
        ModernButton(self.container, "Login", self.submit, variant="primary", width=360, height=48).pack(fill="x", padx=30)
        close_font = tkfont.Font(family="Segoe UI", size=12, underline=True)
        self.exit_button = tk.Label(
            self.container,
            text="Back / Exit Application",
            bg=self.CARD_BG,
            fg="#20242a",
            cursor="hand2",
            font=close_font,
        )
        self.exit_button.pack(anchor="center", pady=(18, 0))
        self.exit_button.bind("<Button-1>", lambda _event: self.app.close_application())

        self.status_var = tk.StringVar()
        tk.Label(
            self.container,
            textvariable=self.status_var,
            bg=self.CARD_BG,
            fg="#b91c1c",
            font=("Segoe UI", 9),
            wraplength=360,
            justify="left",
        ).pack(anchor="center", pady=(6, 0))
        self.after_idle(self._layout_card)
        username_entry.focus_set()

    def _build_anniversary_badge(self, parent) -> tk.Canvas:
        # Small decorative badge drawn directly on a canvas.
        badge = tk.Canvas(parent, width=128, height=72, bg=self.CARD_BG, highlightthickness=0, bd=0)
        badge.create_text(64, 27, text="25.", fill="#6b7280", font=("Georgia", 26, "bold"))
        badge.create_text(64, 49, text="Years", fill="#6b7280", font=("Segoe UI", 10, "italic"))
        badge.create_line(35, 58, 51, 65, fill="#7b8189", width=2, smooth=True)
        badge.create_line(77, 65, 93, 58, fill="#7b8189", width=2, smooth=True)
        for index in range(7):
            y = 58 - index * 6
            left_x = 37 - index * 2
            right_x = 91 + index * 2
            badge.create_oval(left_x - 5, y - 5, left_x + 3, y + 5, fill="#7b8189", outline="")
            badge.create_oval(right_x - 3, y - 5, right_x + 5, y + 5, fill="#7b8189", outline="")
        return badge

    def _card_bounds(self) -> tuple[int, int, int, int]:
        # Calculate a responsive card size that stays centered on the photo.
        width = max(self.winfo_width(), 1)
        height = max(self.winfo_height(), 1)
        card_width = min(self.CARD_MAX_WIDTH, max(self.CARD_MIN_WIDTH, int(width * 0.32)))
        content_height = self.container.winfo_reqheight() if self.container.winfo_children() else 0
        card_height = max(540, content_height + 58)
        card_height = min(max(height - 64, 1), card_height)
        x1 = (width - card_width) // 2
        y1 = max(24, (height - card_height) // 2 - 70)
        return x1, y1, x1 + card_width, y1 + card_height

    def _layout_card(self, _event=None) -> None:
        # Place the form container inside the drawn rounded card.
        x1, y1, x2, y2 = self._card_bounds()
        self._redraw_card(x1, y1, x2, y2)
        inset_x = 20
        inset_y = 26
        self.container.place(
            x=x1 + inset_x,
            y=y1 + inset_y,
            width=max(x2 - x1 - inset_x * 2, 1),
            height=max(y2 - y1 - inset_y * 2, 1),
        )

    def _redraw_card(self, x1: int, y1: int, x2: int, y2: int) -> None:
        # Redraw only the card layer over the backdrop.
        self.backdrop.delete("login-card")
        _rounded_rect(
            self.backdrop,
            x1,
            y1,
            x2,
            y2,
            14,
            fill=self.CARD_BG,
            outline=self.CARD_BORDER,
            width=1,
            tags="login-card",
        )

    def submit(self) -> None:
        # Send credentials to the app and show validation errors inline.
        username = self.username_var.get().strip()
        password = self.password_var.get()
        try:
            self.app.handle_login(username, password)
        except ValueError as exc:
            self.status_var.set(str(exc))
