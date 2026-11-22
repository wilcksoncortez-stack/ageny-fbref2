"""Statistical intelligence built from data already stored in the agent.

This module deliberately avoids inventing missing metrics: it analyses completed
matches and numeric fields present in imported FBref CSV records.
"""
from __future__ import annotations
import math
import re
from collections import defaultdict
from sqlalchemy import select
from app.models import Match, DataRecord


def _num(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        s = str(value).strip().replace(',', '.')
        if not s or s in {'-', '—', 'N/A', 'nan'}:
            return None
        m = re.search(r'-?\d+(?:\.\d+)?', s)
        return float(m.group()) if m else None
    except (TypeError, ValueError):
        return None


def _match_rows(db, team=None):
    q = select(Match).where(Match.home_score.is_not(None), Match.away_score.is_not(None))
    if team:
        q = q.where((Match.home_team.ilike(f'%{team}%')) | (Match.away_team.ilike(f'%{team}%')))
    return db.scalars(q.order_by(Match.utc_date.desc())).all()


def team_profile(db, team_name):
    matches = _match_rows(db, team_name)
    played = wins = draws = losses = gf = ga = 0
    home = away = 0
    for m in matches:
        is_home = (m.home_team or '').casefold() == team_name.casefold()
        is_away = (m.away_team or '').casefold() == team_name.casefold()
        if not (is_home or is_away):
            continue
        played += 1
        home += int(is_home); away += int(is_away)
        scored, conceded = (m.home_score, m.away_score) if is_home else (m.away_score, m.home_score)
        gf += scored; ga += conceded
        wins += scored > conceded; draws += scored == conceded; losses += scored < conceded
    return {'team': team_name, 'matches': played, 'wins': wins, 'draws': draws, 'losses': losses,
            'goals_for': gf, 'goals_against': ga, 'goal_difference': gf-ga,
            'points': wins*3+draws, 'points_per_match': round((wins*3+draws)/played, 3) if played else None,
            'goals_for_per_match': round(gf/played, 3) if played else None,
            'goals_against_per_match': round(ga/played, 3) if played else None,
            'home_matches': home, 'away_matches': away,
            'sample_note': 'Calculado apenas com jogos concluídos existentes na base de dados.'}


def compare_teams(db, home, away):
    return {'home': team_profile(db, home), 'away': team_profile(db, away)}


def _poisson(lam, k):
    return math.exp(-lam) * (lam ** k) / math.factorial(k)


def predict_match(db, home, away):
    hp, ap = team_profile(db, home), team_profile(db, away)
    league = _match_rows(db)
    if not league or hp['matches'] < 1 or ap['matches'] < 1:
        return {'status': 'insufficient_data', 'home': home, 'away': away,
                'message': 'São necessários jogos concluídos das duas equipas e uma amostra histórica na base.'}
    league_gf = sum(m.home_score for m in league) / len(league)
    league_ga = sum(m.away_score for m in league) / len(league)
    # Home/away strength is estimated from each team's overall rates, shrunk toward league mean.
    h_for = (hp['goals_for_per_match'] * .65 + league_gf * .35)
    h_against = (hp['goals_against_per_match'] * .65 + league_ga * .35)
    a_for = (ap['goals_for_per_match'] * .65 + league_ga * .35)
    a_against = (ap['goals_against_per_match'] * .65 + league_gf * .35)
    home_xg = max(.05, (h_for + a_against) / 2 * 1.08)
    away_xg = max(.05, (a_for + h_against) / 2 * .92)
    max_goals = 10
    ph = [_poisson(home_xg, i) for i in range(max_goals+1)]
    pa = [_poisson(away_xg, i) for i in range(max_goals+1)]
    p1 = px = p2 = over15 = over25 = over35 = btts = 0.0
    scores = []
    for i, pi in enumerate(ph):
        for j, pj in enumerate(pa):
            p = pi * pj
            if i > j: p1 += p
            elif i == j: px += p
            else: p2 += p
            if i+j >= 2: over15 += p
            if i+j >= 3: over25 += p
            if i+j >= 4: over35 += p
            if i > 0 and j > 0: btts += p
            scores.append((p, i, j))
    total = p1+px+p2
    return {'status': 'estimated', 'home': home, 'away': away,
            'expected_goals': {'home': round(home_xg, 3), 'away': round(away_xg, 3)},
            'markets': {'1': round(p1/total, 4), 'X': round(px/total, 4), '2': round(p2/total, 4),
                        'over_1_5': round(over15, 4), 'over_2_5': round(over25, 4),
                        'over_3_5': round(over35, 4), 'btts_yes': round(btts, 4)},
            'most_likely_scores': [{'score': f'{i}-{j}', 'probability': round(p, 4)} for p,i,j in sorted(scores, reverse=True)[:5]],
            'method': 'Poisson simples com médias históricas e regressão parcial à média da amostra.',
            'sample': {'home_matches': hp['matches'], 'away_matches': ap['matches'], 'database_matches': len(league)},
            'warning': 'Estimativas estatísticas, não garantias nem aconselhamento financeiro.'}


def _fbref_rows(db, dataset=None):
    q = select(DataRecord).where(DataRecord.source == 'fbref_authorized_import')
    if dataset: q = q.where(DataRecord.dataset == dataset)
    rows = db.scalars(q.order_by(DataRecord.id.desc()).limit(10000)).all()
    result = []
    for r in rows:
        payload = r.payload or {}
        cols = payload.get('columns', payload)
        if isinstance(cols, dict):
            result.append({'dataset': r.dataset, 'season': r.season, 'competition': r.competition, **cols})
    return result


def player_profiles(db, dataset=None):
    rows = _fbref_rows(db, dataset)
    profiles = []
    for row in rows:
        name = row.get('Player') or row.get('player') or row.get('name')
        if not name: continue
        metrics = {k: v for k,v in row.items() if _num(v) is not None}
        profiles.append({'name': name, 'team': row.get('Squad') or row.get('Team'),
                         'position': row.get('Pos') or row.get('Position'), 'metrics': metrics,
                         'season': row.get('season'), 'competition': row.get('competition')})
    return profiles


def similar_players(db, player_name, dataset=None, limit=10):
    profiles = player_profiles(db, dataset)
    target = next((p for p in profiles if p['name'].casefold() == player_name.casefold()), None)
    if not target: return {'status': 'not_found', 'message': 'Jogador não encontrado nos CSVs FBref importados.'}
    keys = [k for k,v in target['metrics'].items() if _num(v) is not None and k.lower() not in {'age','born','shirtnumber'}]
    candidates = []
    for p in profiles:
        if p is target or p['name'] == target['name']: continue
        common = [k for k in keys if _num(p['metrics'].get(k)) is not None]
        if len(common) < 2: continue
        a = [_num(target['metrics'][k]) for k in common]
        b = [_num(p['metrics'][k]) for k in common]
        # Cosine similarity; raw metrics are used as supplied, without claiming normalization.
        dot = sum(x*y for x,y in zip(a,b)); na = math.sqrt(sum(x*x for x in a)); nb = math.sqrt(sum(y*y for y in b))
        sim = dot/(na*nb) if na and nb else 0
        candidates.append({'name': p['name'], 'team': p['team'], 'position': p['position'],
                           'similarity': round(sim,4), 'shared_metrics': len(common)})
    candidates.sort(key=lambda x: x['similarity'], reverse=True)
    return {'status': 'ok', 'player': target['name'], 'compared_metrics': keys,
            'similar_players': candidates[:limit],
            'note': 'Similaridade exploratória por cosseno sobre métricas numéricas importadas; comparar jogadores de funções/épocas distintas exige normalização.'}
