"""
Вероятности по данным API FPL (v1.19): сила команд, шанс «сухого» матча (CS %), бонус за защитные действия (DC %),
гол / 2+ гола / ассист / гол или ассист, исполнители стандартов, изменение владения за 1/3/7 дней,
мини-лига вживую. Всё считается из того, что отдаёт FPL (история матчей игроков, календарь, составы) —
никаких сторонних сайтов.

Модель (простая и прозрачная):
  * xGA команды в сыгранном матче = наибольший expected_goals_conceded среди её игроков, отыгравших 80+ минут
    (это вратарь/центральные защитники — они на поле весь матч); xG команды = xGA соперника в том же матче.
  * Атака/оборона команды = среднее xG/xGA за матч, сжатое к среднему по лиге (как будто ещё SHRINK матчей «средних»).
    Нет истории (запуск с --no-history) — берём силу команд из FPL (strength_attack/defence).
  * Ожидаемые голы команды T против O: λ = атака(T) × оборона(O) / среднее × (HOME дома, 1/HOME в гостях).
  * CS % = e^(−λ соперника) × шанс игрока отыграть 60+ минут (очки за «сухой» дают только с 60 минут).
  * Гол: λг = xG/90 игрока × ожидаемые минуты/90 × оборона(O)/среднее × дом/выезд; P(гол)=1−e^(−λг), P(2+)=1−e^(−λ)(1+λ);
    ассист так же из xA/90; «гол или ассист» = 1−e^(−(λг+λа)).
  * DC %: число защитных действий за матч ~ отрицательное биномиальное со средним (темп за 90) × (атака соперника/среднее)^0.5,
    порог 10 у защитников и 12 у полузащитников/нападающих (вратарям DC не дают); × шанс отыграть 60+.
  * Двойной тур: P(хотя бы раз) = 1 − Π(1 − p).
Это ориентир, а не приговор — как и xP.
"""
import datetime as dt
import math

SHRINK = 3.0       # «виртуальных» средних матчей в сглаживании силы команд
HOME = 1.12        # преимущество своего поля по xG
NB_R = 6.0         # дисперсия для защитных действий (больше — ближе к Пуассону)
DC_THR = {"DEF": 10, "MID": 12, "FWD": 12}
TEAM_GWS = 10      # горизонт таблиц команд
PLAYER_GWS = 5     # горизонт вероятностей игроков

MATCH_SCHEMA = """
CREATE TABLE IF NOT EXISTS player_match(element INTEGER, fixture INTEGER, gw INTEGER, team INTEGER, opp INTEGER,
  home INTEGER, minutes INTEGER, starts INTEGER, xg REAL, xa REAL, xgc REAL, dc INTEGER, pts INTEGER,
  PRIMARY KEY(element, fixture));
CREATE TABLE IF NOT EXISTS team_snap(snap_id INTEGER, team INTEGER, gw INTEGER, cs REAL, xg REAL, xga REAL,
  PRIMARY KEY(snap_id, team, gw));
"""


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def ensure_schema(con):
    con.executescript(MATCH_SCHEMA)


def store_matches(con, results, fixtures):
    """results: [(element, element-summary json)] -> player_match (по матчу: минуты, старт, xG, xA, xGC, DC)."""
    fx = {f["id"]: f for f in fixtures}
    cur = con.cursor()
    n = 0
    for el, js in results:
        if not js:
            continue
        for h in js.get("history", []):
            f = fx.get(h.get("fixture"))
            home = bool(h.get("was_home"))
            team = (f["team_h"] if home else f["team_a"]) if f else None
            cur.execute("INSERT OR REPLACE INTO player_match VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (el, h.get("fixture"), h.get("round"), team, h.get("opponent_team"), 1 if home else 0,
                         h.get("minutes", 0), h.get("starts", 0), _f(h.get("expected_goals")), _f(h.get("expected_assists")),
                         _f(h.get("expected_goals_conceded")), h.get("defensive_contribution") or 0, h.get("total_points", 0)))
            n += 1
    con.commit()
    return n


def nb_tail(mu, k, r=NB_R):
    """P(X >= k) для отрицательного биномиального со средним mu."""
    if mu <= 0:
        return 0.0
    p = r / (r + mu)
    pmf = p ** r
    s = pmf
    for x in range(1, k):
        pmf *= (x + r - 1) / x * (1 - p)
        s += pmf
    return min(1.0, max(0.0, 1.0 - s))


