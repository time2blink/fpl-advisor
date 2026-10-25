#!/usr/bin/env python3
"""Генератор ДЕМО-данных (формат как у API FPL) для проверки инструмента без сети.
Запуск:  python tests/make_mock.py   затем   python fpl_tool.py --offline
"""
import json
import os
import random
import sys
import datetime as dt

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import fpl_tool  # noqa

random.seed(7)
OUT = os.path.join(os.path.dirname(HERE), "mock")
os.makedirs(OUT, exist_ok=True)


def put(path, obj):
    with open(fpl_tool._mock_name(path), "w", encoding="utf-8") as f:
        json.dump(obj, f)


TEAMS = ["ARS", "AVL", "BOU", "BRE", "BHA", "CHE", "COV", "CRY", "EVE", "FUL", "HUL", "IPS", "LEE", "LIV", "MCI", "MUN", "NEW", "NFO", "TOT", "SUN"]
SURN = ("Haaland Isak Calafiori Groß Rogers Palmer Raya Konsa Neto Mbeumo Foden Gabriel Egan Thomas Williams Greaves "
        "Ødegaard Verbruggen Tzolakis DeCuyper Boscagli Gomez Ayari Tavernier Barry Brobbey Solanke Trafford Saka Cherki "
        "Wissa Evanilson Gonzalo Timber Muñoz Leno Bruno Rice Vušković Kostoulas Thiago Rúben Virgil Mitchell Semenyo "
        "Szoboszlai Mateta Delap Belloumi Maeda Ouattara Tarkowski Kinsky Dubravka Justin Bogle Dunk Kadıoğlu Lewis-Potter "
        "Iwobi Bobb Cunha Jackson Havertz Gakpo Doku Barcola Hall Schade Barnes Ndiaye Slater Diop Davis O'Shea").split()

elements = []
eid = 1
by_team_pos = {}
for ti, tn in enumerate(TEAMS, start=1):
    comp = [(1, 3), (2, 8), (3, 9), (4, 4)]
    for pos, cnt in comp:
        for k in range(cnt):
            name = SURN[(eid - 1) % len(SURN)] if eid <= len(SURN) else "Player%d" % eid
            if eid > len(SURN):
                name = random.choice(SURN) + str(eid % 7)
            base = {1: 4.5, 2: 4.8, 3: 5.5, 4: 6.0}[pos]
            star = random.random() < 0.12
            price = int((base + random.random() * (2.5 if not star else 6.0)) * 10)
            mins = random.choice([0, 120, 300, 450, 540, 630, 630, 630]) if random.random() < 0.8 else 630
            pts = int(mins / 90 * random.uniform(2.5, 8.0)) if mins else 0
            ppg = round(pts / max(mins / 90, 1), 1) if mins else 0.0
            elements.append({
                "id": eid, "web_name": name, "first_name": "F", "second_name": name, "team": ti, "element_type": pos,
                "now_cost": price, "cost_change_start": random.choice([-1, 0, 0, 0, 1, 2]),
                "selected_by_percent": str(round(random.random() ** 2 * 40, 1)),
                "form": str(round(random.uniform(0, 9), 1)), "points_per_game": str(ppg), "total_points": pts,
                "minutes": mins, "status": random.choice(["a"] * 17 + ["d", "i"]),
                "news": "", "chance_of_playing_next_round": None,
                "ep_next": str(round(random.uniform(1, 7), 1)),
                "transfers_in_event": random.randint(0, 60000), "transfers_out_event": random.randint(0, 60000),
                "expected_goal_involvements_per_90": str(round(random.uniform(0.05, 0.9) * (0.3 if pos <= 2 else 1), 2)),
                "expected_goals_conceded_per_90": str(round(random.uniform(0.6, 2.0), 2)),
                "defensive_contribution_per_90": str(round(random.uniform(1, 11), 1)),
                "clean_sheets": random.randint(0, 5), "goals_scored": random.randint(0, 5),
                "assists": random.randint(0, 4), "bonus": random.randint(0, 6),
            })
            by_team_pos.setdefault(pos, []).append(eid)
            eid += 1
for e in elements:
    if e["status"] == "i":
        e["news"] = "Hamstring injury - Expected back soon"
        e["chance_of_playing_next_round"] = 0
    if e["status"] == "d":
        e["news"] = "Knock - 75% chance of playing"
        e["chance_of_playing_next_round"] = 75

now = dt.datetime.utcnow()
events = []
for g in range(1, 39):
    events.append({"id": g, "finished": g <= 7, "is_current": g == 7, "is_next": g == 8,
                   "deadline_time": (now + dt.timedelta(days=(g - 8) * 7 + 3)).strftime("%Y-%m-%dT%H:%M:%SZ")})
