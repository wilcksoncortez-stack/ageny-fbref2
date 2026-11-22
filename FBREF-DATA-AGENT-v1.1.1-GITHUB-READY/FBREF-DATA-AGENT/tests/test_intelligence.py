from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.database import Base
from app.models import Match, DataRecord
from app.services.intelligence import team_profile, predict_match, similar_players


def make_db():
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    return Session(engine)


def test_team_profile_counts_completed_matches():
    db = make_db()
    db.add_all([
        Match(source='test', external_id='1', home_team='Arsenal', away_team='Chelsea', home_score=2, away_score=1),
        Match(source='test', external_id='2', home_team='Liverpool', away_team='Arsenal', home_score=0, away_score=0),
    ])
    db.commit()
    profile = team_profile(db, 'Arsenal')
    assert profile['matches'] == 2
    assert profile['wins'] == 1
    assert profile['draws'] == 1
    assert profile['points'] == 4
    db.close()


def test_prediction_returns_markets_with_history():
    db = make_db()
    db.add_all([
        Match(source='test', external_id='1', home_team='Arsenal', away_team='Chelsea', home_score=2, away_score=1),
        Match(source='test', external_id='2', home_team='Chelsea', away_team='Arsenal', home_score=0, away_score=2),
        Match(source='test', external_id='3', home_team='Liverpool', away_team='Chelsea', home_score=1, away_score=1),
    ])
    db.commit()
    result = predict_match(db, 'Arsenal', 'Chelsea')
    assert result['status'] == 'estimated'
    assert set(['1', 'X', '2', 'over_2_5', 'btts_yes']).issubset(result['markets'])
    assert abs(sum(result['markets'][k] for k in ['1', 'X', '2']) - 1) < 0.001
    db.close()


def test_similar_players_returns_not_found_without_imported_data():
    db = make_db()
    assert similar_players(db, 'Unknown Player')['status'] == 'not_found'
    db.close()