def team_strength(con, teams, fixtures):
    """{team: {'att': xG за матч, 'def': xGA за матч, 'n': матчей}}, среднее по лиге."""
    rows = con.execute("SELECT fixture, team, MAX(xgc) FROM player_match WHERE minutes>=80 AND team IS NOT NULL "
                       "GROUP BY fixture, team").fetchall()
    xga = {(fid, t): v for fid, t, v in rows}
    fx = {f["id"]: f for f in fixtures if f.get("finished")}
    att = {t: [] for t in teams}
    dfn = {t: [] for t in teams}
    for fid, f in fx.items():
        h, a = f["team_h"], f["team_a"]
        if (fid, h) in xga and (fid, a) in xga:
            dfn[h].append(xga[(fid, h)])
            dfn[a].append(xga[(fid, a)])
            att[h].append(xga[(fid, a)])
            att[a].append(xga[(fid, h)])
    allv = [v for t in teams for v in att[t]]
    if len(allv) >= 20:
        avg = sum(allv) / len(allv)
        out = {t: {"att": (sum(att[t]) + SHRINK * avg) / (len(att[t]) + SHRINK),
                   "def": (sum(dfn[t]) + SHRINK * avg) / (len(dfn[t]) + SHRINK), "n": len(att[t])} for t in teams}
        return out, avg, "xg"
    # запасной вариант: сила команд из FPL
    avg = 1.35
    sa = {t: (teams[t].get("strength_attack_home", 1100) + teams[t].get("strength_attack_away", 1100)) / 2 for t in teams}
    sd = {t: (teams[t].get("strength_defence_home", 1100) + teams[t].get("strength_defence_away", 1100)) / 2 for t in teams}
    ma, md = sum(sa.values()) / len(sa), sum(sd.values()) / len(sd)
    out = {t: {"att": avg * (sa[t] / ma) ** 2, "def": avg * (md / sd[t]) ** 2, "n": 0} for t in teams}
    return out, avg, "fpl"


def lam(st, avg, t, o, home):
    return st[t]["att"] * st[o]["def"] / avg * (HOME if home else 1 / HOME)


def team_fixtures(st, avg, fixtures, teams, gw_next):
    """{team: [{gw, opp, h, xg, xga, cs}]} на TEAM_GWS туров."""
    out = {t: [] for t in teams}
    for f in fixtures:
        ev = f.get("event")
        if ev is None or ev < gw_next or ev >= gw_next + TEAM_GWS or f.get("finished"):
            continue
        h, a = f["team_h"], f["team_a"]
        lh, la = lam(st, avg, h, a, True), lam(st, avg, a, h, False)
        out[h].append({"gw": ev, "opp": a, "h": True, "xg": round(lh, 2), "xga": round(la, 2), "cs": round(math.exp(-la), 3)})
        out[a].append({"gw": ev, "opp": h, "h": False, "xg": round(la, 2), "xga": round(lh, 2), "cs": round(math.exp(-lh), 3)})
    for t in out:
        out[t].sort(key=lambda x: x["gw"])
    return out


def player_usage(con, fixtures, gw_cur):
    """{element: {'min': ожидаемые минуты, 'p60': шанс 60+, 'dc90': темп DC за 90}} по последним 5 матчам команды."""
    team_fix = {}
    for f in fixtures:
        if f.get("finished") and f.get("event"):
            for t in (f["team_h"], f["team_a"]):
                team_fix.setdefault(t, []).append((f["event"], f["id"]))
    for t in team_fix:
        team_fix[t].sort()
    by_el = {}
    for el, fid, team, mins, dc in con.execute("SELECT element, fixture, team, minutes, dc FROM player_match"):
        d = by_el.setdefault(el, {"m": {}, "team": team, "dcs": 0, "dcm": 0})
        d["m"][fid] = mins or 0
        if mins and mins >= 45:
            d["dcs"] += dc or 0
            d["dcm"] += mins
        if team:
            d["team"] = team
    out = {}
    for el, d in by_el.items():
        last = [fid for _, fid in team_fix.get(d["team"], [])][-5:]
        if not last:
            continue
        mins = [d["m"].get(fid, 0) for fid in last]
        out[el] = {"min": sum(mins) / len(mins), "p60": sum(1 for m in mins if m >= 60) / len(mins),
                   "dc90": (d["dcs"] / d["dcm"] * 90) if d["dcm"] >= 180 else None}
    return out


