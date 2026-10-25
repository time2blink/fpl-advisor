"""Вырезает из tool/out/data.json компактный набор для мобильного прототипа -> mobile/data.js.
Запуск: python -X utf8 build_data.py"""
import json, pathlib

HERE = pathlib.Path(__file__).parent
d = json.load(open(HERE.parent / 'tool' / 'out' / 'data.json', encoding='utf-8'))
P = {p['id']: p for p in d['players']}
AN = {int(k): v for k, v in d['all_names'].items()}

ids = set()
def add(*xs):
    for x in xs:
        if isinstance(x, int): ids.add(x)

for p in d['me']['squad']: add(p['id'])
cl = d['claude_lineup']
for k in ('xi', 'bench'): add(*cl[k])
for s in d['plan']['steps']:
    for m in s['moves']: add(*m)
    add(s.get('captain'))
for s in d['sugg']['single'][:8]: add(s['out'], s['inn'])
for t in d['threats']['intercept'][:8]: add(t['id'])
for w in d['watch']:
    pass
for k in ('rising', 'falling', 'my_risk', 'my_gain'):
    for m in d['market'][k][:6]: add(m['id'])
for k in ('roma', 'stas'):
    add(*d['holdings'][k])
add(*[int(k) for k in d['threats']['deny']][:0])
for w in d['watch']:
    nm = w['player']
    for p in d['players']:
        if f"{p['name']}:{p['tname']}" == nm: add(p['id'])

TOP = d['top']
for k in ('ins_list', 'outs_list', 'caps_list'):
    for i, _ in TOP[k][:14]: add(i)
for i, _ in TOP['owned_list'][:20]: add(i)
CH = d['changes']
for x in CH['price'][:40] + CH['status'][:40] + CH['own_up'][:8] + CH['own_down'][:8]: add(x['id'])
for k, v in d['friend_moves'].items():
    add(*v['sold'], *v['bought'])

def pl(i):
    p = P.get(i)
    if not p:
        a = AN.get(i, {})
        return {'id': i, 'name': a.get('name', '?'), 'tname': a.get('team', ''), 'pos': a.get('pos', ''), 'price': a.get('price', 0), 'min': True}
    keep = ['id', 'name', 'full', 'tname', 'pos', 'pcode', 'tcode', 'price', 'price_start', 'own', 'form', 'ppg', 'pts',
            'status', 'news', 'chance', 'xp1', 'xp5', 'fix', 'xgi90', 'dc90', 'goals', 'assists', 'bonus', 'minutes',
            'mfrac', 'taken_by', 'top_cnt', 'ptrend', 'press', 'xpg', 'sp']
    o = {k: p.get(k) for k in keep}
    o['series'] = [{'gw': s['gw'], 'pts': s['pts'], 'min': s['min']} for s in p.get('series', [])][-8:]
    o['fix'] = o['fix'][:5]
    o['xpg'] = (o['xpg'] or [])[:6]
    return o

players = {i: pl(i) for i in sorted(ids)}

def mgr(m):
    return {'team': m.get('team'), 'manager': m.get('manager'), 'overall_pts': m.get('overall_pts'), 'bank': m.get('bank'),
            'value': m.get('value'), 'ft': m.get('ft_estimate'), 'chips': [c['label'] for c in m.get('chips', [])],
            'gw_points': m.get('gw_points', []), 'hits_lost': m.get('hits_lost'), 'bench_lost': m.get('bench_lost'),
            'name': m.get('name'), 'fav': (m.get('fav_team') or {}).get('code'), 'fav_name': (m.get('fav_team') or {}).get('name')}

out = {
    'meta': d['meta'],
    'me': {**mgr(d['me']), 'rank': d['me']['overall_rank'], 'squad': [{'id': s['id'], 'slot': s['pos_slot'], 'sell': s['sell'], 'now': s['now']} for s in d['me']['squad']]},
    'roma': mgr(d['league']['roma']), 'stas': mgr(d['league']['stas']),
    'table': d['league_table'],
    'names': d['league_names'],
    'players': players,
    'claude': {k: cl[k] for k in ('gw', 'updated', 'status', 'summary', 'formation', 'xi', 'bench', 'captain', 'vice', 'notes', 'tags')},
    'plan': d['plan'], 'chips': d['chips'], 'race': d['race'],
    'single': d['sugg']['single'][:6],
    'intercept': d['threats']['intercept'][:6],
    'friends': d['threats']['friends'],
    'live': {'state': d['live']['state'], 'gw': d['live']['gw'], 'managers': {k: {kk: v[kk] for kk in ('pts', 'hit', 'played', 'to_play')} for k, v in d['live']['managers'].items()}},
    'holdings': d['holdings'],
    'watch': d['watch'][:10],
    'market': {k: d['market'][k][:6] for k in ('rising', 'falling', 'my_risk', 'my_gain')},
    'teams': d['teams'],
    'top': {'n': TOP['n'], 'ins': TOP['ins_list'][:14], 'outs': TOP['outs_list'][:14], 'caps': TOP['caps_list'][:8], 'chips': TOP['chips'], 'owned': TOP['owned_list'][:20]},
    'changes': {'prev_ts': CH.get('prev_ts'), 'price': CH['price'][:40], 'status': CH['status'][:40], 'own_up': CH['own_up'][:8], 'own_down': CH['own_down'][:8]},
    'friend_moves': d['friend_moves'],
    'defaults': {'league_id': d['meta'].get('league_id'), 'entries': {'me': d['me'].get('entry'), 'roma': d['league']['roma'].get('entry'), 'stas': d['league']['stas'].get('entry')}, 'top_n': TOP['n']},
}
(HERE / 'data.js').write_text('window.FPL=' + json.dumps(out, ensure_ascii=False, separators=(',', ':')) + ';', encoding='utf-8')
print('players', len(players), 'bytes', (HERE / 'data.js').stat().st_size)
