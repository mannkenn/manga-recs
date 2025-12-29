from typing import List, Dict

def fetch_all_pages(client, query, avg_score: int = 70, popularity: int = 20000, per_page: int = 50) -> List[Dict]:
    '''
    Fetches manga metadata from all pages based on arguments

    Args:
        avg_score (int): Minimum avg score of manga
        popularity (int): Minimum popularity of manga
        per_page (int): Results per page

    Returns:
        Array of response data as dict
    '''

    page = 1
    all_manga = []

    # Go through all pages
    while True:

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

        page += 1
    
    return all_manga


