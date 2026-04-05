from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

_level_name = os.getenv("LOG_LEVEL", "INFO").upper()
_level = getattr(logging, _level_name, logging.INFO)

_fmt = "[%(levelname)s] %(message)s"
logging.basicConfig(level=_level, format=_fmt)

_log_dir = Path(__file__).parent.parent / "logs"
_log_dir.mkdir(exist_ok=True)
_file_handler = RotatingFileHandler(
    _log_dir / "app.log",
    maxBytes=1_000_000,
    backupCount=3,
    encoding="utf-8",
)
_file_handler.setFormatter(logging.Formatter("%(asctime)s " + _fmt))
logging.getLogger().addHandler(_file_handler)

logger = logging.getLogger("slack-post-interceptor")