teams = [{"id": i, "short_name": t, "name": t, "strength": 3} for i, t in enumerate(TEAMS, start=1)]
put("bootstrap-static/", {"events": events, "teams": teams, "elements": elements})

fx = []
for g in range(1, 39):
    ts = list(range(1, 21))
    random.shuffle(ts)
    for i in range(0, 20, 2):
        fx.append({"id": len(fx) + 1, "event": g, "team_h": ts[i], "team_a": ts[i + 1],
                   "team_h_difficulty": random.choice([2, 3, 3, 4, 5]), "team_a_difficulty": random.choice([2, 3, 3, 4, 5])})
put("fixtures/", fx)


def squad(excl):
    res = []
    for pos, n in ((1, 2), (2, 5), (3, 5), (4, 3)):
        pool = [i for i in by_team_pos[pos] if i not in excl and elements[i - 1]["minutes"] > 300]
        res += random.sample(pool, n)
    return res


def picks_for(ids, cap=None):
    order = list(ids)
    pk = []
    for i, el in enumerate(order, start=1):
        pk.append({"element": el, "position": i, "multiplier": 1, "is_captain": i == (cap or 14), "is_vice_captain": i == 13})
    return pk


used = set()
mgr = {}
for key, eid_ in (("me", 1000001), ("roma", 1000002), ("stas", 1000003)):
    ids = squad(used)
    used.update(ids)
    mgr[key] = (eid_, ids)

for key, (eid_, ids) in mgr.items():
    put("entry/%d/" % eid_, {"id": eid_, "name": "Team " + key, "player_first_name": key.title(), "player_last_name": "X",
                             "summary_overall_points": random.randint(380, 440), "summary_overall_rank": random.randint(10000, 5000000)})
    cur = []
    for g in range(1, 8):
        cur.append({"event": g, "points": random.randint(40, 95), "points_on_bench": random.randint(0, 12),
                    "event_transfers": random.choice([0, 1, 1, 2]), "event_transfers_cost": random.choice([0, 0, 0, 4]),
                    "overall_rank": random.randint(100000, 5000000), "bank": 3, "value": 1000})
    put("entry/%d/history/" % eid_, {"current": cur, "chips": [{"name": "3xc", "event": 7}] if key == "me" else []})
    trs = [{"element_in": ids[3], "element_in_cost": elements[ids[3] - 1]["now_cost"] - 2, "element_out": ids[0], "element_out_cost": 45,
            "entry": eid_, "event": 6, "time": "2026-10-10T06:56:47Z"}]
    if key == "me":
        trs.append({"element_in": ids[5], "element_in_cost": elements[ids[5] - 1]["now_cost"], "element_out": ids[6], "element_out_cost": 50,
                    "entry": eid_, "event": 8, "time": "2026-10-19T18:00:00Z"})
    put("entry/%d/transfers/" % eid_, trs)
    put("entry/%d/event/7/picks/" % eid_, {"active_chip": None, "picks": picks_for(ids),
                                           "entry_history": {"event": 7, "bank": 3, "value": 1000, "points": 60}})

top_entries = []
for i in range(50):
    ids = squad(set())
    top_entries.append(100000 + i)
    put("entry/%d/event/7/picks/" % (100000 + i), {"active_chip": "bboost" if i % 17 == 0 else None, "picks": picks_for(ids),
                                                   "entry_history": {"event": 7, "bank": 5, "value": 1010, "points": 90}})
    put("entry/%d/transfers/" % (100000 + i), [{"element_in": random.choice(ids), "element_in_cost": 60, "element_out": random.randint(1, 500),
                                                 "element_out_cost": 60, "entry": 100000 + i, "event": 7, "time": "2026-10-14T12:00:00Z"}])
put("leagues-classic/314/standings/?page_standings=1", {"standings": {"results": [
    {"entry": 100000 + i, "entry_name": "Top %d" % (i + 1), "player_name": "M %d" % i, "rank": i + 1, "total": 600 - i} for i in range(50)]}})
put("leagues-classic/1234567/standings/", {"standings": {"results": [
    {"entry": mgr[k][0], "entry_name": "Team " + k, "player_name": k.title(), "rank": i + 1, "total": 412 - i * 5, "event_total": 60}
    for i, k in enumerate(("me", "roma", "stas"))]}})

for e in elements:
    if e["minutes"] > 0:
        h = []
        for g in range(1, 8):
            h.append({"round": g, "total_points": random.randint(0, 12), "minutes": random.choice([0, 60, 90, 90]),
                      "expected_goal_involvements": "0.4", "opponent_team": random.randint(1, 20), "was_home": random.random() < 0.5})
        put("element-summary/%d/" % e["id"], {"history": h})
print("mock готов:", OUT)
