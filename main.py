"""Application entry point for EmailPOC.

Loads ``.env`` and starts the Uvicorn ASGI server pointing at
``dynamic_email:app``.  Hot-reload is enabled by default so the server
restarts automatically when any ``.py`` or template file changes during
development.

Usage::

    # Recommended — uses pyproject.toml script entry point:
    uv run python main.py

    # Or directly via uvicorn:
    uv run uvicorn dynamic_email:app --host 0.0.0.0 --port 8000 --reload
"""

from dotenv import load_dotenv
load_dotenv()

import uvicorn


def main() -> None:
    """Start the Uvicorn server with hot-reload enabled.

    Binds to all network interfaces (``0.0.0.0``) on port ``8000``.  In
    production replace ``reload=True`` with ``workers=N`` and point a reverse
    proxy (nginx / Caddy) in front of Uvicorn.

    Returns:
        None

    Example:
        $ uv run python main.py
        INFO: Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
        INFO: Started reloader process using WatchFiles
    """
    uvicorn.run(
        "dynamic_email:app",
        host="0.0.0.0",
        port=7000,
        reload=True,
    )


if __name__ == "__main__":
    main()
