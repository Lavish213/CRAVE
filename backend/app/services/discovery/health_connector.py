from __future__ import annotations

import csv
import io
import json
import logging
from typing import Any, Dict, Iterator, List, Optional

from app.services.network.http_fetcher import fetch


logger = logging.getLogger(__name__)


class HealthConnector:

    def fetch_csv(self, url: str, *, encoding: str = "utf-8") -> List[Dict[str, Any]]:
        try:
            response = fetch(url, method="GET", headers={"Accept": "text/csv,application/csv,text/plain"})
            if response.status_code != 200:
                logger.warning("health_csv_fetch_failed url=%s status=%s", url, response.status_code)
                return []
            content = response.content.decode(encoding, errors="replace")
            reader = csv.DictReader(io.StringIO(content))
            rows = [dict(row) for row in reader]
            logger.info("health_csv_fetched url=%s rows=%s", url, len(rows))
            return rows
        except Exception as exc:
            logger.error("health_csv_fetch_error url=%s error=%s", url, exc)
            return []

    def fetch_json(self, url: str, *, record_key: Optional[str] = None) -> List[Dict[str, Any]]:
        try:
            response = fetch(url, method="GET", headers={"Accept": "application/json"})
            if response.status_code != 200:
                logger.warning("health_json_fetch_failed url=%s status=%s", url, response.status_code)
                return []
            data = response.json()
            if record_key:
                records = data.get(record_key, [])
            elif isinstance(data, list):
                records = data
            elif isinstance(data, dict):
                for v in data.values():
                    if isinstance(v, list):
                        records = v
                        break
                else:
                    records = [data]
            else:
                records = []
            logger.info("health_json_fetched url=%s records=%s", url, len(records))
            return records
        except Exception as exc:
            logger.error("health_json_fetch_error url=%s error=%s", url, exc)
            return []

    def load_file(self, path: str) -> List[Dict[str, Any]]:
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                if path.endswith(".json"):
                    data = json.load(f)
                    if isinstance(data, list):
                        return data
                    for v in data.values():
                        if isinstance(v, list):
                            return v
                    return [data]
                else:
                    reader = csv.DictReader(f)
                    rows = [dict(row) for row in reader]
                    logger.info("health_file_loaded path=%s rows=%s", path, len(rows))
                    return rows
        except Exception as exc:
            logger.error("health_file_load_error path=%s error=%s", path, exc)
            return []
