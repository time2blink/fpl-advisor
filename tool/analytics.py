# -*- coding: utf-8 -*-
"""
Аналитика поверх данных FPL (без внешних библиотек):
  1. threats  — прогноз ходов друзей и угроза перехвата твоих целей
  2. market   — давление на цену (рост/падение), калибровка по истории снимков
  3. plan     — план трансферов на несколько туров с учётом FT, банка и хитов + оценка чипов
  4. luck     — недоудачливые и перегретые игроки (очки vs xGI / xGC)
  5. race     — положение в лиге, шанс выиграть, влияние риска
  6. warnings — проверка формата API
  7. exports  — CSV для Excel
"""
import csv
import itertools
import math
import os
import random
import statistics

FORMS = [(d, m, f) for d in range(3, 6) for m in range(2, 6) for f in range(1, 4) if d + m + f == 10]
CHIPS = ["wildcard", "freehit", "bboost", "3xc"]
CHIP_RU = {"wildcard": "Wildcard", "freehit": "Free Hit", "bboost": "Bench Boost", "3xc": "Triple Captain"}


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def club_ok(team_ids, cap=3):
    cnt = {}
    for t in team_ids:
        cnt[t] = cnt.get(t, 0) + 1
        if cnt[t] > cap:
            return False
    return True


# ============================================================================ проверка формата API
def check_schema(bst, fixtures):
    w = []
    need_el = ["id", "web_name", "team", "element_type", "now_cost", "form", "points_per_game", "minutes", "status",
               "selected_by_percent", "transfers_in_event", "transfers_out_event", "expected_goal_involvements_per_90",
               "expected_goals_conceded_per_90", "defensive_contribution_per_90", "cost_change_start", "ep_next"]
    if not bst.get("elements"):
        w.append("В bootstrap-static нет списка игроков — формат API изменился.")
    else:
        miss = [k for k in need_el if k not in bst["elements"][0]]
        if miss:
            w.append("У игроков API пропали поля: %s. Часть расчётов будет неточной." % ", ".join(miss))
    for k in ("events", "teams"):
        if not bst.get(k):
            w.append("В bootstrap-static нет '%s'." % k)
    if "total_players" not in bst:
        w.append("В bootstrap-static нет total_players: прогноз цен использует приближение.")
    if fixtures:
        miss = [k for k in ("event", "team_h", "team_a", "team_h_difficulty", "team_a_difficulty") if k not in fixtures[0]]
        if miss:
            w.append("В fixtures пропали поля: %s." % ", ".join(miss))
    else:
        w.append("Календарь матчей пуст — xP и рекомендации недостоверны.")
    return w


# ============================================================================ XI и оценка состава
def xi_value(ids, gwi, R, detail=False):
    """Лучшая расстановка на тур gwi по xP + бонус капитана. detail=True -> (value, bench_sum, cap_xp)."""
    by = {"GK": [], "DEF": [], "MID": [], "FWD": []}
    for i in ids:
        by[R[i]["pos"]].append(R[i]["xpg"][gwi])
    for k in by:
        by[k].sort(reverse=True)
    if not by["GK"]:
        return (0.0, 0.0, 0.0) if detail else 0.0
    best, best_xi = -1.0, None
    for d, m, f in FORMS:
        if len(by["DEF"]) < d or len(by["MID"]) < m or len(by["FWD"]) < f:
            continue
        v = by["GK"][0] + sum(by["DEF"][:d]) + sum(by["MID"][:m]) + sum(by["FWD"][:f])
        if v > best:
            best, best_xi = v, (d, m, f)
    if best_xi is None:
        return (0.0, 0.0, 0.0) if detail else 0.0
    cap = max(by["GK"][0], by["DEF"][0], by["MID"][0], by["FWD"][0])
    if not detail:
        return best + cap
    total = sum(sum(v) for v in by.values())
    return best + cap, total - best, cap


def captain_of(ids, gwi, R):
    best = None
    for i in ids:
        if best is None or R[i]["xpg"][gwi] > R[best]["xpg"][gwi]:
            best = i
    return best


