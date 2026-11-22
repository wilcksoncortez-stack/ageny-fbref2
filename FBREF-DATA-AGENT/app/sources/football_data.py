import httpx
from app.config import settings

class FootballDataClient:
    name = "football-data.org"

    def __init__(self):
        self.base = settings.football_data_base_url.rstrip("/")
        self.headers = {"X-Auth-Token": settings.football_data_token} if settings.football_data_token else {}

    @property
    def configured(self):
        return bool(settings.football_data_token)

    async def get(self, path: str, params=None):
        if not self.configured:
            raise RuntimeError("FOOTBALL_DATA_TOKEN não configurado.")
        async with httpx.AsyncClient(timeout=settings.request_timeout) as client:
            response = await client.get(f"{self.base}/{path.lstrip('/')}", headers=self.headers, params=params)
            response.raise_for_status()
            return response.json()

    async def competitions(self):
        return await self.get("competitions")

    async def matches(self, code: str, season: int | None = None):
        params = {"season": season} if season else None
        return await self.get(f"competitions/{code}/matches", params=params)
