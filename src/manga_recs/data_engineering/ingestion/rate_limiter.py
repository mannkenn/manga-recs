import time

class RateLimiter:
    def __init__(self, requests_per_minute: int):
        self.delay = 60 / requests_per_minute
        self.last_call = 0.0

    def wait(self):
        elapsed = time.time() - self.last_call
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)
        self.last_call = time.time()
