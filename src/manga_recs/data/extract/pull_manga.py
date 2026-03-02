from typing import List, Dict

def fetch_manga_data(client, query, rate_limiter, avg_score: int = 70, popularity: int = 20000, per_page: int = 50) -> List[Dict]:
    '''
    Fetches manga metadata from all pages based on arguments

    Args:
        client: GraphQL API client
        query (str): GraphQL query string
        avg_score (int): Minimum avg score of manga
        popularity (int): Minimum popularity of manga
        per_page (int): Results per page

    Returns:
        List[Dict]: Aggregated mediaList entries across all pages
    '''

    page = 1
    all_manga = []

    # Go through all pages
    while True:
        rate_limiter.wait()

        # input variables 
        variables = {
            'page': page,
            'perPage': per_page,
            'type': 'MANGA',
            'averageScoreGreater': avg_score,
            'popularityGreater': popularity
        }
        result = client.query(query, variables)
        
        page_data = result["Page"]
        all_manga.extend(page_data["media"])

        if not page_data["pageInfo"]["hasNextPage"]:
            break
        print(f"Fetched page {page}")
        page += 1
        
    print(f"Finished Fetching {page} pages of manga data.")
    return all_manga



