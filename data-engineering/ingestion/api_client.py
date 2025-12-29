import requests

class MangaGraphQLClient:
    def __init__(self, url, timeout=10):
        self.url = url
        self.session = requests.Session()
        self.timeout = timeout
        
    def query(self, query: str, variables: dict | None = None) -> dict:
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
