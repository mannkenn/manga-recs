import requests
import json
from typing import Dict, Optional

class MangaAPIClient:
    '''
    Manga API client with error handling 
    '''

    def __init__(self, base_url: str, timeout: int = 10):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.session = requests.Session()

    def _build_url(self, endpoint: str) -> str:
        '''Construct full URL from base URL and endpoint'''
        return f"{self.base_url}/{endpoint.lstrip('/')}" 

    def get(self, endpoint: str, params: Optional[Dict] = None,
            headers: Optional[Dict] = None) -> Dict:
        '''
        Make GET request to API endpoint

        Args:
            endpoint: API endpoint path
            params: Query parameters
            headers: additional headers 
        
        Returns: 
            Response data as dictionary

        '''
        url = self._build_url(endpoint)

        # Make safe requests
        try:
            response = self.session.get(
                params=params,
                headers=headers,
                timeout=self.timeout
            )
            response.raise_for_status() # Raise exceptions
            return response.json()  
        
        except requests.exceptions.Timeout:
            print(f'Request timed out for {url}')
            raise
        except requests.exceptions.ConnectionError:
            print(f'Connection error out for {url}')
            raise
        except requests.exceptions.HTTPError as e:
            print(f'HTTP error {e.response.status_code}: {e.response.text}')
            raise
        except json.JSONDecodeError:
            print(f'Invalid JSON response from {url}')
            print(f'Response text: {response.text}')
            raise
        
client = MangaAPIClient('https://graphql.anilist.co').get()

    
    
