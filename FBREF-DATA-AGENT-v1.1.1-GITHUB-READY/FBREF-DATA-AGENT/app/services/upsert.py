from sqlalchemy import select
from app.models import Competition, Team, Player, Match, DataRecord

def upsert_competition(db, source, external_id, name, country=None, code=None, data=None):
    obj = db.scalar(select(Competition).where(Competition.source==source, Competition.external_id==str(external_id)))
    if obj is None:
        obj = Competition(source=source, external_id=str(external_id), name=name)
        db.add(obj)
    obj.name, obj.country, obj.code, obj.data = name, country, code, data or {}
    return obj

def upsert_team(db, source, external_id, name, country=None, data=None):
    obj = db.scalar(select(Team).where(Team.source==source, Team.external_id==str(external_id)))
    if obj is None:
        obj = Team(source=source, external_id=str(external_id), name=name)
        db.add(obj)
    obj.name, obj.country, obj.data = name, country, data or {}
    return obj

def upsert_player(db, source, external_id, name, team_name=None, position=None, data=None):
    obj = db.scalar(select(Player).where(Player.source==source, Player.external_id==str(external_id)))
    if obj is None:
        obj = Player(source=source, external_id=str(external_id), name=name)
        db.add(obj)
    obj.name, obj.team_name, obj.position, obj.data = name, team_name, position, data or {}
    return obj

def upsert_match(db, source, external_id, competition=None, season=None, utc_date=None,
                 home_team=None, away_team=None, home_score=None, away_score=None, status=None, data=None):
    obj = db.scalar(select(Match).where(Match.source==source, Match.external_id==str(external_id)))
    if obj is None:
        obj = Match(source=source, external_id=str(external_id))
        db.add(obj)
    for k, v in dict(competition=competition, season=season, utc_date=utc_date,
                     home_team=home_team, away_team=away_team, home_score=home_score,
                     away_score=away_score, status=status, data=data or {}).items():
        setattr(obj, k, v)
    return obj
