from __future__ import annotations

import logging
from typing import List, Dict

from app.services.network.http_fetcher import fetch


logger = logging.getLogger(__name__)


GITHUB_SEARCH_URL = "https://api.github.com/search/repositories"


def search_menu_repositories(query: str = "restaurant menu json") -> List[Dict]:

    params = {
        "q": query,
        "per_page": 50,
    }

    try:

        response = fetch(
            GITHUB_SEARCH_URL,
            params=params,
        )

        if response.status_code != 200:
            return []

        data = response.json()

    except Exception as exc:

        logger.debug("github_repo_search_failed error=%s", exc)
        return []

    results: List[Dict] = []

    for repo in data.get("items", []):

        results.append(
            {
                "name": repo.get("name"),
                "full_name": repo.get("full_name"),
                "url": repo.get("html_url"),
            }
        )

    logger.info("github_repos_found count=%s", len(results))

    return results