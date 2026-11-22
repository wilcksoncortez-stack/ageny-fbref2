from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from app.database import get_db
from app.models import Competition, Team, Player, Match, DataRecord, SyncRun
from app.security import require_admin
from app.services.collector import sync_all
from app.services.importer import import_fbref_csv

router = APIRouter(prefix="/api")

@router.get("/health")
def health(db: Session = Depends(get_db)):
    return {"status": "ok", "database": "connected", "service": "FBREF DATA AGENT"}

@router.get("/overview")
def overview(db: Session = Depends(get_db)):
    return {
        "competitions": db.scalar(select(func.count()).select_from(Competition)) or 0,
        "teams": db.scalar(select(func.count()).select_from(Team)) or 0,
        "players": db.scalar(select(func.count()).select_from(Player)) or 0,
        "matches": db.scalar(select(func.count()).select_from(Match)) or 0,
        "records": db.scalar(select(func.count()).select_from(DataRecord)) or 0,
        "last_sync": (lambda x: {"source": x.source, "status": x.status, "finished_at": x.finished_at.isoformat() if x.finished_at else None} if x else None)(
            db.scalar(select(SyncRun).order_by(SyncRun.id.desc()).limit(1)))
    }

@router.get("/competitions")
def competitions(db: Session = Depends(get_db), search: str | None = None, limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0)):
    q = select(Competition)
    if search: q = q.where(Competition.name.ilike(f"%{search}%"))
    rows = db.scalars(q.order_by(Competition.name).offset(offset).limit(limit)).all()
    return [{"id": x.id, "source": x.source, "external_id": x.external_id, "name": x.name, "country": x.country, "code": x.code, "updated_at": x.updated_at.isoformat()} for x in rows]

@router.get("/teams")
def teams(db: Session = Depends(get_db), search: str | None = None, limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0)):
    q = select(Team)
    if search: q = q.where(Team.name.ilike(f"%{search}%"))
    return [{"id": x.id, "source": x.source, "external_id": x.external_id, "name": x.name, "country": x.country, "data": x.data} for x in db.scalars(q.order_by(Team.name).offset(offset).limit(limit)).all()]

@router.get("/players")
def players(db: Session = Depends(get_db), search: str | None = None, limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0)):
    q = select(Player)
    if search: q = q.where(Player.name.ilike(f"%{search}%"))
    return [{"id": x.id, "source": x.source, "external_id": x.external_id, "name": x.name, "team": x.team_name, "position": x.position, "data": x.data} for x in db.scalars(q.order_by(Player.name).offset(offset).limit(limit)).all()]

@router.get("/matches")
def matches(db: Session = Depends(get_db), competition: str | None = None, season: str | None = None, team: str | None = None, limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0)):
    q = select(Match)
    if competition: q = q.where(Match.competition.ilike(f"%{competition}%"))
    if season: q = q.where(Match.season == season)
    if team: q = q.where((Match.home_team.ilike(f"%{team}%")) | (Match.away_team.ilike(f"%{team}%")))
    rows = db.scalars(q.order_by(Match.utc_date.desc()).offset(offset).limit(limit)).all()
    return [{"id": x.id, "source": x.source, "external_id": x.external_id, "competition": x.competition, "season": x.season, "date": x.utc_date, "home": x.home_team, "away": x.away_team, "home_score": x.home_score, "away_score": x.away_score, "status": x.status, "data": x.data} for x in rows]

@router.get("/records")
def records(db: Session = Depends(get_db), source: str | None = None, dataset: str | None = None, limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0)):
    q = select(DataRecord)
    if source: q = q.where(DataRecord.source == source)
    if dataset: q = q.where(DataRecord.dataset == dataset)
    rows = db.scalars(q.order_by(DataRecord.id.desc()).offset(offset).limit(limit)).all()
    return [{"id": x.id, "source": x.source, "dataset": x.dataset, "competition": x.competition, "season": x.season, "payload": x.payload, "imported_at": x.imported_at.isoformat()} for x in rows]

@router.get("/sources")
def sources():
    from app.sources.football_data import FootballDataClient
    from app.config import settings
    return [
        {"id": "fbref_authorized_import", "name": "FBref (importação autorizada)", "mode": "CSV/manual", "status": "ready", "note": "Sem scraping automático."},
        {"id": "football-data.org", "name": "football-data.org", "mode": "API", "status": "configured" if FootballDataClient().configured else "needs_token"},
        {"id": "statsbomb_open_data", "name": "StatsBomb Open Data", "mode": "JSON open data", "status": "enabled" if settings.stats_bomb_open_data else "disabled"}
    ]

@router.post("/admin/sync", dependencies=[Depends(require_admin)])
async def run_sync():
    return {"results": await sync_all()}

@router.post("/import/fbref", dependencies=[Depends(require_admin)])
async def import_fbref(dataset: str = "standard", season: str | None = None, competition: str | None = None,
                       file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Envie um ficheiro CSV.")
    content = await file.read()
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Ficheiro excede 20 MB.")
    try:
        count = import_fbref_csv(db, content, dataset, season, competition)
        return {"status": "success", "source": "fbref_authorized_import", "dataset": dataset, "records_imported": count}
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Falha ao importar CSV: {exc}")

@router.post("/admin/statsbomb/events/{match_id}", dependencies=[Depends(require_admin)])
async def import_statsbomb_events(match_id: int, db: Session = Depends(get_db)):
    from app.sources.statsbomb import StatsBombOpenData
    try:
        events = await StatsBombOpenData().events(match_id)
        db.add(DataRecord(source="statsbomb_open_data", dataset="events", external_id=str(match_id),
                          payload={"match_id": match_id, "events": events}))
        db.commit()
        return {"status": "success", "match_id": match_id, "events": len(events)}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Não foi possível obter eventos: {exc}")

@router.get("/sync-runs")
def sync_runs(db: Session = Depends(get_db), limit: int = Query(20, ge=1, le=100)):
    rows = db.scalars(select(SyncRun).order_by(SyncRun.id.desc()).limit(limit)).all()
    return [{"id": x.id, "source": x.source, "status": x.status, "message": x.message, "records": x.records_count,
             "started_at": x.started_at.isoformat(), "finished_at": x.finished_at.isoformat() if x.finished_at else None} for x in rows]
