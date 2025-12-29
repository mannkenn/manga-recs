import requests

class MangaGraphQLClient:
    def __init__(self, url):
        self.url = url

    def query(self, query, variables=None):
        payload = {"query": query}
        if variables:
            payload["variables"] = variables

        response = requests.post(self.url, json=payload)
        result = response.json()

        if "errors" in result:
            raise Exception(result["errors"])

        return result["data"]
        

    
    
