"""
Бэктест прогноза очков (v1.20, N0): насколько xP модели совпадает с тем, что игроки реально набрали.

Два режима:
  1) «Ретро» (walk-forward): для каждого сыгранного тура g (с 4-го) заново считаем прогноз только по данным
     ДО тура g (очки за игру, форма, минуты) и сравниваем с фактом. Так проверяется формула xP из fpl_tool.compute_players
     на уже накопленных данных (player_gw). Доступность (травмы) в прошлом неизвестна, считается 1.0 — это
     честная оговорка: ретро-оценка немного пессимистична к реальной xP.
  2) «Журнал» (forward): с v1.20 каждый запуск пишет в таблицу forecast прогноз на ближайший тур
     (xP1 нашей модели и ep_next от FPL). Когда тур сыгран, сверяем прогнозы, сделанные ДО его дедлайна.
     Это единственная по-настоящему честная проверка; копится с каждым туром.

Модели в сравнении:
  naive  — среднее очков за выход (без календаря и минут)
  mins   — среднее очков × вероятность выйти на поле (по минутам)
  xp     — текущая формула xP (регрессия формы к среднему × сложность × минуты)
  ep     — ep_next от FPL (только в журнале)

Метрики: MAE, RMSE, корреляция Пирсона и Спирмена (порядок игроков важнее точных чисел), смещение (прогноз − факт),
«топ-10 по позиции»: сколько очков в среднем набрали выбранные моделью лучшие — то, что реально важно для трансферов.
"""
import math