def fpl_ratios(bst):
    """Во сколько раз FPL засчитывает больше голов/ассистов, чем xG/xA (ассисты в FPL щедрее Opta). Калибровка по всей лиге сезона."""
    els = bst["elements"]
    g, xg = sum(e.get("goals_scored", 0) for e in els), sum(_f(e.get("expected_goals")) for e in els)
    a, xa = sum(e.get("assists", 0) for e in els), sum(_f(e.get("expected_assists")) for e in els)
    cl = lambda v: min(1.6, max(0.8, v))
    return {"g": cl(g / xg) if xg > 20 else 1.0, "a": cl(a / xa) if xa > 20 else 1.25}


def player_probs(row, el_raw, usage, st, avg, tfix, gw_next, ratios=None):
    """[{gw, cs, dc, g, g2, a, ga}] на PLAYER_GWS туров (проценты 0–100, None — не применимо)."""
    u = usage.get(row["id"])
    if not u:
        return None
    avail = row.get("avail", 1.0)
    m = u["min"] * avail
    p60 = u["p60"] * avail
    ratios = ratios or {"g": 1.0, "a": 1.0}
    xg90, xa90 = _f(el_raw.get("expected_goals_per_90")) * ratios["g"], _f(el_raw.get("expected_assists_per_90")) * ratios["a"]
    thr = DC_THR.get(row["pos"])
    out = []
    for ev in range(gw_next, gw_next + PLAYER_GWS):
        fs = [f for f in tfix.get(row["team"], []) if f["gw"] == ev]
        if not fs:
            out.append({"gw": ev, "blank": True})
            continue
        q = {"cs": 1.0, "dc": 1.0, "g": 1.0, "g2": 1.0, "a": 1.0, "ga": 1.0}
        for f in fs:
            o, home = f["opp"], f["h"]
            mult = st[o]["def"] / avg * (HOME if home else 1 / HOME)
            lg, la = xg90 * m / 90 * mult, xa90 * m / 90 * mult
            q["cs"] *= 1 - f["cs"] * p60
            q["g"] *= math.exp(-lg)
            q["g2"] *= math.exp(-lg) * (1 + lg)
            q["a"] *= math.exp(-la)
            q["ga"] *= math.exp(-(lg + la))
            if thr and u["dc90"] is not None:
                mu = u["dc90"] * (st[o]["att"] / avg) ** 0.5
                q["dc"] *= 1 - nb_tail(mu, thr) * p60
        pct = lambda v: int(round(100 * (1 - v)))
        out.append({"gw": ev, "cs": pct(q["cs"]) if row["pos"] in ("GK", "DEF", "MID") else None,
                    "dc": pct(q["dc"]) if thr and u["dc90"] is not None else None,
                    "g": pct(q["g"]), "g2": pct(q["g2"]), "a": pct(q["a"]), "ga": pct(q["ga"])})
    return out


def set_pieces(el_raw):
    """Порядок исполнителей: пенальти / штрафные / угловые (1 — первый номер). Пусто — не бьёт."""
    sp = {}
    for k, f in (("pen", "penalties_order"), ("fk", "direct_freekicks_order"), ("cor", "corners_and_indirect_freekicks_order")):
        v = el_raw.get(f)
        if v:
            sp[k] = v
    return sp


def team_set_pieces(bst):
    """Стандарты по клубам по ВСЕМ игрокам FPL: {team: {'pen': [[№, id, имя, код фото]], 'fk': [...], 'cor': [...]}}."""
    out = {}
    for e in bst["elements"]:
        for k, v in set_pieces(e).items():
            out.setdefault(e["team"], {"pen": [], "fk": [], "cor": []})[k].append([v, e["id"], e["web_name"], e.get("code")])
    for t in out:
        for k in out[t]:
            out[t][k].sort()
    return out


def save_team_snap(con, sid, tfix):
    con.execute("DELETE FROM team_snap WHERE snap_id=?", (sid,))
    for t, lst in tfix.items():
        seen = {}
        for f in lst:  # двойной тур: храним сумму xG и «хотя бы один сухой»
            s = seen.setdefault(f["gw"], [0.0, 0.0, 1.0])
            s[0] += f["xg"]; s[1] += f["xga"]; s[2] *= 1 - f["cs"]
        for gw, (xg, xga, ncs) in seen.items():
            con.execute("INSERT OR REPLACE INTO team_snap VALUES(?,?,?,?,?,?)", (sid, t, gw, round(1 - ncs, 3), xg, xga))
    con.commit()


