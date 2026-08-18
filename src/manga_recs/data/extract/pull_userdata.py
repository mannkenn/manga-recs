import logging

import requests

from manga_recs.data.utils import GraphQLQueryError

logger = logging.getLogger(__name__)


def fetch_user_data(
    client,
    query,
    rate_limiter,
    per_page: int = 50,
    max_pages: int = 10,
    start_user_id: int = 1,
    end_user_id: int = 1000,
    max_retries: int = 3,
) -> list[dict]:
    """Fetch manga read lists for a range of AniList user ids.

    Many ids in any range are private, deleted, or empty; those are skipped
    rather than treated as failures. ``max_pages`` bounds the cost of a single
    user so one very large library cannot dominate the run.

    ``max_retries`` is deliberately low. An individual user is optional data, and
    AniList returns 500s for some accounts persistently, so a long exponential
    backoff spends minutes per user to learn something a couple of attempts
    already established.

    Args:
        client: GraphQL API client
        query: GraphQL query string
        per_page: entries per page
        max_pages: maximum pages to fetch per user
        start_user_id: starting user id (inclusive)
        end_user_id: ending user id (inclusive)
        max_retries: attempts per request before skipping the user

    Returns:
        Aggregated mediaList entries across all users and pages.
    """
    all_media: list[dict] = []
    total_users = end_user_id - start_user_id + 1
    users_with_data = 0
    users_skipped = 0

    for index, user_id in enumerate(range(start_user_id, end_user_id + 1), start=1):
        page = 1
        fetched_for_user = 0
        skipped_user = False

        while page <= max_pages:
            rate_limiter.wait()
            variables = {
                "userId": user_id,
                "page": page,
                "perPage": per_page,
                "type": "MANGA",
            }
            try:
                result = client.query(query, variables, max_retries=max_retries)
            except requests.HTTPError as exc:
                response_text = ""
                status_code = None
                if exc.response is not None and exc.response.text:
                    response_text = exc.response.text.lower()
                    status_code = exc.response.status_code

                if "private user" in response_text or "not found" in response_text:
                    skipped_user = True
                    logger.debug("Skipping user %d: private or unavailable", user_id)
                    break

                if status_code in {500, 502, 503, 504} or "internal server error" in response_text:
                    skipped_user = True
                    logger.warning("Skipping user %d: AniList server error after retries", user_id)
                    break

                raise
            except (GraphQLQueryError, requests.Timeout, requests.ConnectionError) as exc:
                # One user's read list is optional data; never fail the whole run for it.
                skipped_user = True
                logger.warning("Skipping user %d: %s", user_id, type(exc).__name__)
                break

            page_data = result["Page"]
            media_list = page_data["mediaList"]
            all_media.extend(media_list)
            fetched_for_user += len(media_list)

            if not page_data["pageInfo"]["hasNextPage"]:
                break

            page += 1

        if skipped_user:
            users_skipped += 1
        if fetched_for_user:
            users_with_data += 1
        if page > max_pages:
            logger.debug("User %d hit the %d-page cap", user_id, max_pages)

        if index % 25 == 0 or index == total_users:
            logger.info(
                "Users %d/%d scanned | %d with data | %d skipped | %d entries collected",
                index,
                total_users,
                users_with_data,
                users_skipped,
                len(all_media),
            )

    logger.info(
        "Finished %d users: %d had data, %d skipped, %d total entries",
        total_users,
        users_with_data,
        users_skipped,
        len(all_media),
    )
    return all_media
