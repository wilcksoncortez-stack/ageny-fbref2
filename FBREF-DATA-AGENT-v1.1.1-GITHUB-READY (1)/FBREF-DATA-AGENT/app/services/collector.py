from datetime import datetime
from sqlalchemy import func, select
from app.database import SessionLocal
from app.models import SyncRun, DataRecord, Competition
from app.sources.football_data import FootballDataClient
from app.sources.statsbomb import StatsBombOpenData
from app.services.upsert import upsert_competition, upsert_team, upsert_player, upsert_match

def _score(match, side):
    return ((match.get("score") or {}).get("fullTime") or {}).get(side)

async def sync_football_data():
    client = FootballDataClient()
    if not client.configured:
        return {"source": client.name, "status": "skipped", "message": "Token não configurado.", "records": 0}
    db = SessionLocal()
    run = SyncRun(source=client.name, status="running", message="A sincronizar catálogo de competições.")
    db.add(run); db.commit()
    count = 0
    try:
        payload = await client.competitions()
        for c in payload.get("competitions", []):
            upsert_competition(db, client.name, c.get("id"), c.get("name", "Unknown"),
                               (c.get("area") or {}).get("name"), c.get("code"), c)
            count += 1
        db.commit()
        # Sync current season matches for competitions available to the token.
        for c in payload.get("competitions", []):
            code = c.get("code")
            if not code:
                continue
            try:
                result = await client.matches(code)
                for m in result.get("matches", []):
                    home, away = m.get("homeTeam") or {}, m.get("awayTeam") or {}
                    upsert_team(db, client.name, home.get("id") or home.get("name"), home.get("name", "Unknown"), data=home)
                    upsert_team(db, client.name, away.get("id") or away.get("name"), away.get("name", "Unknown"), data=away)
                    season = (m.get("season") or {}).get("startDate", "")[:4] or None
                    upsert_match(db, client.name, m.get("id"), (m.get("competition") or {}).get("name"),
                                 season, m.get("utcDate"), home.get("name"), away.get("name"),
                                 _score(m, "home"), _score(m, "away"), m.get("status"), m)
                    count += 1
                db.commit()
            except Exception as exc:
                db.add(DataRecord(source=client.name, dataset="sync_warning", payload={"competition": code, "error": str(exc)}))
                db.commit()
        run.status, run.message, run.records_count = "success", "Catálogo e jogos sincronizados; cobertura depende do plano do fornecedor.", count
    except Exception as exc:
        db.rollback()
        run.status, run.message = "error", str(exc)
    finally:
        run.finished_at = datetime.utcnow()
        db.commit()
        db.close()
    return {"source": client.name, "status": run.status, "message": run.message, "records": count}

async def sync_statsbomb_catalog():
    client = StatsBombOpenData()
    db = SessionLocal()
    run = SyncRun(source=client.name, status="running", message="A importar catálogo aberto.")
    db.add(run); db.commit()
    count = 0
    try:
        competitions = await client.competitions()
        for c in competitions:
            cid, sid = c.get("competition_id"), c.get("season_id")
            label = f'{c.get("competition_name", "Competition")} — {c.get("season_name", "Season")}'
            upsert_competition(db, client.name, f"{cid}:{sid}", label, c.get("country_name"), str(cid), c)
            count += 1
        db.commit()
        # Match/event data can be large. Import match metadata; events are fetched on demand via endpoint.
        seen = set()
        for c in competitions:
            cid, sid = c.get("competition_id"), c.get("season_id")
            if (cid, sid) in seen: continue
            seen.add((cid, sid))
            try:
                matches = await client.matches(cid, sid)
                for m in matches:
                    home = (m.get("home_team") or {}).get("home_team_name")
                    away = (m.get("away_team") or {}).get("away_team_name")
                    mid = m.get("match_id")
                    upsert_match(db, client.name, mid, f'{c.get("competition_name")}', str(c.get("season_name")),
                                 m.get("match_date"), home, away,
                                 (m.get("home_score")), (m.get("away_score")), "FINISHED", m)
                    count += 1
                db.commit()
            except Exception as exc:
                db.add(DataRecord(source=client.name, dataset="sync_warning", payload={"competition_id": cid, "season_id": sid, "error": str(exc)}))
                db.commit()
        run.status, run.message, run.records_count = "success", "Catálogo e metadados de jogos importados; eventos disponíveis sob pedido.", count
    except Exception as exc:
        db.rollback()
        run.status, run.message = "error", str(exc)
    finally:
        run.finished_at = datetime.utcnow()
        db.commit(); db.close()
    return {"source": client.name, "status": run.status, "message": run.message, "records": count}

async def sync_all():
    results = [await sync_football_data()]
    from app.config import settings
    if settings.stats_bomb_open_data:
        results.append(await sync_statsbomb_catalog())
    return results
