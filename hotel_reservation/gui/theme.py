"""Visual theme helpers for the Tkinter interface."""

from types import SimpleNamespace
from tkinter import ttk


# The Theme namespace keeps colors and helper functions together.
Theme = SimpleNamespace(
    BG="#f6f7fb",
    SURFACE="#ffffff",
    SURFACE_ALT="#eef2f7",
    GLASS="#f8fafc",
    SIDEBAR="#172033",
    SIDEBAR_DARK="#101827",
    SIDEBAR_ACTIVE="#2563eb",
    ACCENT="#0f766e",
    GOLD="#b7791f",
    CORAL="#e11d48",
    TEXT="#111827",
    MUTED="#667085",
    BORDER="#d8dee9",
    SUCCESS="#16a34a",
    WARNING="#f59e0b",
    DANGER="#dc2626",
)


def apply(root) -> None:
    # Apply one consistent ttk look across all screens.
    style = ttk.Style(root)
    try:
        # "clam" gives more predictable styling than the platform default.
        style.theme_use("clam")
    except Exception:
        pass
    root.configure(bg=Theme.BG)
    style.configure("TFrame", background=Theme.BG)
    style.configure("Surface.TFrame", background=Theme.SURFACE, relief="flat")
    style.configure("Toolbar.TFrame", background=Theme.BG, relief="flat")
    style.configure("Dialog.TFrame", background=Theme.SURFACE, relief="flat")
    style.configure("Glass.TFrame", background=Theme.GLASS, relief="flat")
    style.configure("TLabel", background=Theme.BG, foreground=Theme.TEXT, font=("Segoe UI", 10))
    style.configure("Muted.TLabel", background=Theme.BG, foreground=Theme.MUTED, font=("Segoe UI", 9))
    style.configure("Title.TLabel", background=Theme.BG, foreground=Theme.TEXT, font=("Segoe UI Semibold", 21))
    style.configure("Section.TLabel", background=Theme.BG, foreground=Theme.TEXT, font=("Segoe UI Semibold", 13))
    style.configure("Field.TLabel", background=Theme.SURFACE, foreground=Theme.MUTED, font=("Segoe UI Semibold", 9))
    style.configure("Surface.TLabel", background=Theme.SURFACE, foreground=Theme.TEXT, font=("Segoe UI", 10))
    style.configure("Glass.TLabel", background=Theme.GLASS, foreground=Theme.TEXT, font=("Segoe UI", 10))
    style.configure("SurfaceTitle.TLabel", background=Theme.SURFACE, foreground=Theme.TEXT, font=("Segoe UI Semibold", 14))
    style.configure("GlassTitle.TLabel", background=Theme.GLASS, foreground=Theme.TEXT, font=("Segoe UI Semibold", 16))
    style.configure("TEntry", fieldbackground=Theme.SURFACE, bordercolor=Theme.BORDER, lightcolor=Theme.BORDER, padding=8)
    style.configure("TCombobox", fieldbackground=Theme.SURFACE, bordercolor=Theme.BORDER, lightcolor=Theme.BORDER, padding=8)
    style.configure("Vertical.TScrollbar", background=Theme.SURFACE_ALT, troughcolor=Theme.BG, bordercolor=Theme.BORDER)


def money(value: float | int | str) -> str:
    # Convert any numeric value into the display format used in the UI.
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = 0.0
    return f"{number:,.2f} TL"


# Attach helpers so callers can use Theme.apply(...) and Theme.money(...).
Theme.apply = apply
Theme.money = money
