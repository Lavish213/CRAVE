from __future__ import annotations

import logging
from typing import List, Dict

from app.services.network.http_fetcher import fetch


logger = logging.getLogger(__name__)


def fetch_repo_files(repo_full_name: str) -> List[Dict]:

    url = f"https://api.github.com/repos/{repo_full_name}/contents"

    try:

        response = fetch(url)

        if response.status_code != 200:
            return []

        data = response.json()

    except Exception as exc:

        logger.debug("github_repo_fetch_failed error=%s", exc)
        return []

    files: List[Dict] = []

    for item in data:

        files.append(
            {
                "name": item.get("name"),
                "path": item.get("path"),
                "download_url": item.get("download_url"),
            }
        )

    return files