import httpx
from app.config import settings

BASE = "https://raw.githubusercontent.com/hudl/open-data/master/data"

class StatsBombOpenData:
    name = "statsbomb_open_data"

    async def fetch_json(self, path: str):
        async with httpx.AsyncClient(timeout=settings.request_timeout, follow_redirects=True) as client:
            r = await client.get(f"{BASE}/{path}")
            r.raise_for_status()
            return r.json()

    async def competitions(self):
        return await self.fetch_json("competitions.json")

    async def matches(self, competition_id: int, season_id: int):
        return await self.fetch_json(f"matches/{competition_id}/{season_id}.json")

    async def events(self, match_id: int):
        return await self.fetch_json(f"events/{match_id}.json")
