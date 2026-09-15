"""
app_logger.py - Centralized logging configuration.

A handful of except blocks across the app catch broadly (Exception, or a
bare except:) and previously either did nothing (`pass`) or just returned
False/None with no record of what actually went wrong. That's a deliberate,
reasonable choice for keeping a shop-floor kiosk app from crashing on a
secondary failure — but "resilient" and "silent" don't have to be the same
thing. This module gives those handlers somewhere to record the real
exception before swallowing it, without changing how they behave for the
person using the app.

Usage: `from app_logger import logger` and call `logger.exception("...")`
inside an except block (it logs the current traceback automatically), or
`logger.error("...")` / `logger.warning("...")` elsewhere.

Writes to both the console (visible wherever uvicorn is running) and a
rotating file under logs/, so history survives past terminal scrollback.
Logs live in the same directory as backups/uploads.
"""
import logging
import os
from logging.handlers import RotatingFileHandler

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(BASE_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)

logger = logging.getLogger("formlabs_mes")
logger.setLevel(logging.INFO)

# A module-level guard, not just Python's own import cache: uvicorn's
# --reload watches for file changes and re-executes modules, and this file
# is imported from enough places (crud.py, api/, the gateway) that without
# this check a reload could add a second set of handlers — duplicate log
# lines, and file handles accumulating for the life of the server process.
if not logger.handlers:
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )

    file_handler = RotatingFileHandler(
        os.path.join(LOG_DIR, "formlabs_mes.log"), maxBytes=2_000_000, backupCount=5
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
