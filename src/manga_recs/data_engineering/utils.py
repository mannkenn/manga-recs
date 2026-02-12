import requests, time, json
import pandas as pd
from typing import Dict, Any

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
    
class RateLimiter:
    def __init__(self, requests_per_minute: int):
        self.delay = 60 / requests_per_minute
        self.last_call = 0.0

    def wait(self):
        elapsed = time.time() - self.last_call
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)
        self.last_call = time.time()

def load_json(filepath: str) -> Any:
    """Load JSON file safely (UTF-8, Windows compatible)."""
    with open(filepath, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def save_json(data: Any, filepath: str) -> None:
    """Save data to JSON file."""
    with open(filepath, 'w', encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_parquet(filepath: str) -> pd.DataFrame:
    """Load parquet file into DataFrame."""
    return pd.read_parquet(str(filepath))


def save_parquet(data: pd.DataFrame, filepath: str) -> None:
    """Save DataFrame to parquet file."""
    data.to_parquet(str(filepath))
