import time
import httpx
from typing import Optional


class ChessComClient:
    BASE = "https://api.chess.com/pub"
    HEADERS = {"User-Agent": "chess-cli/0.1"}
    SLEEP = 0.1  # seconds between requests

    def __init__(self):
        self._client = httpx.Client(headers=self.HEADERS, timeout=30)

    def _get(self, url: str) -> dict:
        resp = self._client.get(url)
        resp.raise_for_status()
        return resp.json()

    def get_archives(self, username: str) -> list[str]:
        data = self._get(f"{self.BASE}/player/{username}/games/archives")
        return data.get("archives", [])

    def get_games(self, archive_url: str) -> list[dict]:
        time.sleep(self.SLEEP)
        data = self._get(archive_url)
        return data.get("games", [])

    def get_stats(self, username: str) -> dict:
        return self._get(f"{self.BASE}/player/{username}/stats")

    def close(self):
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
