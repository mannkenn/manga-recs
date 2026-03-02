import requests, time, json
import pandas as pd
from typing import Dict, Any

class MangaGraphQLClient:
    '''
    GraphQL API Client
    '''
    
    def __init__(self, url: str, timeout: int = 10):
        self.url = url.rstrip("/")
        self.session = requests.Session()
        self.timeout = timeout

    def _retry_delay(self, response: requests.Response, attempt: int) -> float:
        retry_after = response.headers.get("Retry-After")
        if retry_after is not None:
            try:
                return max(float(retry_after), 0.0)
            except ValueError:
                pass

        rate_limit_reset = response.headers.get("X-RateLimit-Reset")
        if rate_limit_reset is not None:
            try:
                reset_at = float(rate_limit_reset)
                wait_seconds = reset_at - time.time()
                if wait_seconds > 0:
                    return wait_seconds
            except ValueError:
                pass

        return float(min(2 ** attempt, 60))
        
    def query(self, query: str, variables: dict | None = None, max_retries: int = 8) -> Dict:
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

        retryable_statuses = {429, 500, 502, 503, 504}
        last_exception = None

        for attempt in range(1, max_retries + 1):
            response = self.session.post(
                self.url,
                json=payload,
                timeout=self.timeout
            )

            if response.status_code in retryable_statuses and attempt < max_retries:
                time.sleep(self._retry_delay(response, attempt))
                continue

            try:
                response.raise_for_status()
            except requests.HTTPError as exc:
                response_text = response.text[:500]
                raise requests.HTTPError(
                    f"GraphQL request failed with {response.status_code} at {self.url}. "
                    f"Response: {response_text}",
                    response=response,
                ) from exc

            try:
                result = response.json()
            except ValueError as exc:
                raise ValueError(
                    f"Non-JSON response from GraphQL endpoint {self.url}: {response.text[:500]}"
                ) from exc

            if "errors" in result:
                last_exception = Exception(result["errors"])
                error_blob = json.dumps(result["errors"]).lower()
                if attempt < max_retries:
                    if "too many requests" in error_blob or '"status": 429' in error_blob:
                        time.sleep(self._retry_delay(response, attempt))
                    else:
                        time.sleep(min(2 ** attempt, 8))
                    continue
                raise last_exception

            return result["data"]

        if last_exception is not None:
            raise last_exception
        raise RuntimeError("GraphQL query failed without a response.")
    
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