def team_changes(con, sid):
    """Изменение CS %/xG команды на тур с прошлого снимка: {team: {gw: {'cs': d, 'xg': d}}}."""
    prev = con.execute("SELECT DISTINCT snap_id FROM team_snap WHERE snap_id<? ORDER BY snap_id DESC LIMIT 1", (sid,)).fetchone()
    if not prev:
        return {}, None
    pts = con.execute("SELECT ts FROM snapshots WHERE id=?", (prev[0],)).fetchone()
    old = {(t, gw): (cs, xg) for t, gw, cs, xg in con.execute("SELECT team, gw, cs, xg FROM team_snap WHERE snap_id=?", (prev[0],))}
    out = {}
    for t, gw, cs, xg in con.execute("SELECT team, gw, cs, xg FROM team_snap WHERE snap_id=?", (sid,)):
        if (t, gw) in old:
            o = old[(t, gw)]
            out.setdefault(t, {})[gw] = {"cs": round((cs - o[0]) * 100, 1), "xg": round(xg - o[1], 2)}
    return out, pts[0] if pts else None


def own_deltas(con, sid, ts):
    """Изменение владения (п.п.) за ~1, 3 и 7 дней по снимкам: {element: {'1': d, '3': d, '7': d}}."""
    now = {el: own for el, own in con.execute("SELECT element, own FROM player_snap WHERE snap_id=?", (sid,))}
    t = dt.datetime.fromisoformat(ts)
    out, used = {}, {}
    for days in (1, 3, 7):
        target = (t - dt.timedelta(days=days, hours=-6)).isoformat()   # допуск 6 часов
        row = con.execute("SELECT id, ts FROM snapshots WHERE id<? AND ts<=? ORDER BY id DESC LIMIT 1", (sid, target)).fetchone()
        if not row:
            continue
        used[str(days)] = row[1]
        for el, own in con.execute("SELECT element, own FROM player_snap WHERE snap_id=?", (row[0],)):
            if el in now:
                out.setdefault(el, {})[str(days)] = round(now[el] - own, 2)
    return out, used


def build_live(get, bst, fixtures, managers, cur_ev):
    """Мини-лига вживую: если текущий тур идёт — очки по ходу, кто ещё сыграет, капитаны; иначе только статус."""
    if not cur_ev:
        return {"state": "none"}
    gw = cur_ev["id"]
    if cur_ev.get("finished") and cur_ev.get("data_checked"):
        return {"state": "between", "gw": gw}
    live = get("event/%d/live/" % gw, optional=True) or {}
    pts = {e["id"]: e.get("stats", {}) for e in live.get("elements", [])}
    els = {e["id"]: e for e in bst["elements"]}
    fx = [f for f in fixtures if f.get("event") == gw]
    team_state = {}
    for f in fx:
        st = "done" if f.get("finished") or f.get("finished_provisional") else ("live" if f.get("started") else "wait")
        for t in (f["team_h"], f["team_a"]):
            team_state.setdefault(t, []).append(st)
    mgr = {}
    for k, m in managers.items():
        p = get("entry/%d/event/%d/picks/" % (m["entry"], gw), optional=True) or {}
        picks = p.get("picks") or []
        total, played, to_play, playing = 0, 0, 0, 0
        rows = []
        for pk in picks:
            el = pk["element"]
            s = pts.get(el, {})
            mult = pk.get("multiplier", 1)
            sts = team_state.get((els.get(el) or {}).get("team"), [])
            state = "wait" if "wait" in sts else ("live" if "live" in sts else ("done" if sts else "blank"))
            if mult > 0:
                total += s.get("total_points", 0) * mult
                if state == "wait":
                    to_play += 1
                elif state == "live":
                    playing += 1
                else:
                    played += 1
            rows.append({"id": el, "mult": mult, "pts": s.get("total_points", 0), "min": s.get("minutes", 0), "state": state,
                         "cap": pk.get("is_captain", False)})
        eh = p.get("entry_history") or {}
        mgr[k] = {"pts": total - (eh.get("event_transfers_cost") or 0), "hit": eh.get("event_transfers_cost") or 0,
                  "chip": p.get("active_chip"), "played": played, "playing": playing, "to_play": to_play, "picks": rows}
    return {"state": "live" if not cur_ev.get("finished") else "provisional", "gw": gw, "managers": mgr,
            "fixtures": [{"h": f["team_h"], "a": f["team_a"], "hs": f.get("team_h_score"), "as": f.get("team_a_score"),
                          "started": f.get("started"), "finished": f.get("finished") or f.get("finished_provisional"),
                          "min": f.get("minutes", 0), "kick": f.get("kickoff_time")} for f in fx]}
