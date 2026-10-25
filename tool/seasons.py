"""
Прошлые сезоны игрока (v1.21, N7): `history_past` из element-summary (итоги по сезонам: очки, минуты, старты, голы, ассисты,
«сухие», цена в начале и конце сезона). Лишних запросов нет — те же ответы, что уже качает store_history.

Зачем: в начале сезона у игрока мало матчей, и форма/очки за игру шумят. Прошлый сезон — «якорь», вес которого падает
с каждым сыгранным матчем: w = K / (n + K), где n — матчей с выходом на поле в этом сезоне, K — «сила приора» в матчах
(подбирается бэктестом, `prior_k` в config.json; 0 — выключено).

Оговорки: в history_past нет клуба — смена клуба/роли видна только по скачку цены (помечаем); у новичков истории нет — для
них приор не применяется (прежняя формула).
"""
import statistics

NEW_W = 0.6          # вес последнего сезона (предпоследний — 1 − NEW_W)
MIN_SEASON_MIN = 450  # сезон короче этого в приор не берём
MIN_TOTAL_MIN = 900   # меньше — приор ненадёжен

SCHEMA = """
CREATE TABLE IF NOT EXISTS player_season(element INTEGER, season TEXT, pts INTEGER, minutes INTEGER, starts INTEGER,
  goals INTEGER, assists INTEGER, cs INTEGER, bonus INTEGER, xg REAL, xa REAL, c0 INTEGER, c1 INTEGER,
  PRIMARY KEY(element, season));
"""


def ensure_schema(con):
    con.executescript(SCHEMA)


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def store(con, results):
    """results — [(element, element-summary json)]. Перезаписывает сезоны игрока целиком."""
    n = 0
    for el, js in results:
        if not js:
            continue
        for h in js.get("history_past", []) or []:
            con.execute("INSERT OR REPLACE INTO player_season VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (el, h.get("season_name"), h.get("total_points", 0), h.get("minutes", 0), h.get("starts", 0),
                         h.get("goals_scored", 0), h.get("assists", 0), h.get("clean_sheets", 0), h.get("bonus", 0),
                         _f(h.get("expected_goals")), _f(h.get("expected_assists")),
                         h.get("start_cost", 0), h.get("end_cost", 0)))
            n += 1
    con.commit()
    return n


def load(con):
    """{element: [строки сезонов от новых к старым]}"""
    out = {}
    try:
        rows = con.execute("SELECT element, season, pts, minutes, starts, goals, assists, cs, bonus, xg, xa, c0, c1 "
                           "FROM player_season ORDER BY element, season DESC").fetchall()
    except Exception:
        return out
    for r in rows:
        out.setdefault(r[0], []).append(dict(zip(
            ("season", "pts", "min", "starts", "goals", "assists", "cs", "bonus", "xg", "xa", "c0", "c1"), r[1:])))
    return out


def prior_pts90(seasons):
    """Очки за 90 минут по двум последним содержательным сезонам или None."""
    use = [s for s in seasons if s["min"] >= MIN_SEASON_MIN][:2]
    if not use or sum(s["min"] for s in use) < MIN_TOTAL_MIN:
        return None
    ws = [NEW_W, 1 - NEW_W][:len(use)]
    num = sum(w * s["pts"] / (s["min"] / 90.0) for w, s in zip(ws, use))
    return num / sum(ws)


def conv_factor(pairs):
    """Перевод «очки за 90» в «очки за выход» (как у ppg FPL): медиана ppg / pts90 по игрокам этого сезона.
    pairs — [(ppg, pts90)] для игроков с достаточной историей в этом сезоне."""
    r = [p / q for p, q in pairs if q and q > 0.3 and p > 0]
    return statistics.median(r) if len(r) >= 20 else 0.82


def weight(n_apps, k):
    return 0.0 if k <= 0 else k / (n_apps + k)


def blend(ppg, form, n_apps, prior_ppg, k):
    """Возвращает (ppg_eff, form_eff, w). prior_ppg None → без изменений."""
    if prior_ppg is None or k <= 0:
        return ppg, form, 0.0
    w = weight(n_apps, k)
    return (1 - w) * ppg + w * prior_ppg, (1 - w) * form + w * prior_ppg, w


def note(seasons, pos=None):
    """Короткий вывод словами для карточки игрока."""
    if not seasons:
        return "Нет данных АПЛ за прошлые сезоны: оценка опирается только на этот сезон."
    full = [s for s in seasons if s["min"] >= 2000]
    last = seasons[0]
    if len(full) >= 3:
        txt = "Основной игрок: %d из последних %d сезонов с 2000+ минут" % (len(full), len(seasons))
    elif last["min"] >= 2000:
        txt = "Прошлый сезон — основной игрок (%d мин, %d стартов)" % (last["min"], last["starts"])
    elif last["min"] >= 900:
        txt = "Прошлый сезон — частичная роль (%d мин, %d стартов)" % (last["min"], last["starts"])
    else:
        txt = "Прошлый сезон — мало игрового времени (%d мин)" % last["min"]
    return txt


def card(seasons, now_cost=None):
    """Данные для карточки: до 3 сезонов + вывод + пометка о возможной смене роли (скачок цены к текущей)."""
    rows = []
    for s in seasons[:3]:
        rows.append({"season": s["season"], "pts": s["pts"], "min": s["min"], "starts": s["starts"],
                     "ga": s["goals"] + s["assists"], "cs": s["cs"], "c0": s["c0"], "c1": s["c1"],
                     "p90": round(s["pts"] / (s["min"] / 90.0), 2) if s["min"] >= 90 else None})
    flag = None
    if seasons and now_cost and seasons[0]["c1"] and abs(now_cost - seasons[0]["c1"]) >= 20:
        flag = "Цена изменилась на %.1f с конца прошлого сезона — роль или клуб могли поменяться — проверь новости." % (
            (now_cost - seasons[0]["c1"]) / 10.0)
    return {"rows": rows, "note": note(seasons), "flag": flag}


def load_prior_map(db_path):
    """{element: очки за 90 по прошлым сезонам} — читаем базу до её открытия основным кодом (первый запуск: пусто)."""
    import os
    import sqlite3
    if not os.path.exists(db_path):
        return {}
    try:
        con = sqlite3.connect(db_path, timeout=30)
        try:
            S = load(con)
        finally:
            con.close()
    except Exception:
        return {}
    m = {el: prior_pts90(v) for el, v in S.items()}
    return {el: v for el, v in m.items() if v}
