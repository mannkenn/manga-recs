import requests
from typing import Dict

class MangaGraphQLClient:
    '''
    GraphQL API Client
    '''
    
    def __init__(self, url: str, timeout: int = 10):
        self.url = url
        self.session = requests.Session()
        self.timeout = timeout
        
    def query(self, query: str, variables: dict | None = None) -> Dict:
        '''
        Construct GraphQL query with variables

        Args:
            query (str): GraphQL query
            variables (dict, optional): dynamic values to queries

        Returns:
            Response data as dictionary  
        '''

        payload = {"query": query}
        if variables:
            payload["variables"] = variables

        response = self.session.post(
            self.url,
            json=payload,
            timeout=self.timeout
        )
        response.raise_for_status()     
        result = response.json()

        if "errors" in result:
            raise Exception(result["errors"])

        return result["data"]
