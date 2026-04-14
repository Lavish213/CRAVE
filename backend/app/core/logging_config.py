from __future__ import annotations

import logging
from app.middleware.request_id import request_id_var


class RequestIDFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get("")
        return True
