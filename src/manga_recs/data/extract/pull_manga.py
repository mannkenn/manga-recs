import logging

logger = logging.getLogger(__name__)


def fetch_manga_data(
    client,
    query,
    rate_limiter,
    avg_score: int = 70,
    popularity: int = 20000,
    per_page: int = 50,
) -> list[dict]:
    """Fetch every page of manga metadata matching the score/popularity floor.

    Args:
        client: GraphQL API client
        query: GraphQL query string
        rate_limiter: throttle applied before each request
        avg_score: minimum average score
        popularity: minimum popularity
        per_page: results per page

    Returns:
        Aggregated media entries across all pages.
    """
    page = 1
    all_manga: list[dict] = []

    while True:
        rate_limiter.wait()

        variables = {
            "page": page,
            "perPage": per_page,
            "type": "MANGA",
            "averageScoreGreater": avg_score,
            "popularityGreater": popularity,
        }
        result = client.query(query, variables)

        page_data = result["Page"]
        all_manga.extend(page_data["media"])
        logger.info("Fetched manga page %d (%d records so far)", page, len(all_manga))

        if not page_data["pageInfo"]["hasNextPage"]:
            break
        page += 1

    logger.info("Finished fetching %d manga records across %d pages", len(all_manga), page)
    return all_manga
