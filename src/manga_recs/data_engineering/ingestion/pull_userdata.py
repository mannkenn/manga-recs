from typing import List, Dict

def fetch_user_data(client, query, rate_limiter, per_page: int = 50, max_pages = 1000) -> List[Dict]:
    """
    Fetches paginated user read data from AniList GraphQL API.

    Args:
        client: GraphQL API client
        query (str): GraphQL query string
        per_page (int): Number of items per page

    Returns:
        List[Dict]: Aggregated mediaList entries across all pages
    """

    page = 1
    all_media = []

    # Go through all pages
    while page < max_pages:
        rate_limiter.wait()
        # input variables 
        variables = {
            'page': page,
            'perPage': per_page,
            'type': 'MANGA',
        }
        result = client.query(query, variables)
        
        page_data = result["Page"]
        all_media.extend(page_data["mediaList"])

        if not page_data["pageInfo"]["hasNextPage"]:
            break
        
        print(f"Fetched page {page}")
        page += 1
        
    print(f"Finished Fetching {page}'s of user data.")
    return all_media


