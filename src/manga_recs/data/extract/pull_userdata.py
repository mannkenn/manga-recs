from typing import List, Dict
import requests

def fetch_user_data(
    client,
    query,
    rate_limiter,
    per_page: int = 50,
    max_pages: int = 1000,
    start_user_id: int = 1,
    end_user_id: int = 1000,
) -> List[Dict]:
    """
    Fetches paginated manga list data from AniList GraphQL API for a user ID range.

    Args:
        client: GraphQL API client
        query (str): GraphQL query string
        per_page (int): Number of items per page
        max_pages (int): Maximum pages to fetch per user
        start_user_id (int): Starting user ID (inclusive)
        end_user_id (int): Ending user ID (inclusive)

    Returns:
        List[Dict]: Aggregated mediaList entries across all users and pages
    """
    all_media = []

    for user_id in range(start_user_id, end_user_id + 1):
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
                result = client.query(query, variables)
            except requests.HTTPError as exc:
                response_text = ""
                status_code = None
                if exc.response is not None and exc.response.text:
                    response_text = exc.response.text.lower()
                    status_code = exc.response.status_code

                if "private user" in response_text or "not found" in response_text:
                    skipped_user = True
                    print(f"Skipping user {user_id}: private or unavailable")
                    break

                if status_code in {500, 502, 503, 504} or "internal server error" in response_text:
                    skipped_user = True
                    print(f"Skipping user {user_id}: AniList server error after retries")
                    break

                raise

            page_data = result["Page"]
            media_list = page_data["mediaList"]
            all_media.extend(media_list)
            fetched_for_user += len(media_list)

            if not page_data["pageInfo"]["hasNextPage"]:
                break

            page += 1

        if not skipped_user:
            print(f"Fetched {fetched_for_user} records for user {user_id}")

    print(
        f"Finished fetching user data for {end_user_id - start_user_id + 1} users. "
        f"Total records: {len(all_media)}"
    )
    return all_media