# ============================================================================ 1. угрозы от друзей
def build_threats(ctx):
    M, R, rows, cfg = ctx["managers"], ctx["R"], ctx["rows"], ctx["cfg"]
    names = cfg["names"]
    owned = set()
    for m in M.values():
        owned.update(s["id"] for s in m["squad"])
    free_pool = [r for r in rows if r["id"] not in owned and r["avail"] >= 0.5
                 and (r["mfrac"] >= cfg.get("min_minutes_frac", 0.25) or r["pts"] >= 20)]
    out = {"friends": {}, "intercept": [], "releases": []}
    pbuy = {}                                           # player_id -> {friend: prob}
    for k, m in M.items():
        if k == "me":
            continue
        sq = [R[s["id"]] for s in m["squad"] if s["id"] in R]
        sell = {s["id"]: s["sell"] for s in m["squad"]}
        ft = m.get("ft_estimate", 1) or 0
        hist = m.get("tr_per_gw") or []
        recent = hist[-4:]
        avg = sum(recent) / len(recent) if recent else 1.0
        exp_moves = clamp(max(avg, 1.0 if ft >= 2 else 0.4), 0.3, ft + 1)
        xps = sorted(r["xp5"] for r in sq)
        w = {}
        for r in sq:
            rank = sum(1 for x in xps if x < r["xp5"]) / max(len(xps) - 1, 1)
            x = 0.04 + 0.85 * (1 - r["avail"]) + 0.25 * (1 - rank)
            if r["form"] < 2 and r["mfrac"] > 0.3:
                x += 0.10
            if r["mfrac"] < 0.25:
                x += 0.15
            if r["news"]:
                x += 0.05
            w[r["id"]] = x
        tot = sum(w.values()) or 1.0
        prob = {i: min(0.95, v * exp_moves / tot) for i, v in w.items()}
        sells = sorted(prob.items(), key=lambda kv: -kv[1])
        bank = m.get("bank") or 0
        buys = {}
        for oid, p in sells[:8]:
            o = R[oid]
            limit = sell.get(oid, o["price"]) + bank
            cands = [c for c in free_pool if c["pos"] == o["pos"] and c["price"] <= limit
                     and club_ok([r["team"] for r in sq if r["id"] != oid] + [c["team"]])]
            cands.sort(key=lambda c: -c["xp5"])
            top = cands[:5]
            if not top:
                continue
            mx = top[0]["xp5"]
            ws = [math.exp((c["xp5"] - mx) / 2.5) for c in top]
            sw = sum(ws)
            for c, wc in zip(top, ws):
                pr = p * wc / sw
                buys[c["id"]] = buys.get(c["id"], 0) + pr
                pbuy.setdefault(c["id"], {})[k] = pbuy.get(c["id"], {}).get(k, 0) + pr
                fg = out.setdefault("_fgain", {})
                fg[c["id"]] = fg.get(c["id"], 0) + pr * max(0.0, c["xp5"] - o["xp5"])
        out["friends"][k] = {
            "name": names.get(k, k), "bank": bank, "ft": ft, "exp_moves": round(exp_moves, 2),
            "verified": bool(ctx.get("verified", {}).get(k)),
            "sells": [{"id": i, "prob": round(p, 3)} for i, p in sells[:6]],
            "buys": [{"id": i, "prob": round(min(p, 0.95), 3)} for i, p in sorted(buys.items(), key=lambda kv: -kv[1])[:8]],
        }
        for i, p in sells:
            if p >= 0.15:
                out["releases"].append({"id": i, "owner": k, "prob": round(p, 3)})
    # мои цели: из одиночных/двойных ходов и плана
    targets = {}
    for mv in ctx["sugg"]["single"][:30]:
        targets[mv["inn"]] = max(targets.get(mv["inn"], 0), mv["gain"])
    for pr in ctx["sugg"]["double"][:15]:
        for part in (pr["a"], pr["b"]):
            targets[part["inn"]] = max(targets.get(part["inn"], 0), part["gain"])
    for i in ctx.get("plan_ins", []):
        targets.setdefault(i, 1.0)
    for i, gain in targets.items():
        per = {k: round(min(v, 0.95), 3) for k, v in pbuy.get(i, {}).items()}
        if not per:
            continue
        risk = 1.0
        for v in per.values():
            risk *= (1 - v)
        risk = 1 - risk
        out["intercept"].append({"id": i, "risk": round(risk, 3), "who": per, "gain": round(gain, 1),
                                 "urgency": round(risk * gain, 2)})
    # эффект блокировки: ожидаемый прирост друзей от покупки игрока (нам он важен, т.к. отнимает его у них)
    out["deny"] = {i: round(v, 2) for i, v in out.pop("_fgain", {}).items()}
    out["intercept"].sort(key=lambda x: -x["urgency"])
    out["intercept"] = out["intercept"][:20]
    out["releases"].sort(key=lambda x: -x["prob"])
    out["releases"] = out["releases"][:12]
    return out


