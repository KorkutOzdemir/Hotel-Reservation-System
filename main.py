"""Application entry point for the hotel reservation system."""

from __future__ import annotations

import sys

from hotel_reservation.runtime import gui_environment_message


def main() -> None:
    # Tkinter is imported here so CLI import errors can show a friendly message.
    try:
        import tkinter as tk
    except Exception as exc:
        print(gui_environment_message(exc), file=sys.stderr)
        raise SystemExit(1) from None

    # Build the main window only after the GUI environment is confirmed.
    try:
        from hotel_reservation.gui.app import AppWindow

        app = AppWindow()
        app.mainloop()
    except tk.TclError as exc:
        print(gui_environment_message(exc), file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    # Keep direct script execution simple: python main.py
    main()
