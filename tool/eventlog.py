"""
Журнал событий (v1.20, N19 + часть N26). Дневной снимок слишком грубый: цена и флаги травм меняются в любой момент.
При каждом запуске (в облаке — раз в 3 часа) сверяем игроков с прошлым состоянием и пишем ИЗМЕНЕНИЯ с временем:
  * price_event  — смена цены (кто, когда, было → стало, владение и чистый поток трансферов на момент смены);
  * status_event — смена статуса/шанса сыграть/текста новости (с `news_added` от FPL, если есть).
Это нужно для: калибровки прогноза цен (предсказали → сменилась ли), ленты «что изменилось за сутки» и уведомлений.
Первый запуск только запоминает исходное состояние (событий нет).
"""
SCHEMA = """
CREATE TABLE IF NOT EXISTS elem_last(element INTEGER PRIMARY KEY, price INTEGER, status TEXT, chance INTEGER, news TEXT);
CREATE TABLE IF NOT EXISTS price_event(ts TEXT, element INTEGER, old INTEGER, new INTEGER, own REAL, net INTEGER);
CREATE TABLE IF NOT EXISTS status_event(ts TEXT, element INTEGER, old_status TEXT, new_status TEXT,
  old_chance INTEGER, new_chance INTEGER, news TEXT, news_added TEXT);
CREATE INDEX IF NOT EXISTS idx_price_event_ts ON price_event(ts);
CREATE INDEX IF NOT EXISTS idx_status_event_ts ON status_event(ts);
"""


def ensure_schema(con):
    con.executescript(SCHEMA)


def log_changes(con, ts, bst):
    """Возвращает (число смен цены, число смен статуса)."""
    last = {r[0]: r[1:] for r in con.execute("SELECT element, price, status, chance, news FROM elem_last")}
    first_run = not last
    n_p = n_s = 0
    upd = []
    for e in bst["elements"]:
        i = e["id"]
        price, st = e.get("now_cost", 0), e.get("status", "a")
        ch, news = e.get("chance_of_playing_next_round"), e.get("news") or ""
        upd.append((i, price, st, ch, news))
        old = last.get(i)
        if first_run or old is None:
            continue
        if old[0] != price:
            net = (e.get("transfers_in_event") or 0) - (e.get("transfers_out_event") or 0)
            try:
                own = float(e.get("selected_by_percent") or 0)
            except ValueError:
                own = 0.0
            con.execute("INSERT INTO price_event VALUES(?,?,?,?,?,?)", (ts, i, old[0], price, own, net))
            n_p += 1
        if (old[1], old[2], old[3]) != (st, ch, news):
            con.execute("INSERT INTO status_event VALUES(?,?,?,?,?,?,?,?)",
                        (ts, i, old[1], st, old[2], ch, news, e.get("news_added")))
            n_s += 1
    con.executemany("INSERT OR REPLACE INTO elem_last VALUES(?,?,?,?,?)", upd)
    con.commit()
    return n_p, n_s


def recent(con, since_ts, limit=60):
    """Последние события для brief/дашборда."""
    pe = con.execute("SELECT ts, element, old, new, own, net FROM price_event WHERE ts>=? ORDER BY ts DESC LIMIT ?",
                     (since_ts, limit)).fetchall()
    se = con.execute("SELECT ts, element, old_status, new_status, old_chance, new_chance, news FROM status_event "
                     "WHERE ts>=? ORDER BY ts DESC LIMIT ?", (since_ts, limit)).fetchall()
    return {"price": [dict(zip(("ts", "id", "old", "new", "own", "net"), r)) for r in pe],
            "status": [dict(zip(("ts", "id", "old_status", "new_status", "old_chance", "new_chance", "news"), r)) for r in se]}
