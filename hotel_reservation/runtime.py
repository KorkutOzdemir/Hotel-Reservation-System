"""Runtime helpers for launching the desktop GUI reliably."""

from __future__ import annotations

import sys


def gui_environment_message(error: BaseException) -> str:
    """Return a short, useful message for common Tkinter launch failures."""

    # This text is printed when the app cannot open a desktop window.
    return (
        "The application code loaded, but Python could not open the Tkinter GUI.\n\n"
        f"Python executable: {sys.executable}\n"
        f"Error: {error}\n\n"
        "Install Python 3.10+ from python.org with Tcl/Tk support enabled, then run:\n"
        "python main.py\n\n"
        "You can verify the environment with:\n"
        "python scripts\\check_environment.py"
    )