MIN_HISTORY = 3          # сколько туров истории нужно, чтобы начать ретро-оценку
POS_NAME = {1: "GK", 2: "DEF", 3: "MID", 4: "FWD"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS forecast(
  gw INTEGER, element INTEGER, snap_id INTEGER, made_at TEXT, xp1 REAL, ep_next REAL, avail REAL,
  PRIMARY KEY(gw, element));
"""


def ensure_schema(con):
    con.executescript(SCHEMA)


# ----------------------------------------------------------------------------- журнал прогнозов
def log_forecast(con, sid, ts, gw_next, rows, started_gw):
    """Пишем прогноз на ближайший тур. Пока тур не начался, прогноз перезаписывается свежим
    (в журнал попадает последний ДО дедлайна). Начавшийся/сыгранный тур не трогаем."""
    if gw_next <= started_gw:
        return 0
    con.executemany(
        "INSERT OR REPLACE INTO forecast VALUES(?,?,?,?,?,?,?)",
        [(gw_next, r["id"], sid, ts, r["xp1"], r["ep_next"], r["avail"]) for r in rows])
    con.commit()
    return len(rows)


# ----------------------------------------------------------------------------- метрики
def _rank(v):
    order = sorted(range(len(v)), key=lambda i: v[i])
    r = [0.0] * len(v)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
            j += 1
        for k in range(i, j + 1):
            r[order[k]] = (i + j) / 2.0
        i = j + 1
    return r


def _corr(a, b):
    n = len(a)
    if n < 3:
        return None
    ma, mb = sum(a) / n, sum(b) / n
    sa = math.sqrt(sum((x - ma) ** 2 for x in a))
    sb = math.sqrt(sum((y - mb) ** 2 for y in b))
    if sa == 0 or sb == 0:
        return None
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / (sa * sb)


def metrics(pred, act, pos=None):
    """pred/act — списки одной длины; pos — позиции для «топ-10 по позиции»."""
    n = len(pred)
    if n == 0:
        return None
    err = [p - a for p, a in zip(pred, act)]
    out = {
        "n": n,
        "mae": round(sum(abs(e) for e in err) / n, 3),
        "rmse": round(math.sqrt(sum(e * e for e in err) / n), 3),
        "bias": round(sum(err) / n, 3),
    }
    p = _corr(pred, act)
    s = _corr(_rank(pred), _rank(act))
    out["pearson"] = None if p is None else round(p, 3)
    out["spearman"] = None if s is None else round(s, 3)
    if pos:
        tops, allv = [], []
        for pp in set(pos):
            idx = [i for i in range(n) if pos[i] == pp]
            if len(idx) < 12:
                continue
            idx.sort(key=lambda i: -pred[i])
            tops.extend(act[i] for i in idx[:10])
            allv.extend(act[i] for i in idx)
        if tops:
            out["top10_actual"] = round(sum(tops) / len(tops), 2)     # факт у выбранных моделью
            out["pool_actual"] = round(sum(allv) / len(allv), 2)      # факт у всех игроков тех же позиций
    return out


# ----------------------------------------------------------------------------- ретро-оценка
def _fdr_by_event(fixtures):
    """(команда, тур) -> [сложность по матчам]"""
    d = {}
    for f in fixtures:
        ev = f.get("event")
        if not ev:
            continue
        d.setdefault((f["team_h"], ev), []).append(f.get("team_h_difficulty", 3))
        d.setdefault((f["team_a"], ev), []).append(f.get("team_a_difficulty", 3))
    return d


def retro(con, bst, fixtures, last_finished_gw, prior=None, k_grid=(3, 6, 10, 16)):
    """Walk-forward по турам MIN_HISTORY+1 … last_finished_gw. Возвращает {gw: {model: метрики}}.
    prior — {element: очки за 90 по прошлым сезонам}: если задан, добавляются модели xpK<k> (xP с якорем на прошлый сезон)."""
    prior = prior or {}
    els = {e["id"]: e for e in bst["elements"]}
    fdr = _fdr_by_event(fixtures)
    rows = con.execute("SELECT element, gw, pts, minutes FROM player_gw").fetchall()
    hist = {}        # element -> {gw: [pts, minutes]} (сумма по матчам тура)
    for el, gw, pts, mn in rows:
        h = hist.setdefault(el, {}).setdefault(gw, [0, 0])
        h[0] += pts or 0
        h[1] += mn or 0
    # матчей у команды в туре: чтобы знать, был ли вообще матч
    n_fix = {k: len(v) for k, v in fdr.items()}
    res = {}
    for g in range(MIN_HISTORY + 1, last_finished_gw + 1):
        past = range(1, g)
        # якорь по позиции: среднее очков за выход среди игроков основы (как в compute_players)
        pos_pts = {1: [], 2: [], 3: [], 4: []}
        per = {}
        for el, hh in hist.items():
            e = els.get(el)
            if not e:
                continue
            gp = [(gw, hh[gw]) for gw in past if gw in hh]
            apps = [(gw, v) for gw, v in gp if v[1] > 0]
            if not apps:
                continue
            tot_min = sum(v[1] for _, v in gp)
            ppg = sum(v[0] for _, v in apps) / len(apps)
            last = sorted(apps)[-4:]
            form = sum(v[0] for _, v in last) / len(last)
            mfrac = min(1.2, tot_min / float((g - 1) * 90))
            tot_pts = sum(v[0] for _, v in gp)
            per[el] = (ppg, form, mfrac, e, len(apps), (tot_pts / (tot_min / 90.0)) if tot_min else 0)
            if mfrac >= 0.5:
                pos_pts[e["element_type"]].append(ppg)
        import seasons as _se
        conv = _se.conv_factor([(v[0], v[5]) for v in per.values() if v[4] >= 3])
        pos_mean = {p: (sum(v) / len(v) if v else 3.5) for p, v in pos_pts.items()}
        P = {"naive": [], "mins": [], "xp": []}
        for k in k_grid:
            P["xpK%d" % k] = []
        A, POS = [], []
        for el, (ppg, form, mfrac, e, n_apps, _p90) in per.items():
            fx = fdr.get((e["team"], g), [])
            if not fx:
                continue                                    # в туре нет матча — не оцениваем
            act = hist.get(el, {}).get(g)
            if act is None:
                continue                                    # нет строки факта (игрок вне выборки истории)
            pp = max(0.15, min(1.0, mfrac / 0.8)) if g - 1 >= 3 else 1.0
            base = 0.7 * (0.5 * ppg + 0.5 * form) + 0.3 * pos_mean[e["element_type"]]
            P["naive"].append(ppg * len(fx))
            P["mins"].append(ppg * pp * len(fx))
            P["xp"].append(sum(base * (1 + 0.10 * (3 - d)) * pp for d in fx))
            p90 = prior.get(el)
            for k in k_grid:
                pe, fe, _w = _se.blend(ppg, form, n_apps, None if p90 is None else p90 * conv, k)
                b2 = 0.7 * (0.5 * pe + 0.5 * fe) + 0.3 * pos_mean[e["element_type"]]
                P["xpK%d" % k].append(sum(b2 * (1 + 0.10 * (3 - d)) * pp for d in fx))
            A.append(act[0])
            POS.append(e["element_type"])
        # оцениваем только тех, кто выходил в последних турах (иначе «мёртвые души» с нулём в прогнозе и факте раздувают корреляцию)
        keep = [i for i in range(len(A)) if P["mins"][i] > 0.4]
        if len(keep) < 30:
            continue
        sel = lambda v: [v[i] for i in keep]
        res[g] = {m: metrics(sel(P[m]), sel(A), sel(POS)) for m in P}
    return res


# ----------------------------------------------------------------------------- журнал: честная проверка
def forward(con, last_finished_gw):
    """Сверка прогнозов из таблицы forecast с фактом тура (только сыгранные туры)."""
    out = {}
    gws = [r[0] for r in con.execute("SELECT DISTINCT gw FROM forecast ORDER BY gw")]
    for g in gws:
        if g > last_finished_gw:
            continue
        q = con.execute(
            """SELECT f.xp1, f.ep_next, f.avail, SUM(p.pts), SUM(p.minutes)
               FROM forecast f JOIN player_gw p ON p.element=f.element AND p.gw=f.gw
               WHERE f.gw=? GROUP BY f.element""", (g,)).fetchall()
        q = [r for r in q if r[0] is not None and r[0] > 0.4]
        if len(q) < 30:
            continue
        act = [r[3] or 0 for r in q]
        out[g] = {"xp": metrics([r[0] for r in q], act), "ep": metrics([r[1] or 0 for r in q], act)}
    return out


def summarize(r):
    """Среднее по турам для каждой модели → короткая таблица для дашборда и brief."""
    keys = ("mae", "rmse", "bias", "pearson", "spearman", "top10_actual", "pool_actual")
    agg = {}
    for g, models in r.items():
        for m, v in models.items():
            if not v:
                continue
            a = agg.setdefault(m, {k: [] for k in keys})
            for k in keys:
                if v.get(k) is not None:
                    a[k].append(v[k])
    return {m: {k: (round(sum(x) / len(x), 3) if x else None) for k, x in a.items()} for m, a in agg.items()}


def build(con, bst, fixtures, last_finished_gw, prior_k=0):
    """Всё вместе → блок data['backtest']."""
    if last_finished_gw < MIN_HISTORY + 1:
        return {"ok": False, "note": "Мало сыгранных туров для оценки."}
    import seasons
    S = seasons.load(con)
    prior = {el: v for el, v in ((el, seasons.prior_pts90(x)) for el, x in S.items()) if v}
    grid = sorted({3, 6, 10, 16} | ({prior_k} if prior_k > 0 else set()))
    r = retro(con, bst, fixtures, last_finished_gw, prior, grid)
    f = forward(con, last_finished_gw)
    n_log = con.execute("SELECT COUNT(DISTINCT gw) FROM forecast").fetchone()[0]
    rsum = summarize(r)
    if prior_k > 0 and ("xpK%d" % prior_k) in rsum:
        rsum["xp_prior"] = rsum["xpK%d" % prior_k]
    return {
        "ok": bool(r),
        "prior_k": prior_k,
        "retro": {str(g): v for g, v in r.items()},
        "retro_summary": rsum,
        "forward": {str(g): v for g, v in f.items()},
        "forward_summary": summarize(f),
        "logged_gws": n_log,
        "note": ("Ретро: прогноз пересчитан по данным до каждого тура (травмы прошлого неизвестны, доступность = 1). "
                 "Журнал: реальные прогнозы, сохранённые до дедлайна; копится с v1.20."),
    }


def brief_lines(bt):
    L = []
    if not bt or not bt.get("ok"):
        return ["Бэктест: данных пока мало."]
    s = bt["retro_summary"]
    L.append("Ретро по %d турам (прогноз пересчитан по данным до тура):" % len(bt["retro"]))
    for m, lab in (("naive", "среднее очков"), ("mins", "среднее × минуты"), ("xp", "xP без прошлых сезонов"),
                   ("xp_prior", "xP с якорем на прошлый сезон (в работе, K=%s)" % bt.get("prior_k"))):
        v = s.get(m)
        if v:
            L.append("- %s: MAE %.2f, корр. %.2f (порядок %.2f), топ-10 по позиции в среднем %.2f очка (все игроки %.2f)" % (
                lab, v["mae"] or 0, v["pearson"] or 0, v["spearman"] or 0, v["top10_actual"] or 0, v["pool_actual"] or 0))
    fs = bt.get("forward_summary") or {}
    if fs:
        for m, lab in (("xp", "журнал: наша xP"), ("ep", "журнал: ep_next FPL")):
            v = fs.get(m)
            if v:
                L.append("- %s: MAE %.2f, корр. %.2f, топ-10 %.2f (туров в журнале: %d)" % (
                    lab, v["mae"] or 0, v["pearson"] or 0, v["top10_actual"] or 0, len(bt["forward"])))
    else:
        L.append("Журнал честных прогнозов копится (туров записано: %s); первое сравнение с ep_next — после сыгранного тура." % bt.get("logged_gws", 0))
    return L
