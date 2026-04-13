def compute_crawl_priority(
    menu_exists: bool,
    image_count: int,
    last_crawled_days: int,
) -> float:
    """
    Score crawl priority for a place.
    Higher score = crawl sooner.
    """

    score = 0.0

    if not menu_exists:
        score += 5

    if image_count < 3:
        score += 2

    score += last_crawled_days * 0.1

    return score