# ============================================================================ 2. цены
def _calibrate(con, default):
    """Порог давления по истории: сравниваем net-трансферы вчера с изменением цены сегодня."""
    if con is None:
        return default, 0
    try:
        snaps = con.execute("SELECT id FROM snapshots ORDER BY id").fetchall()
        riser, n_ev = [], 0
        for (a,), (b,) in zip(snaps[:-1], snaps[1:]):
            prev = {r[0]: r for r in con.execute("SELECT element, price, tin, tout FROM player_snap WHERE snap_id=?", (a,))}
            cur = {r[0]: r for r in con.execute("SELECT element, price FROM player_snap WHERE snap_id=?", (b,))}
            for el, p in prev.items():
                c = cur.get(el)
                if c and c[1] > p[1]:
                    riser.append(p[2] - p[3])
                    n_ev += 1
        riser = [x for x in riser if x > 0]
        if len(riser) >= 5:
            riser.sort()
            return riser[len(riser) // 4], n_ev
    except Exception:
        pass
    return default, 0


def build_market(ctx):
    bst, rows, R, con, mine = ctx["bst"], ctx["rows"], ctx["R"], ctx.get("con"), ctx["mine_ids"]
    total = float(bst.get("total_players") or 11000000)
    thr_pct_default = 0.45                              # % менеджеров, чистый приток за тур (ориентир по умолчанию)
    thr_abs, n_ev = _calibrate(con, thr_pct_default / 100 * total)
    for r in rows:
        r["net"] = r["tin"] - r["tout"]
        r["press"] = round(r["net"] / total * 100, 3)    # % всех менеджеров
        ratio = r["net"] / thr_abs if thr_abs else 0
        if ratio >= 1.5:
            r["ptrend"] = "up2"
        elif ratio >= 1.0:
            r["ptrend"] = "up"
        elif ratio >= 0.6:
            r["ptrend"] = "up?"
        elif ratio <= -1.5:
            r["ptrend"] = "dn2"
        elif ratio <= -1.0:
            r["ptrend"] = "dn"
        elif ratio <= -0.6:
            r["ptrend"] = "dn?"
        else:
            r["ptrend"] = ""
    up = sorted([r for r in rows if r["net"] > 0], key=lambda r: -r["net"])[:15]
    dn = sorted([r for r in rows if r["net"] < 0], key=lambda r: r["net"])[:15]
    f = lambda r: {"id": r["id"], "net": r["net"], "press": r["press"], "tier": r["ptrend"], "price": r["price"],
                   "own": r["own"]}
    targets = set()
    for mv in ctx["sugg"]["single"][:15]:
        targets.add(mv["inn"])
    return {
        "thr": int(thr_abs), "calib_events": n_ev,
        "rising": [f(r) for r in up], "falling": [f(r) for r in dn],
        "my_risk": [f(R[i]) for i in mine if i in R and R[i]["ptrend"] in ("dn", "dn2", "dn?")],
        "my_gain": [f(R[i]) for i in mine if i in R and R[i]["ptrend"] in ("up", "up2", "up?")],
        "targets_up": [f(R[i]) for i in targets if i in R and R[i]["ptrend"] in ("up", "up2", "up?")],
    }


# ============================================================================ 3. план на несколько туров
def _gen_singles(st, g, R, pool_pos, H, limit=10):
    res = []
    ids = st["ids"]
    idset = set(ids)
    for o in ids:
        ro = R[o]
        so = sum(ro["xpg"][g:])
        for c in pool_pos[ro["pos"]]:
            if c in idset:
                continue
            rc = R[c]
            gain = sum(rc["xpg"][g:]) - so
            if gain <= 0.5:
                continue
            delta = rc["price"] - st["sell"][o]
            if delta > st["bank"]:
                continue
            teams = [R[i]["team"] for i in ids if i != o] + [rc["team"]]
            if not club_ok(teams):
                continue
            res.append((gain, o, c, delta))
    res.sort(reverse=True)
    return res[:limit]


def run_plan(squad, bank, ft, R, blocked, cfg, gw_next):
    H = min(len(next(iter(R.values()))["xpg"]), max(1, cfg.get("planner_horizon", 8)))
    cap_ft = cfg.get("max_free_transfers", 5)
    hit = cfg.get("hit_cost", 4)
    max_hits = cfg.get("max_hits_per_gw", 1)
    deny = cfg.get("_deny") or {}
    dw = cfg.get("deny_weight", 0.3)
    ids0 = tuple(sorted(s["id"] for s in squad))
    sells0 = {s["id"]: s["sell"] for s in squad}
    mine = set(ids0)
    base_pool = [r for r in R.values() if r["id"] not in blocked and r["id"] not in mine and r["avail"] >= 0.5
                 and (r["mfrac"] >= cfg.get("min_minutes_frac", 0.25) or r["pts"] >= 20)]

    def fut(g0, ids):
        return sum(xi_value(ids, j, R) for j in range(g0, H))

    states = [{"ids": ids0, "sell": sells0, "bank": bank, "ft": ft, "total": 0.0, "moves": [], "score": 0.0}]
    for g in range(H):
        pool_pos = {}
        for pos in ("GK", "DEF", "MID", "FWD"):
            cs = [r for r in base_pool if r["pos"] == pos]
            cs.sort(key=lambda r: -sum(r["xpg"][g:]))
            pool_pos[pos] = [r["id"] for r in cs[:14]]
        nxt = {}
        for st in states:
            options = [([], 0)]
            singles = _gen_singles(st, g, R, pool_pos, H)
            options += [([(o, c, d)], 1) for (_, o, c, d) in singles]
            for (g1, o1, c1, d1), (g2, o2, c2, d2) in itertools.combinations(singles[:8], 2):
                if o1 == o2 or c1 == c2:
                    continue
                if d1 + d2 > st["bank"]:
                    continue
                teams = [R[i]["team"] for i in st["ids"] if i not in (o1, o2)] + [R[c1]["team"], R[c2]["team"]]
                if not club_ok(teams):
                    continue
                options.append(([(o1, c1, d1), (o2, c2, d2)], 2))
            for mv, n in options:
                if n - min(n, st["ft"]) > max_hits:
                    continue                      # лимит платных трансферов за тур
                ids = set(st["ids"])
                sell = dict(st["sell"])
                bank_new = st["bank"]
                for (o, c, d) in mv:
                    ids.discard(o)
                    ids.add(c)
                    sell.pop(o, None)
                    sell[c] = R[c]["price"]
                    bank_new -= d
                free_used = min(n, st["ft"])
                hits = (n - free_used) * hit
                ft_after = st["ft"] - free_used
                ft_next = min(cap_ft, ft_after + 1)
                ids_t = tuple(sorted(ids))
                val = xi_value(ids_t, g, R)
                bonus = 0.0
                if dw and deny:
                    for (o, c, d) in mv:
                        bonus += dw * deny.get(c, 0.0) * (0.65 ** g)   # чем раньше покупаем, тем вероятнее, что опередим друга
                total = st["total"] + val - hits + bonus
                key = (ids_t, ft_next)
                if key in nxt and nxt[key]["total"] >= total:
                    continue
                nxt[key] = {"ids": ids_t, "sell": sell, "bank": bank_new, "ft": ft_next, "total": total,
                            "moves": st["moves"] + [{"gw": gw_next + g, "moves": [(o, c) for (o, c, d) in mv],
                                                     "hit": hits, "ft_before": st["ft"], "value": round(val, 1),
                                                     "captain": captain_of(ids_t, g, R)}]}
        cand = list(nxt.values())
        for s_ in cand:
            s_["score"] = s_["total"] + fut(g + 1, s_["ids"])
        cand.sort(key=lambda s_: -s_["score"])
        states = cand[:35]
    states.sort(key=lambda s_: -s_["total"])
    # базовая линия: без трансферов
    base_total = sum(xi_value(ids0, j, R) for j in range(H))
    return states, base_total, ids0


def _greedy(ids, sell, bank, R, blocked, g_from, g_to, max_swaps=15, gw_only=None):
    """Жадные улучшения (для оценки WC/FH): максимум суммы xP на отрезке туров."""
    ids = set(ids)
    sell = dict(sell)
    pool = [r for r in R.values() if r["id"] not in blocked and r["avail"] >= 0.5 and r["mfrac"] >= 0.25]
    rng = range(g_from, g_to)
    score = lambda r: sum(r["xpg"][j] for j in rng)
    for _ in range(max_swaps):
        best = None
        for o in list(ids):
            for r in pool:
                if r["id"] in ids or r["pos"] != R[o]["pos"]:
                    continue
                gain = score(r) - score(R[o])
                if gain <= 0.3 or (best and gain <= best[0]):
                    continue
                delta = r["price"] - sell.get(o, R[o]["price"])
                if delta > bank:
                    continue
                teams = [R[i]["team"] for i in ids if i != o] + [r["team"]]
                if not club_ok(teams):
                    continue
                best = (gain, o, r["id"], delta)
        if not best:
            break
        _, o, c, d = best
        ids.discard(o)
        ids.add(c)
        sell.pop(o, None)
        sell[c] = R[c]["price"]
        bank -= d
    return tuple(sorted(ids))


def chips_available(chips_used, gw_next, cfg):
    reset = cfg.get("chip_reset_gw", 20)
    halves = cfg.get("chip_halves", True)
    used = set()
    for c in chips_used or []:
        ev = c.get("event", 0)
        if halves and ((gw_next < reset) != (ev < reset)):
            continue
        used.add(c["name"])
    return [c for c in CHIPS if c not in used]


def build_plan(ctx):
    cfg, R, me, sugg, gw_next = ctx["cfg"], ctx["R"], ctx["managers"]["me"], ctx["sugg"], ctx["gw_next"]
    squad = [{"id": s["id"], "sell": s["sell"]} for s in me["squad"] if s["id"] in R]
    if len(squad) < 15:
        return {"error": "Состав меньше 15 игроков — план не построен."}, {}
    comp = {}
    for s_ in squad:
        comp[R[s_["id"]]["pos"]] = comp.get(R[s_["id"]]["pos"], 0) + 1
    if comp != {"GK": 2, "DEF": 5, "MID": 5, "FWD": 3}:
        return {"error": "Состав не 2-5-5-3 (%s) — проверь pending в config.json." % comp}, {}
    blocked = set(ctx["taken"].keys())
    states, base_total, ids0 = run_plan(squad, sugg["bank"], sugg["ft"], R, blocked, cfg, gw_next)
    best = states[0]
    H = min(len(R[ids0[0]]["xpg"]), max(1, cfg.get("planner_horizon", 8)))
    # альтернативы с разным первым действием
    alts, seen = [], set()
    for st in states:
        first = tuple(sorted(st["moves"][0]["moves"]))
        # «первое действие» — первое непустое
        act = next((tuple(sorted(m["moves"])) for m in st["moves"] if m["moves"]), ())
        if act in seen:
            continue
        seen.add(act)
        alts.append({"total": round(st["total"], 1), "gain": round(st["total"] - base_total, 1),
                     "first": [{"gw": m["gw"], "out": o, "in": c} for m in st["moves"] if m["moves"] for (o, c) in m["moves"]][:4]})
        if len(alts) >= 4:
            break
    plan = {
        "horizon": H, "gw_from": gw_next, "baseline": round(base_total, 1), "best_total": round(best["total"], 1),
        "gain": round(best["total"] - base_total, 1), "steps": best["moves"], "alts": alts,
        "bank_end": best["bank"],
    }
    # ---- чипы (горизонт — до сгорания первого набора: дедлайн GW19)
    sells = {s["id"]: s["sell"] for s in squad}
    avail = chips_available(me.get("chips", []), gw_next, cfg)
    Hc = len(R[ids0[0]]["xpg"])
    expiry_gw = cfg.get("chip_expiry_gw", 19)
    first_half = gw_next < cfg.get("chip_reset_gw", 20)
    gmax = min(Hc - 1, (expiry_gw - gw_next) if first_half else Hc - 1)
    gmax = max(gmax, 0)
    squads_by_gw = []
    cur = set(ids0)
    for g in range(Hc):
        if g < len(best["moves"]):
            for (o, c) in best["moves"][g]["moves"]:
                cur.discard(o)
                cur.add(c)
        squads_by_gw.append(tuple(sorted(cur)))
    # столкновения «свои против своих» по турам (самоедство при Bench Boost)
    opp = {}
    for fx in ctx.get("fixtures") or []:
        ev = fx.get("event")
        if ev is None or fx.get("team_h") is None:
            continue
        opp.setdefault(ev, {}).setdefault(fx["team_h"], set()).add(fx["team_a"])
        opp.setdefault(ev, {}).setdefault(fx["team_a"], set()).add(fx["team_h"])

    def clashes(sq, g):
        ev = gw_next + g
        teams = [R[i]["team"] for i in sq]
        n = 0
        for i, ti in enumerate(teams):
            for tj in teams[i + 1:]:
                if tj in opp.get(ev, {}).get(ti, ()):
                    n += 1
        return n

    gain = {}
    if "bboost" in avail:
        gain["bboost"] = [xi_value(sq, g, R, True)[1] - 1.5 * clashes(sq, g) for g, sq in enumerate(squads_by_gw[:gmax + 1])]
    if "3xc" in avail:
        gain["3xc"] = [xi_value(sq, g, R, True)[2] for g, sq in enumerate(squads_by_gw[:gmax + 1])]
    if "freehit" in avail:
        arr = []
        for g, sq in enumerate(squads_by_gw[:gmax + 1]):
            ns = _greedy(sq, {i: sells.get(i, R[i]["price"]) for i in sq}, sugg["bank"], R, blocked, g, g + 1, 15)
            arr.append(xi_value(ns, g, R) - xi_value(sq, g, R))
        gain["freehit"] = arr
    if "wildcard" in avail:
        arr = []
        for g, sq in enumerate(squads_by_gw[:gmax + 1]):
            end = min(Hc, g + 6)
            ns = _greedy(sq, {i: sells.get(i, R[i]["price"]) for i in sq}, sugg["bank"], R, blocked, g, end, 15)
            arr.append(sum(xi_value(ns, j, R) - xi_value(sq, j, R) for j in range(g, end)))
        gain["wildcard"] = arr
    NOTE = {
        "bboost": "сумма xP четырёх игроков скамейки; важно, чтобы они реально играли; штраф за матчи «свои против своих»",
        "3xc": "+1 капитанский множитель к лучшему по xP",
        "freehit": "идеальный состав на один тур; лучше всего работает на пустых/двойных турах",
        "wildcard": "прирост xP за 6 туров после розыгрыша сверх обычного плана (без хитов)",
    }
    chips = []
    for ch, arr in gain.items():
        if not arr:
            continue
        v = max(arr)
        g = arr.index(v)
        chips.append({"chip": ch, "gw": gw_next + g, "gain": round(v, 1), "note": NOTE[ch]})
    chips.sort(key=lambda c: -c["gain"])
    # согласованное расписание: один чип на тур, Bench Boost сразу после Wildcard — бонус
    schedule = []
    names = list(gain.keys())
    if names:
        best_s, best_v = None, -1e9
        rng = range(gmax + 1)
        for combo in itertools.product(rng, repeat=len(names)):
            if len(set(combo)) < len(combo):
                continue
            v = sum(gain[n][g] for n, g in zip(names, combo))
            cm = dict(zip(names, combo))
            if "bboost" in cm and "wildcard" in cm and cm["bboost"] == cm["wildcard"] + 1:
                v += 3.0
            if v > best_v:
                best_v, best_s = v, cm
        schedule = sorted([{"chip": n, "gw": gw_next + g, "gain": round(gain[n][g], 1)} for n, g in best_s.items()],
                          key=lambda x: x["gw"])
    expiry = {"gw": expiry_gw, "deadline": cfg.get("chip_expiry_deadline"), "gws_left": max(0, expiry_gw - gw_next + 1),
              "active": bool(first_half and avail)}
    ins = [c for m in best["moves"][:3] for (_, c) in m["moves"]]
    return plan, {"available": avail, "recommend": chips, "schedule": schedule, "expiry": expiry, "plan_ins": ins}


# ============================================================================ 4. удача
def build_luck(ctx):
    rows = ctx["rows"]
    under, over = [], []
    for r in rows:
        games = r["minutes"] / 90.0
        if r["minutes"] < 270:
            continue
        r["luck_gi"] = round(r["goals"] + r["assists"] - r["xgi90"] * games, 2)
        r["luck_cs"] = round(r["cs"] - games * math.exp(-r["xgc90"]), 2) if r["pos"] in ("DEF", "GK") else 0.0
        if r["pos"] in ("MID", "FWD"):
            d, kind = r["luck_gi"], "голы+ассисты vs xGI"
            thr = 1.5
        elif r["pos"] == "DEF":
            d, kind = r["luck_gi"] + r["luck_cs"] * 0.8, "xGI и чистые матчи vs ожидание"
            thr = 1.8
        else:
            d, kind = r["luck_cs"], "чистые матчи vs ожидание"
            thr = 1.5
        item = {"id": r["id"], "delta": round(d, 2), "kind": kind, "gi": r["goals"] + r["assists"],
                "xgi": round(r["xgi90"] * games, 1), "cs": r["cs"]}
        if d <= -thr:
            under.append(item)
        elif d >= thr:
            over.append(item)
        r["luck"] = round(d, 2)
    under.sort(key=lambda x: x["delta"])
    over.sort(key=lambda x: -x["delta"])
    return {"under": under[:20], "over": over[:20]}


# ============================================================================ 5. гонка за лигу
def build_race(ctx):
    cfg, M, gw_cur = ctx["cfg"], ctx["managers"], ctx["gw_cur"]
    table = ctx.get("league_table") or []
    by_entry = {r["entry"]: r for r in table}
    names = cfg["names"]
    players = {}
    for k, eid in cfg["entries"].items():
        pts = [g["pts"] for g in M[k].get("gw_points", []) if g.get("pts") is not None]
        tot = by_entry.get(eid, {}).get("total", M[k].get("overall_pts") or sum(pts))
        if not pts:
            continue
        season_mean = sum(pts) / len(pts)
        recent = pts[-5:]
        mean = 0.5 * season_mean + 0.5 * (sum(recent) / len(recent))
        sd = statistics.pstdev(pts) if len(pts) >= 3 else 15.0
        players[k] = {"total": tot, "mean": mean, "sd": max(10.0, sd)}
    if "me" not in players or len(players) < 2:
        return {}
    n_left = max(0, 38 - gw_cur)
    rnd = random.Random(42)
    N = 20000

    def sim(me_boost=0.0, me_mult=1.0):
        wins = {k: 0 for k in players}
        exp = {k: 0.0 for k in players}
        for _ in range(N):
            fin = {}
            for k, p in players.items():
                mu = p["mean"] + (me_boost if k == "me" else 0)
                sd = p["sd"] * (me_mult if k == "me" else 1)
                fin[k] = p["total"] + rnd.gauss(mu * n_left, sd * math.sqrt(max(n_left, 1)))
            w = max(fin, key=fin.get)
            wins[w] += 1
            for k in fin:
                exp[k] += fin[k]
        return {k: wins[k] / N for k in wins}, {k: exp[k] / N for k in exp}

    base, expected = sim()
    leader = max(players, key=lambda k: players[k]["total"])
    scen = []
    for b in (0.0, 2.0, 4.0):
        row = []
        for mult, pen in ((1.0, 0.0), (1.25, -0.5), (1.5, -1.0)):
            w, _ = sim(b + pen, mult)
            row.append(round(w["me"], 3))
        scen.append({"boost": b, "p": row})
    p_me = base["me"]
    if leader == "me":
        mode, text = "defend", "Ты лидируешь: защищай отрыв, избегай лишних хитов и ставок на «лотерейных» игроков."
    elif p_me < 0.35:
        mode, text = "chase", "Ты догоняешь: нужен более высокий риск — дифференциалы, ранние покупки на рост, чипы в удачные туры."
    else:
        mode, text = "balanced", "Шансы близки к равным: играй от xP, риск только за явный апгрейд стартера."
    gap = players[leader]["total"] - players["me"]["total"] if leader != "me" else 0
    chips = {k: [CHIP_RU[c] for c in chips_available(M[k].get("chips", []), ctx["gw_next"], cfg)] for k in M}
    return {
        "remaining": n_left, "leader": leader, "gap": gap, "mode": mode, "text": text, "sims": N,
        "players": {k: {"name": names.get(k, k), "total": v["total"], "mean": round(v["mean"], 1), "sd": round(v["sd"], 1),
                        "p_win": round(base[k], 3), "exp_final": round(expected[k])} for k, v in players.items()},
        "scenarios": scen, "chips_left": chips,
        "need_per_gw": round(gap / n_left, 1) if n_left else 0,
    }


# ============================================================================ экспорт в CSV
def export_csv(out_dir, data, R):
    d = os.path.join(out_dir, "export")
    os.makedirs(d, exist_ok=True)

    def w(name, header, rows):
        with open(os.path.join(d, name), "w", newline="", encoding="utf-8-sig") as f:
            cw = csv.writer(f, delimiter=";")
            cw.writerow(header)
            cw.writerows(rows)

    nm = lambda i: R[i]["name"] if i in R else str(i)
    w("players.csv", ["id", "игрок", "клуб", "поз", "цена", "рейтинг", "форма", "очки/игру", "xGI/90", "DC/90", "xP1", "xP5",
                      "в топе", "владение%", "статус", "занят"],
      [[p["id"], p["name"], p["tname"], p["pos"], p["price"] / 10, p["score"], p["form"], p["ppg"], p["xgi90"], p["dc90"],
        p["xp1"], p["xp5"], p["top_cnt"], p["own"], p["status"], p["taken_by"]] for p in data["players"]])
    w("my_squad.csv", ["игрок", "поз", "цена", "продажа", "xP1", "xP5"],
      [[nm(s["id"]), R[s["id"]]["pos"], s["now"] / 10, s["sell"] / 10, R[s["id"]]["xp1"], R[s["id"]]["xp5"]] for s in data["me"]["squad"]])
    plan = data.get("plan", {})
    w("plan.csv", ["тур", "ходы", "хит", "FT до", "xP тура", "капитан"],
      [[s["gw"], "; ".join("%s → %s" % (nm(o), nm(c)) for o, c in s["moves"]) or "—", s["hit"], s["ft_before"], s["value"],
        nm(s["captain"]) if s.get("captain") else ""] for s in plan.get("steps", [])])
    w("threats.csv", ["игрок", "риск перехвата", "мой прирост xP", "срочность"],
      [[nm(x["id"]), x["risk"], x["gain"], x["urgency"]] for x in data.get("threats", {}).get("intercept", [])])
    return d


# ============================================================================ сборка
def build(ctx):
    """ctx: bst, fixtures, rows, R, managers, taken, cfg, gw_cur, gw_next, sugg, mine_ids, con, league_table, verified."""
    res = {"warnings": check_schema(ctx["bst"], ctx.get("fixtures") or [])}
    try:
        ctx["plan_ins"] = []
        ctx["cfg"]["_deny"] = (build_threats(ctx) or {}).get("deny", {})
    except Exception as ex:
        ctx["cfg"]["_deny"] = {}
        res["warnings"].append("Эффект блокировки: %s" % ex)
    try:
        plan, chips = build_plan(ctx)
    except Exception as ex:                       # аналитика не должна ронять основной отчёт
        plan, chips = {"error": "план не построен: %s" % ex}, {}
        res["warnings"].append("Планировщик: %s" % ex)
    res["plan"] = plan
    res["chips"] = {k: v for k, v in chips.items() if k != "plan_ins"}
    ctx["plan_ins"] = chips.get("plan_ins", [])
    for name, fn in (("threats", build_threats), ("market", build_market), ("luck", build_luck), ("race", build_race)):
        try:
            res[name] = fn(ctx)
        except Exception as ex:
            res[name] = {}
            res["warnings"].append("%s: %s" % (name, ex))
    return res


def brief_lines(data, nm, names):
    L = []
    P = L.append
    plan = data.get("plan") or {}
    if plan.get("steps"):
        P("")
        P("## План трансферов на %d туров (оценка; перепроверь новостями)" % plan["horizon"])
        P("Прирост относительно «без трансферов»: +%.1f xP. Итого по плану %.1f xP." % (plan["gain"], plan["best_total"]))
        for s in plan["steps"]:
            mv = "; ".join("%s → %s" % (nm(o), nm(c)) for o, c in s["moves"]) or "без ходов"
            P("- GW%d: %s | FT до хода %d%s | xP тура %.1f | кап. %s" % (
                s["gw"], mv, s["ft_before"], (" | хит −%d" % s["hit"]) if s["hit"] else "", s["value"],
                nm(s["captain"]) if s.get("captain") else "—"))
        ch = data.get("chips") or {}
        if ch.get("recommend"):
            P("Чипы (доступно: %s):" % ", ".join(CHIP_RU[c] for c in ch["available"]))
            ex = ch.get("expiry") or {}
            if ex.get("active"):
                P("⚠ Чипы первого набора СГОРАЮТ после дедлайна GW%s (%s): осталось туров до сгорания — %s. Все доступные чипы нужно сыграть до этого срока." % (ex["gw"], ex.get("deadline"), ex["gws_left"]))
            if ch.get("schedule"):
                P("Согласованное расписание чипов (один чип на тур): " + "; ".join("%s — GW%d (+%.1f xP)" % (CHIP_RU[x["chip"]], x["gw"], x["gain"]) for x in ch["schedule"]))
            for c in ch["recommend"]:
                P("- %s: лучший тур GW%d, ориентир +%.1f xP (%s)" % (CHIP_RU[c["chip"]], c["gw"], c["gain"], c["note"]))
    th = data.get("threats") or {}
    if th.get("friends"):
        P("")
        P("## Соперники: ожидаемые ходы и угроза перехвата")
        for k, f in th["friends"].items():
            P("- %s: банк £%.1f, FT≈%s, ожидаемо ходов %.1f%s | вероятно продаст: %s | вероятно купит: %s" % (
                f["name"], f["bank"] / 10, f["ft"], f["exp_moves"], "" if f["verified"] else " (состав на прошлый дедлайн)",
                ", ".join("%s %d%%" % (nm(x["id"]), x["prob"] * 100) for x in f["sells"][:4]) or "—",
                ", ".join("%s %d%%" % (nm(x["id"]), x["prob"] * 100) for x in f["buys"][:4]) or "—"))
        if th.get("intercept"):
            P("Мои цели под угрозой перехвата (срочность = риск × мой прирост):")
            for x in th["intercept"][:8]:
                P("- %s: риск %d%% (%s), мой прирост +%.1f xP" % (
                    nm(x["id"]), x["risk"] * 100, ", ".join("%s %d%%" % (names.get(k, k), v * 100) for k, v in x["who"].items()), x["gain"]))
    mk = data.get("market") or {}
    if mk:
        P("")
        P("## Давление на цены (оценка по трансферам, порог ≈ %s чистых трансферов; калибровка: %d событий)" % (mk["thr"], mk["calib_events"]))
        if mk.get("targets_up"):
            P("Цели, которые дорожают (купить раньше): " + ", ".join(nm(x["id"]) for x in mk["targets_up"]))
        if mk.get("my_risk"):
            P("Мои игроки под угрозой падения цены: " + ", ".join(nm(x["id"]) for x in mk["my_risk"]))
        P("Растут: " + ", ".join("%s (%+d)" % (nm(x["id"]), x["net"]) for x in mk["rising"][:8]))
        P("Падают: " + ", ".join("%s (%+d)" % (nm(x["id"]), x["net"]) for x in mk["falling"][:8]))
    lk = data.get("luck") or {}
    if lk.get("under"):
        P("")
        P("## Недоудачливые (ожидаемый рост) / перегретые (ожидаемый спад)")
        P("Недоудача: " + ", ".join("%s %+.1f" % (nm(x["id"]), x["delta"]) for x in lk["under"][:8]))
        P("Перегрев: " + ", ".join("%s %+.1f" % (nm(x["id"]), x["delta"]) for x in lk["over"][:8]))
    rc = data.get("race") or {}
    if rc:
        P("")
        P("## Гонка за лигу (осталось %d туров)" % rc["remaining"])
        for k, p in rc["players"].items():
            P("- %s: %s очк., ср. %.1f за тур, шанс выиграть лигу %d%%, ожидаемый финал ≈ %s" % (
                p["name"], p["total"], p["mean"], p["p_win"] * 100, p["exp_final"]))
        P(rc["text"] + (" Отставание от лидера %s очк. (≈ %.1f за тур)." % (rc["gap"], rc["need_per_gw"]) if rc["gap"] else ""))
        P("Фишки: " + "; ".join("%s: %s" % (names.get(k, k), ", ".join(v) or "нет") for k, v in rc["chips_left"].items()))
    if data.get("warnings"):
        P("")
        P("## ⚠ Предупреждения инструмента")
        for w in data["warnings"]:
            P("- " + w)
    return L
