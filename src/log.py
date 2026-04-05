from __future__ import annotations

import logging
import os

from dotenv import load_dotenv

load_dotenv()

_level_name = os.getenv("LOG_LEVEL", "INFO").upper()
_level = getattr(logging, _level_name, logging.INFO)

logging.basicConfig(
    level=_level,
    format="[%(levelname)s] %(message)s",
)

logger = logging.getLogger("slack-post-interceptor")
