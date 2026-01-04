from typing import List, Dict

def fetch_user_data(client, query) -> List[Dict]:
    '''
    Fetches user data from all pages based on arguments

    Args:
        

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


