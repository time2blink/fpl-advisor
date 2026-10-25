#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FPL League Advisor — локальный инструмент аналитики.

Что делает:
  1. Скачивает данные из открытого API FPL (без ключа и логина).
  2. Кладёт ежедневный снимок в SQLite (data/fpl.db) -> тренды, новички, ушедшие.
  3. Считает рейтинги игроков, ожидаемые очки (xP) с учётом календаря, подбор по бюджету.
  4. Следит за составами тебя, Стаса и Ромы (из API, без скриншотов).
  5. Пишет out/dashboard.html (красивый дашборд), out/claude_brief.md (данные для Claude), out/data.json.

Только стандартная библиотека Python 3.8+ (pip ничего ставить не нужно).

Запуск:
  python fpl_tool.py                # скачать + посчитать + собрать дашборд
  python fpl_tool.py --offline      # без сети, из папки mock/ (для проверки)
  python fpl_tool.py --no-history   # быстрее: не качать историю игроков по турам
"""
import argparse
import datetime as dt
import itertools
import json
import math
import os
import re
import shutil
import sqlite3
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

BASE = os.environ.get("FPL_BASE", "https://fantasy.premierleague.com/api")
HERE = os.path.dirname(os.path.abspath(__file__))
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
sys.path.insert(0, HERE)
import analytics  # noqa: E402
import probs  # noqa: E402  (v1.19: CS %, DC %, голы/ассисты, стандарты, live)
import backtest  # noqa: E402  (v1.20: проверка точности прогноза)
import eventlog  # noqa: E402  (v1.20: журнал смен цен и статусов)
import seasons  # noqa: E402  (v1.21: прошлые сезоны игроков)

WARNINGS = []
POS = {1: "GK", 2: "DEF", 3: "MID", 4: "FWD"}
OFFLINE = False


# ----------------------------------------------------------------------------- сеть
def _mock_name(path):
    s = path.strip("/").replace("/", "_").replace("?", "_").replace("=", "_").replace("&", "_")
    return os.path.join(HERE, "mock", s + ".json")


CACHE_DIR = os.environ.get("FPL_CACHE_DIR") or os.path.join(HERE, "cache")
FORCE = False
FRIENDS = set()                      # ID менеджеров мини-лиги (их данные освежаем чаще всего)
STATS = {"cache": 0, "net": 0, "stale": 0}
_last = [0.0]
_lock = threading.Lock()


def _ttl(path):
    """Сколько секунд ответ API считается свежим (дальше — снова идём в сеть)."""
    if path.startswith("bootstrap-static"):
        return 10 * 60            # цены/новости/владение
    if path.startswith("fixtures"):
        return 6 * 3600
    if path.startswith("element-summary"):
        return 12 * 3600          # история игрока меняется только после матчей
    if re.match(r"event/\d+/live", path):
        return 60                 # очки тура вживую
    if path.startswith("leagues-classic/314"):
        return 3600               # топ-50 мира
    if path.startswith("leagues-classic"):
        return 15 * 60
    m = re.match(r"entry/(\d+)/(.*)", path)
    if m:
        rest = m.group(2)
        if int(m.group(1)) in FRIENDS:
            return 5 * 60         # составы тебя/Стаса/Ромы — самое «живое»
        if rest.startswith("event/"):
            return 24 * 3600      # составы топ-менеджеров за сыгранный тур не меняются
        if rest.startswith("transfers"):
            return 3 * 3600
        return 6 * 3600
    return 10 * 60


def _cache_file(path):
    return os.path.join(CACHE_DIR, re.sub(r"[^A-Za-z0-9_.-]", "_", path.strip("/")) + ".json")


def _throttle():
    """Не чаще ~8 запросов в секунду суммарно — вежливо к API."""
    with _lock:
        wait = 0.12 - (time.time() - _last[0])
        if wait > 0:
            time.sleep(wait)
        _last[0] = time.time()


def _bump(k):
    with _lock:
        STATS[k] += 1


def get(path, retries=3, optional=False):
    """GET JSON: сначала кэш (по TTL), потом сеть; при сбое — устаревший кэш. В offline — из mock/."""
    if OFFLINE:
        fn = _mock_name(path)
        if not os.path.exists(fn):
            return None
        with open(fn, "r", encoding="utf-8") as f:
            return json.load(f)
    fn = _cache_file(path)
    cached = None
    if os.path.exists(fn):
        try:
            with open(fn, "r", encoding="utf-8") as f:
                cached = json.load(f)
        except Exception:
            cached = None
    if cached is not None and not FORCE and time.time() - cached.get("ts", 0) < _ttl(path):
        _bump("cache")
        return cached.get("data")
    url = BASE + "/" + path.lstrip("/")
    last = None
    for i in range(retries):
        _throttle()
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as r:
                data = json.loads(r.read().decode("utf-8"))
            _bump("net")
            _write_cache(fn, {"ts": time.time(), "data": data, "status": 200})
            return data
        except urllib.error.HTTPError as e:
            last = e
            if e.code == 404:
                _bump("net")
                _write_cache(fn, {"ts": time.time(), "data": None, "status": 404})
                return None
            if e.code == 429:     # просят притормозить
                try:
                    wait = int(e.headers.get("Retry-After", "30"))
                except Exception:
                    wait = 30
                time.sleep(min(wait, 60))
                continue
        except Exception as e:
            last = e
        time.sleep(1.5 * (i + 1))
    if cached is not None:        # сеть/API недоступны — используем старые данные
        _bump("stale")
        return cached.get("data")
    if optional:
        return None
    raise RuntimeError("Не удалось получить %s: %s" % (url, last))


def _write_cache(fn, obj):
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        tmp = fn + ".tmp%d" % threading.get_ident()
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(obj, f)
        os.replace(tmp, fn)
    except Exception:
        pass


# ----------------------------------------------------------------------------- БД
SCHEMA = """
CREATE TABLE IF NOT EXISTS snapshots(id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, gw INTEGER, day TEXT);
CREATE TABLE IF NOT EXISTS player_snap(
  snap_id INTEGER, element INTEGER, price INTEGER, own REAL, form REAL, ppg REAL, pts INTEGER,
  minutes INTEGER, status TEXT, news TEXT, chance INTEGER, ep_next REAL, tin INTEGER, tout INTEGER,
  in_pool INTEGER, score REAL, xp5 REAL,
  PRIMARY KEY(snap_id, element));
CREATE TABLE IF NOT EXISTS player_gw(element INTEGER, gw INTEGER, pts INTEGER, minutes INTEGER, xgi REAL,
  opp INTEGER, home INTEGER, PRIMARY KEY(element, gw, opp));
CREATE TABLE IF NOT EXISTS top_owned(snap_id INTEGER, element INTEGER, cnt INTEGER, n INTEGER,
  PRIMARY KEY(snap_id, element));
CREATE TABLE IF NOT EXISTS manager_snap(snap_id INTEGER, key TEXT, json TEXT, PRIMARY KEY(snap_id, key));
"""


def _data_dir():
    d = os.environ.get("FPL_DATA_DIR") or os.path.join(HERE, "data")
    os.makedirs(d, exist_ok=True)
    return d


def _db_ok(path):
    try:
        c = sqlite3.connect(path)
        r = c.execute("PRAGMA quick_check").fetchone()
        c.close()
        return bool(r) and r[0] == "ok"
    except Exception:
        return False


def _backup_dir(d):
    b = os.path.join(d, "backup")
    os.makedirs(b, exist_ok=True)
    return b


BACKUP_KEEP = 3      # максимум резервных копий базы (по одной в день, старые удаляются сами)
CORRUPT_KEEP = 2     # максимум «битых» баз, отложенных в сторону
CACHE_MAX_AGE_DAYS = 3


def _trim(folder, prefix, suffix, keep):
    try:
        files = sorted(f for f in os.listdir(folder) if f.startswith(prefix) and f.endswith(suffix))
        for f in files[:-keep] if keep > 0 else files:
            os.remove(os.path.join(folder, f))
    except Exception:
        pass


def prune_cache():
    """Кэш ответов API старше 3 суток удаляем — папка не разрастается."""
    if not os.path.isdir(CACHE_DIR):
        return 0
    n, limit = 0, time.time() - CACHE_MAX_AGE_DAYS * 86400
    for f in os.listdir(CACHE_DIR):
        fp = os.path.join(CACHE_DIR, f)
        try:
            if os.path.getmtime(fp) < limit:
                os.remove(fp)
                n += 1
        except Exception:
            pass
    return n


def backup_db(d, path):
    """Одна резервная копия в день; хранится не больше BACKUP_KEEP штук."""
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return
    b = _backup_dir(d)
    dst = os.path.join(b, "fpl_%s.db" % dt.datetime.utcnow().strftime("%Y%m%d"))
    if not os.path.exists(dst):
        shutil.copy2(path, dst)
    _trim(b, "fpl_", ".db", BACKUP_KEEP)


def db_open():
    d = _data_dir()
    path = os.path.join(d, "fpl.db")
    if os.path.exists(path) and os.path.getsize(path) > 0:
        if _db_ok(path):
            backup_db(d, path)                       # копия ДО любых записей
        else:                                         # база повреждена -> откат к последней копии
            bad = path + ".corrupt-" + dt.datetime.utcnow().strftime("%Y%m%d%H%M%S")
            os.replace(path, bad)
            _trim(d, "fpl.db.corrupt-", "", CORRUPT_KEEP)
            print("  ! База повреждена, сохранил как", os.path.basename(bad))
            b = _backup_dir(d)
            cands = sorted(f for f in os.listdir(b) if f.startswith("fpl_") and f.endswith(".db"))
            if cands:
                shutil.copy2(os.path.join(b, cands[-1]), path)
                print("  ✓ Восстановил из копии", cands[-1])
    con = sqlite3.connect(path, timeout=30)
    con.executescript(SCHEMA)
    _migrate(con)
    return con


def _migrate(con):
    cols = [r[1] for r in con.execute("PRAGMA table_info(snapshots)")]
    if "day" not in cols:
        con.execute("ALTER TABLE snapshots ADD COLUMN day TEXT")
    # один снимок в день: оставляем самый поздний, остальные (старые частые запуски) удаляем
    rows = con.execute("SELECT id, ts, day FROM snapshots ORDER BY id").fetchall()
    keep = {}
    for sid, ts, day in rows:
        keep[day or (ts or "")[:10]] = sid
    keep_ids = set(keep.values())
    for sid, ts, day in rows:
        if sid not in keep_ids:
            for t in ("player_snap", "top_owned", "manager_snap"):
                con.execute("DELETE FROM %s WHERE snap_id=?" % t, (sid,))
            con.execute("DELETE FROM snapshots WHERE id=?", (sid,))
    for d_, sid in keep.items():
        con.execute("UPDATE snapshots SET day=? WHERE id=? AND (day IS NULL OR day<>?)", (d_, sid, d_))
    con.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_snap_day ON snapshots(day)")
    con.commit()


def prune(con, keep_days=90):
    """Старше keep_days храним только по одному снимку в неделю (понедельник) — база не раздувается."""
    cutoff = (dt.datetime.utcnow() - dt.timedelta(days=keep_days)).strftime("%Y-%m-%d")
    old = [r[0] for r in con.execute(
        "SELECT id FROM snapshots WHERE day<? AND CAST(strftime('%w', day) AS INTEGER)<>1", (cutoff,))]
    for sid in old:
        for t in ("player_snap", "top_owned", "manager_snap"):
            con.execute("DELETE FROM %s WHERE snap_id=?" % t, (sid,))
        con.execute("DELETE FROM snapshots WHERE id=?", (sid,))
    con.commit()
    if len(old) > 20:
        con.execute("VACUUM")
    return len(old)


def _pid_alive(pid):
    try:
        if os.name == "nt":
            import ctypes
            h = ctypes.windll.kernel32.OpenProcess(0x1000, False, int(pid))  # PROCESS_QUERY_LIMITED_INFORMATION
            if not h:
                return False
            code = ctypes.c_ulong()
            ctypes.windll.kernel32.GetExitCodeProcess(h, ctypes.byref(code))
            ctypes.windll.kernel32.CloseHandle(h)
            return code.value == 259  # STILL_ACTIVE
        os.kill(int(pid), 0)
        return True
    except Exception:
        return False


def acquire_lock():
    """Защита от двух одновременных запусков. Если прошлый запуск закрыли посреди работы, зависший lock игнорируется."""
    lock = os.path.join(_data_dir(), ".lock")
    if os.path.exists(lock):
        try:
            old_pid = open(lock).read().strip()
        except OSError:
            old_pid = ""
        if old_pid.isdigit() and int(old_pid) != os.getpid() and _pid_alive(old_pid) and time.time() - os.path.getmtime(lock) < 600:
            raise SystemExit("Уже идёт другой запуск. Подожди минуту.")
    with open(lock, "w") as f:
        f.write(str(os.getpid()))
    import atexit
    atexit.register(lambda: os.path.exists(lock) and os.remove(lock))
    return lock


# ----------------------------------------------------------------------------- утилиты
def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def pct_rank(values):
    """Процентиль 0..1 для каждого значения списка."""
    n = len(values)
    if n <= 1:
        return [0.5] * n
    order = sorted(range(n), key=lambda i: values[i])
    out = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and values[order[j + 1]] == values[order[i]]:
            j += 1
        r = (i + j) / 2.0 / (n - 1)
        for k in range(i, j + 1):
            out[order[k]] = r
        i = j + 1
    return out


def fnum(x, d=0.0):
    try:
        return float(x)
    except (TypeError, ValueError):
        return d


def availability(e):
    st = e.get("status", "a")
    ch = e.get("chance_of_playing_next_round")
    if st in ("s", "u", "n"):
        return 0.0
    if ch is not None:
        return clamp(ch / 100.0, 0, 1)
    return {"a": 1.0, "d": 0.5, "i": 0.0}.get(st, 0.5)


def sell_price(buy, now):
    """Цена продажи FPL: покупка + половина прибыли (округление вниз до 0.1)."""
    if now > buy:
        return buy + (now - buy) // 2
    return now


# ----------------------------------------------------------------------------- расчёт
def build_fixtures(fixtures, teams, next_gw, horizon):
    """team_id -> {event: [(opp_id, home, fdr)]} на горизонт."""
    out = {t: {} for t in teams}
    for f in fixtures:
        ev = f.get("event")
        if ev is None or ev < next_gw or ev >= next_gw + horizon:
            continue
        out[f["team_h"]].setdefault(ev, []).append((f["team_a"], True, f["team_h_difficulty"]))
        out[f["team_a"]].setdefault(ev, []).append((f["team_h"], False, f["team_a_difficulty"]))
    return out


def team_ease(tfix, next_gw, horizon):
    tot = 0.0
    for ev in range(next_gw, next_gw + horizon):
        s = sum(1 - (fd - 2) / 3.0 for (_, _, fd) in tfix.get(ev, []))
        tot += min(1.3, s)
    return clamp(tot / horizon, 0, 1)


def compute_players(bst, fixtures, cfg, gw_cur, gw_next, prior90=None):
    teams = {t["id"]: t for t in bst["teams"]}
    horizon = cfg.get("horizon", 5)
    chipH = max(0, cfg.get("chip_expiry_gw", 19) - gw_next + 1) if gw_next <= cfg.get("chip_expiry_gw", 19) else 0
    planH = max(1, min(max(cfg.get("planner_horizon", 8), chipH), 39 - gw_next))  # xP по турам: хватает и на план, и на чипы до сгорания
    fx = build_fixtures(fixtures, teams, gw_next, max(horizon, planH))
    gws_played = max(1, gw_cur)
    # среднее очков/игру по позиции среди игроков основы — «якорь» против перегрева формы (регрессия к среднему)
    pos_mean = {}
    for pos_id, pos_name in POS.items():
        vals = [fnum(e.get("points_per_game")) for e in bst["elements"]
                if e["element_type"] == pos_id and e.get("minutes", 0) >= 0.5 * gws_played * 90]
        pos_mean[pos_name] = sum(vals) / len(vals) if vals else 3.5
    # v1.21: якорь на прошлые сезоны (вес K/(n+K), n — выходов на поле в этом сезоне); prior_k=0 выключает
    prior_k = cfg.get("prior_k", 4)
    prior90 = prior90 or {}
    conv = seasons.conv_factor([(fnum(e.get("points_per_game")), e.get("total_points", 0) / (e["minutes"] / 90.0))
                                for e in bst["elements"] if e.get("minutes", 0) >= 270]) if prior90 and prior_k > 0 else 0.82
    rows = []
    for e in bst["elements"]:
        pos = POS[e["element_type"]]
        mins = e.get("minutes", 0)
        mfrac = clamp(mins / float(gws_played * 90), 0, 1.2)
        avail = availability(e)
        ppg = fnum(e.get("points_per_game"))
        form = fnum(e.get("form"))
        p90 = prior90.get(e["id"])
        prior_ppg = None if p90 is None else p90 * conv
        n_apps = (e.get("total_points", 0) / ppg) if ppg > 0 else 0
        ppg_e, form_e, prior_w = seasons.blend(ppg, form, n_apps, prior_ppg, prior_k)   # только для xP; в карточке остаются факты
        tfix = fx.get(e["team"], {})
        base = 0.7 * (0.5 * ppg_e + 0.5 * form_e) + 0.3 * pos_mean[pos]
        pp = clamp(mfrac / 0.8, 0.15, 1.0) if gws_played >= 3 else 1.0

        def xp_event(ev):
            return sum(base * (1 + 0.10 * (3 - fd)) * pp * avail for (_, _, fd) in tfix.get(ev, []))

        xp1 = xp_event(gw_next)
        xp5 = sum(xp_event(ev) for ev in range(gw_next, gw_next + horizon))
        rows.append({
            "id": e["id"], "name": e["web_name"], "full": "%s %s" % (e.get("first_name", ""), e.get("second_name", "")),
            "team": e["team"], "tname": teams[e["team"]]["short_name"], "pos": pos,
            "pcode": e.get("code"), "tcode": teams[e["team"]].get("code"), "photo": e.get("photo", ""),
            "price": e["now_cost"], "price_start": e["now_cost"] - e.get("cost_change_start", 0),
            "own": fnum(e.get("selected_by_percent")), "form": form, "ppg": ppg, "pts": e.get("total_points", 0),
            "minutes": mins, "mfrac": round(mfrac, 2), "status": e.get("status", "a"),
            "news": e.get("news", "") or "", "chance": e.get("chance_of_playing_next_round"),
            "prior_w": round(prior_w, 2), "ep_next": fnum(e.get("ep_next")), "tin": e.get("transfers_in_event", 0),
            "tout": e.get("transfers_out_event", 0),
            "xgi90": fnum(e.get("expected_goal_involvements_per_90")),
            "xgc90": fnum(e.get("expected_goals_conceded_per_90")),
            "dc90": fnum(e.get("defensive_contribution_per_90")),
            "cs": e.get("clean_sheets", 0), "goals": e.get("goals_scored", 0), "assists": e.get("assists", 0),
            "bonus": e.get("bonus", 0), "avail": round(avail, 2),
            "ease": round(team_ease(tfix, gw_next, horizon), 2),
            "fix": [{"gw": ev, "opp": teams[o]["short_name"], "h": h, "fdr": fd}
                    for ev in range(gw_next, gw_next + horizon) for (o, h, fd) in tfix.get(ev, [])],
            "nfix": sum(len(tfix.get(ev, [])) for ev in range(gw_next, gw_next + horizon)),
            "xp1": round(xp1, 2), "xp5": round(xp5, 2),
            "xpg": [round(xp_event(ev), 2) for ev in range(gw_next, gw_next + planH)],
        })
    # композитный скор внутри позиции (только игроки с достаточными минутами)
    minfrac = cfg.get("min_minutes_frac", 0.25)
    for pos in POS.values():
        grp = [r for r in rows if r["pos"] == pos and r["mfrac"] >= minfrac]
        if not grp:
            continue
        p_ppg = pct_rank([r["ppg"] for r in grp])
        p_form = pct_rank([r["form"] for r in grp])
        if pos in ("MID", "FWD"):
            p_met = pct_rank([r["xgi90"] for r in grp])
        elif pos == "DEF":
            a = pct_rank([r["dc90"] for r in grp])
            b = pct_rank([-r["xgc90"] for r in grp])
            p_met = [(x + y) / 2 for x, y in zip(a, b)]
        else:
            p_met = pct_rank([-r["xgc90"] for r in grp])
        p_val = pct_rank([r["ppg"] / max(r["price"], 1) for r in grp])
        for i, r in enumerate(grp):
            s = (0.28 * p_ppg[i] + 0.20 * p_form[i] + 0.22 * p_met[i] + 0.15 * r["ease"]
                 + 0.10 * clamp(r["mfrac"], 0, 1) + 0.05 * p_val[i])
            r["score"] = round(100 * s * (0.35 + 0.65 * r["avail"]), 1)
    for r in rows:
        r.setdefault("score", 0.0)
    return rows, teams


def pool_ids(rows, cfg, extra_ids):
    pool = set(extra_ids)
    for pos, n in cfg["pool"].items():
        grp = sorted([r for r in rows if r["pos"] == pos], key=lambda r: -r["pts"])[:n]
        pool.update(r["id"] for r in grp)
        grp2 = sorted([r for r in rows if r["pos"] == pos and r["mfrac"] >= cfg.get("min_minutes_frac", 0.25)],
                      key=lambda r: -r["form"])[:max(5, n // 5)]
        pool.update(r["id"] for r in grp2)
        grp3 = sorted([r for r in rows if r["pos"] == pos], key=lambda r: -r["score"])[:max(5, n // 5)]
        pool.update(r["id"] for r in grp3)
    return pool


# ----------------------------------------------------------------------------- менеджеры
def free_transfers_estimate(events_tr, chips, gw_cur, gw_next, cap):
    """Оценка свободных трансферов на ближайший дедлайн (с учётом уже сделанных ходов на него)."""
    chip_ev = {}
    for c in chips:
        chip_ev[c["event"]] = c["name"]
    ft = 1  # на GW2
    for ev in range(2, gw_next):
        used = events_tr.get(ev, 0)
        if chip_ev.get(ev) in ("wildcard", "freehit"):
            pass
        else:
            ft = ft - min(used, ft)
        ft = min(cap, ft + 1)
    # ft = доступно на gw_next до ходов; вычитаем уже сделанные на gw_next
    used_next = events_tr.get(gw_next, 0)
    if chip_ev.get(gw_next) in ("wildcard", "freehit"):
        return ft, ft
    return max(0, ft - used_next), ft


def _norm(x):
    import unicodedata
    x = unicodedata.normalize("NFKD", x)
    x = "".join(c for c in x if not unicodedata.combining(c))
    return "".join(c for c in x.lower() if c.isalnum())


def resolve_player(spec, bst):
    """'Thomas:COV' или 'Haaland' -> element id. Берёт совпадение по web_name (+клуб), при неоднозначности — с большим числом очков."""
    name, _, team = spec.partition(":")
    tcode = {t["short_name"].upper(): t["id"] for t in bst["teams"]}
    tid = tcode.get(team.strip().upper()) if team else None
    n = _norm(name)
    exact = [e for e in bst["elements"] if _norm(e["web_name"]) == n and (tid is None or e["team"] == tid)]
    cands = exact or [e for e in bst["elements"] if n and n in _norm(e["web_name"]) and (tid is None or e["team"] == tid)]
    if not cands:
        raise ValueError("Не нашёл игрока '%s' (config.json → pending). Укажи как Имя:КЛУБ, например Thomas:COV" % spec)
    cands.sort(key=lambda e: -e.get("total_points", 0))
    return cands[0]["id"]


def load_manager(key, entry_id, bst, gw_cur, gw_next, cfg):
    info = get("entry/%d/" % entry_id, optional=True) or {}
    hist = get("entry/%d/history/" % entry_id, optional=True) or {"current": [], "chips": []}
    transfers = get("entry/%d/transfers/" % entry_id, optional=True) or []
    picks_cur = get("entry/%d/event/%d/picks/" % (entry_id, gw_cur), optional=True)
    picks_next = get("entry/%d/event/%d/picks/" % (entry_id, gw_next), optional=True)
    els = {e["id"]: e for e in bst["elements"]}

    tr_by_ev = {}
    for t in transfers:
        tr_by_ev[t["event"]] = tr_by_ev.get(t["event"], 0) + 1

    # состав и банк на ближайший дедлайн
    if picks_next and picks_next.get("picks"):
        picks = picks_next["picks"]
        bank = (picks_next.get("entry_history") or {}).get("bank")
        value = (picks_next.get("entry_history") or {}).get("value")
        source = "picks_next"
    elif picks_cur and picks_cur.get("picks"):
        picks = [dict(p) for p in picks_cur["picks"]]
        eh = picks_cur.get("entry_history") or {}
        bank, value = eh.get("bank", 0), eh.get("value", 0)
        for t in sorted([t for t in transfers if t["event"] == gw_next], key=lambda x: x["time"]):
            for p in picks:
                if p["element"] == t["element_out"]:
                    p["element"] = t["element_in"]
                    break
            bank = (bank or 0) + t["element_out_cost"] - t["element_in_cost"]
        source = "picks_cur+transfers"
    else:
        picks, bank, value, source = [], 0, 0, "none"

    # цены покупки -> цена продажи
    last_in = {}
    for t in sorted(transfers, key=lambda x: x["time"]):
        last_in[t["element_in"]] = t["element_in_cost"]
    squad = []
    for p in picks:
        e = els.get(p["element"])
        if not e:
            continue
        buy = last_in.get(p["element"], e["now_cost"] - e.get("cost_change_start", 0))
        squad.append({
            "id": e["id"], "pos_slot": p.get("position"), "captain": p.get("is_captain", False),
            "vice": p.get("is_vice_captain", False), "buy": buy, "now": e["now_cost"],
            "sell": sell_price(buy, e["now_cost"]),
        })
    pend = (cfg.get("pending") or {}).get(key)
    ft_manual = None
    if pend and pend.get("squad") and (source == "picks_next" or (isinstance(pend.get("gw"), int) and pend["gw"] <= gw_cur)):
        # дедлайн тура, на который вводили pending, прошёл: API уже показывает реальный состав — ручной pending устарел
        # (v1.19.1: pending.gw — тур, на который введён состав; без него устаревание видно только через неделю)
        WARNINGS.append("pending.%s (GW%s) игнорируется: дедлайн прошёл, API показывает реальный состав. Блок можно удалить из config.json." % (key, pend.get("gw", "?")))
        pend = None
    elif pend and pend.get("squad") and not isinstance(pend.get("gw"), int):
        WARNINGS.append("pending.%s без поля gw — не смогу понять, когда он устарел. Добавь \"gw\": %d (тур, на который введён состав)." % (key, gw_next))
    if pend and pend.get("squad"):
        # трансферы на ближайший тур до дедлайна в API не видны -> берём состав, который ввёл пользователь
        try:
            prev_ids = set(p["element"] for p in (picks_cur or {}).get("picks", []))
            new_squad = []
            for spec in pend["squad"]:
                el = resolve_player(spec, bst)
                e = els[el]
                if el in prev_ids:
                    buy = last_in.get(el, e["now_cost"] - e.get("cost_change_start", 0))
                else:
                    buy = e["now_cost"]  # недавно куплен: цена покупки ≈ текущая
                new_squad.append({"id": el, "pos_slot": len(new_squad) + 1,
                                  "captain": bool(pend.get("captain")) and _norm(spec.split(":")[0]) == _norm(pend.get("captain", "")),
                                  "vice": bool(pend.get("vice")) and _norm(spec.split(":")[0]) == _norm(pend.get("vice", "")),
                                  "buy": buy, "now": e["now_cost"], "sell": sell_price(buy, e["now_cost"])})
            squad = new_squad
            if pend.get("bank") is not None:
                bank = pend["bank"]
            value = sum(x["sell"] for x in squad)
            ft_manual = pend.get("ft")
            source = "manual"
        except ValueError as ex:
            WARNINGS.append("pending.%s: %s — взят состав из API." % (key, ex))
            print("  ! pending.%s: %s" % (key, ex))
    chips = hist.get("chips", [])
    names = {"3xc": "Triple Captain", "bboost": "Bench Boost", "wildcard": "Wildcard", "freehit": "Free Hit"}
    for c in chips:
        c["label"] = names.get(c["name"], c["name"])
    if bank is None and hist.get("current"):
        bank = hist["current"][-1].get("bank", 0)
        value = value or hist["current"][-1].get("value", 0)
    ft_left, ft_before = free_transfers_estimate(tr_by_ev, chips, gw_cur, gw_next, cfg.get("max_free_transfers", 5))
    if ft_manual is not None:
        ft_left = ft_manual
    cur = hist.get("current", [])
    bench_lost = sum(c.get("points_on_bench", 0) for c in cur)
    hits_lost = sum(c.get("event_transfers_cost", 0) for c in cur)
    tr_recent = [t for t in transfers if t["event"] >= max(1, gw_cur - 1)]
    last_event = cur[-1] if cur else {}
    return {
        "key": key, "entry": entry_id,
        "team": info.get("name", ""), "manager": ("%s %s" % (info.get("player_first_name", ""), info.get("player_last_name", ""))).strip(),
        "overall_pts": info.get("summary_overall_points"), "overall_rank": info.get("summary_overall_rank"),
        "region": info.get("player_region_name") or "", "started_event": info.get("started_event"),
        "fav_team": (lambda ft: {"name": ft["name"], "short": ft["short_name"], "code": ft["code"]} if ft else None)(
            next((t for t in bst["teams"] if t["id"] == info.get("favourite_team")), None)),
        "bank": bank, "value": value, "source": source, "squad": squad,
        "ft_estimate": ft_left, "ft_before_moves": ft_before,
        "chips": chips, "bench_lost": bench_lost, "hits_lost": hits_lost,
        "gw_points": [{"gw": c["event"], "pts": c["points"], "bench": c.get("points_on_bench", 0),
                       "hit": c.get("event_transfers_cost", 0), "rank": c.get("overall_rank")} for c in cur],
        "last_gw": {"pts": last_event.get("points"), "bench": last_event.get("points_on_bench"),
                    "transfers": last_event.get("event_transfers"), "hit": last_event.get("event_transfers_cost")},
        "transfers_recent": [{"gw": t["event"], "in": t["element_in"], "out": t["element_out"],
                              "in_cost": t["element_in_cost"], "out_cost": t["element_out_cost"]} for t in tr_recent],
        "transfers_total": len(transfers),
        "tr_per_gw": [c.get("event_transfers", 0) for c in cur],
    }


def load_top(bst, gw_cur, gw_next, cfg):
    n = cfg.get("top_managers", 50)
    st = get("leagues-classic/314/standings/?page_standings=1", optional=True)
    if not st:
        return {"n": 0, "owned": {}, "ins": {}, "outs": {}, "caps": {}, "chips": {}, "managers": []}
    res = st["standings"]["results"][:n]

    def one(m):
        p = get("entry/%d/event/%d/picks/" % (m["entry"], gw_cur), optional=True)
        t = get("entry/%d/transfers/" % m["entry"], optional=True) or []
        return m, p, t

    owned, ins, outs, caps, chips = {}, {}, {}, {}, {}
    managers = []
    with ThreadPoolExecutor(max_workers=4) as ex:
        results = list(ex.map(one, res))
    used = 0
    for m, p, t in results:
        if not p:
            continue
        used += 1
        for x in p["picks"]:
            owned[x["element"]] = owned.get(x["element"], 0) + 1
            if x.get("is_captain"):
                caps[x["element"]] = caps.get(x["element"], 0) + 1
        if p.get("active_chip"):
            chips[p["active_chip"]] = chips.get(p["active_chip"], 0) + 1
        for tr in t:
            if tr["event"] >= gw_cur:
                ins[tr["element_in"]] = ins.get(tr["element_in"], 0) + 1
                outs[tr["element_out"]] = outs.get(tr["element_out"], 0) + 1
        managers.append({"rank": m["rank"], "name": m["entry_name"], "pts": m["total"]})
    return {"n": used, "owned": owned, "ins": ins, "outs": outs, "caps": caps, "chips": chips, "managers": managers}


# ----------------------------------------------------------------------------- рекомендации
def club_ok(team_ids, cap=3):
    cnt = {}
    for t in team_ids:
        cnt[t] = cnt.get(t, 0) + 1
        if cnt[t] > cap:
            return False
    return True


def best_xi(players):
    """players: список dict с pos, xp1. Возвращает (xi, bench, formation, captain, vice)."""
    by = {"GK": [], "DEF": [], "MID": [], "FWD": []}
    for p in players:
        by[p["pos"]].append(p)
    for k in by:
        by[k].sort(key=lambda p: -p["xp1"])
    best = None
    for d in range(3, 6):
        for m in range(2, 6):
            for f in range(1, 4):
                if d + m + f != 10:
                    continue
                if len(by["GK"]) < 1 or len(by["DEF"]) < d or len(by["MID"]) < m or len(by["FWD"]) < f:
                    continue
                xi = by["GK"][:1] + by["DEF"][:d] + by["MID"][:m] + by["FWD"][:f]
                tot = sum(p["xp1"] for p in xi)
                if best is None or tot > best[0]:
                    best = (tot, xi, "%d-%d-%d" % (d, m, f))
    if not best:
        return [], [], "-", None, None
    xi = best[1]
    ids = set(p["id"] for p in xi)
    bench = sorted([p for p in players if p["id"] not in ids], key=lambda p: (p["pos"] != "GK", -p["xp1"]))
    cands = sorted(xi, key=lambda p: -p["xp1"])
    return xi, bench, best[2], cands[0], cands[1] if len(cands) > 1 else None


def load_claude_picks(me, bst, gw_next):
    """Читает claude_picks.json (рекомендация Claude на тур), проверяет и переводит имена в id."""
    path = os.path.join(HERE, "claude_picks.json")
    if not os.path.exists(path):
        return None
    try:
        raw = json.load(open(path, encoding="utf-8"))
    except Exception as ex:
        WARNINGS.append("claude_picks.json не читается: %s" % ex)
        return None
    errors = []
    squad_ids = [x["id"] for x in me["squad"]]
    def res(spec):
        try:
            return resolve_player(spec, bst)
        except ValueError:
            try:
                return resolve_player(str(spec).split(":")[0], bst)
            except ValueError:
                errors.append("не нашёл игрока '%s'" % spec)
                return None
    xi = [res(x) for x in raw.get("xi", [])]
    bench = [res(x) for x in raw.get("bench", [])]
    cap = res(raw["captain"]) if raw.get("captain") else None
    vice = res(raw["vice"]) if raw.get("vice") else None
    xi, bench = [i for i in xi if i], [i for i in bench if i]
    if len(xi) != 11 or len(bench) != 4:
        errors.append("нужно 11 стартёров и 4 запасных (сейчас %d и %d)" % (len(xi), len(bench)))
    if sorted(xi + bench) != sorted(squad_ids):
        errors.append("состав в claude_picks.json не совпадает с текущими 15 игроками (внеси актуальный pending.me или поправь файл)")
    pos = {e["id"]: e["element_type"] for e in bst["elements"]}
    cnt = {t: sum(1 for i in xi if pos.get(i) == t) for t in (1, 2, 3, 4)}
    if cnt[1] != 1 or cnt[2] < 3 or cnt[3] < 2 or cnt[4] < 1:
        errors.append("недопустимая расстановка стартёров (нужно 1 GK, ≥3 DEF, ≥2 MID, ≥1 FWD)")
    for who, i in (("капитан", cap), ("вице", vice)):
        if i and i not in xi:
            errors.append("%s не в стартовом составе" % who)
    notes = {}
    for k, v in (raw.get("notes") or {}).items():
        i = res(k)
        if i:
            notes[str(i)] = v
    if errors:
        for e in errors:
            WARNINGS.append("claude_picks.json: " + e)
    return {"gw": raw.get("gw"), "updated": raw.get("updated"), "status": raw.get("status", ""),
            "summary": raw.get("summary", ""), "formation": raw.get("formation", ""),
            "xi": xi, "bench": bench, "captain": cap, "vice": vice, "notes": notes, "tags": raw.get("tags") or [],
            "errors": errors, "stale": raw.get("gw") != gw_next}


def suggestions(me, rows_by_id, rows, taken, cfg, gw_next):
    squad = []
    for s in me["squad"]:
        r = dict(rows_by_id[s["id"]])
        r["sell"] = s["sell"]
        squad.append(r)
    bank = cfg.get("bank_override") if cfg.get("bank_override") is not None else (me["bank"] or 0)
    ft = cfg.get("free_transfers_override") if cfg.get("free_transfers_override") is not None else me["ft_estimate"]
    hit = cfg.get("hit_cost", 4)
    mine = set(s["id"] for s in squad)

    def cands_for(out):
        res = []
        for r in rows:
            if r["pos"] != out["pos"] or r["id"] in mine or r["id"] in taken or r["avail"] < 0.5:
                continue
            if r["mfrac"] < cfg.get("min_minutes_frac", 0.25) and r["pts"] < 20:
                continue
            res.append(r)
        return res

    options = []  # (out, cand, gain, cost_delta)
    for out in squad:
        cs = cands_for(out)
        cs.sort(key=lambda c: -c["xp5"])
        for c in cs[:40]:
            gain = c["xp5"] - out["xp5"]
            if gain <= 0.3:
                continue
            options.append({"out": out["id"], "inn": c["id"], "gain": round(gain, 2),
                            "delta": c["price"] - out["sell"], "dteam_in": c["team"], "dteam_out": out["team"]})
    # одиночные
    single = []
    for o in options:
        if o["delta"] > bank:
            continue
        teams_after = [s["team"] for s in squad if s["id"] != o["out"]] + [o["dteam_in"]]
        if not club_ok(teams_after):
            continue
        net = o["gain"] - (0 if ft >= 1 else hit)
        single.append(dict(o, net=round(net, 2), bank_after=bank - o["delta"], hit=(0 if ft >= 1 else hit)))
    single.sort(key=lambda x: -x["net"])
    # парные
    top_opts = {}
    for o in options:
        top_opts.setdefault(o["out"], []).append(o)
    for k in top_opts:
        top_opts[k].sort(key=lambda x: -x["gain"])
        top_opts[k] = top_opts[k][:12]
    flat = [o for v in top_opts.values() for o in v]
    pairs = []
    for a, b in itertools.combinations(flat, 2):
        if a["out"] == b["out"] or a["inn"] == b["inn"]:
            continue
        if a["delta"] + b["delta"] > bank:
            continue
        outs = {a["out"], b["out"]}
        teams_after = [s["team"] for s in squad if s["id"] not in outs] + [a["dteam_in"], b["dteam_in"]]
        if not club_ok(teams_after):
            continue
        hits = max(0, 2 - ft) * hit
        net = a["gain"] + b["gain"] - hits
        pairs.append({"a": a, "b": b, "gain": round(a["gain"] + b["gain"], 2), "net": round(net, 2),
                      "hit": hits, "bank_after": bank - a["delta"] - b["delta"]})
    pairs.sort(key=lambda x: -x["net"])
    # дедуп пар по набору out/in
    seen, uniq = set(), []
    for p in pairs:
        key = (frozenset([p["a"]["out"], p["b"]["out"]]), frozenset([p["a"]["inn"], p["b"]["inn"]]))
        if key in seen:
            continue
        seen.add(key)
        uniq.append(p)
        if len(uniq) >= 40:
            break
    xi, bench, form, cap, vice = best_xi(squad)
    # "слабые звенья" — кого продавать
    bench_ids = set(p["id"] for p in bench)
    weak_pool = squad if cfg.get("weak_include_bench") else [r for r in squad if r["id"] not in bench_ids]
    weak = sorted(weak_pool, key=lambda r: r["xp5"])[:5]
    return {
        "bank": bank, "ft": ft,
        "single": single[:40], "double": uniq,
        "lineup": {"formation": form, "xi": [p["id"] for p in xi], "bench": [p["id"] for p in bench],
                   "captain": cap["id"] if cap else None, "vice": vice["id"] if vice else None,
                   "xp_total": round(sum(p["xp1"] for p in xi), 1)},
        "weak": [w["id"] for w in weak],
    }


def insurance(me, rows_by_id, rows, taken, cfg):
    """Для каждого стартера: 3 запасных варианта на случай травмы (в пределах цены продажи + банк)."""
    bank = me["bank"] or 0
    mine = set(s["id"] for s in me["squad"])
    out = {}
    for s in me["squad"]:
        r = rows_by_id[s["id"]]
        cs = [c for c in rows if c["pos"] == r["pos"] and c["id"] not in mine and c["id"] not in taken
              and c["avail"] >= 0.5 and c["price"] <= s["sell"] + bank and c["mfrac"] >= cfg.get("min_minutes_frac", 0.25)]
        cs.sort(key=lambda c: -c["xp5"])
        out[str(s["id"])] = [c["id"] for c in cs[:10]]
    return out


# ----------------------------------------------------------------------------- снимки и изменения
def save_snapshot(con, ts, gw, rows, pool, top, managers):
    """Один снимок в сутки (UTC): повторный запуск в тот же день ОБНОВЛЯЕТ его, а не плодит новые."""
    day = ts[:10]
    cur = con.cursor()
    row = cur.execute("SELECT id FROM snapshots WHERE day=?", (day,)).fetchone()
    if row:
        sid = row[0]
        for t in ("player_snap", "top_owned", "manager_snap"):
            cur.execute("DELETE FROM %s WHERE snap_id=?" % t, (sid,))
        cur.execute("UPDATE snapshots SET ts=?, gw=? WHERE id=?", (ts, gw, sid))
    else:
        cur.execute("INSERT INTO snapshots(ts, gw, day) VALUES(?,?,?)", (ts, gw, day))
        sid = cur.lastrowid
    cur.executemany(
        "INSERT INTO player_snap VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        [(sid, r["id"], r["price"], r["own"], r["form"], r["ppg"], r["pts"], r["minutes"], r["status"], r["news"],
          r["chance"], r["ep_next"], r["tin"], r["tout"], 1 if r["id"] in pool else 0, r["score"], r["xp5"]) for r in rows])
    cur.executemany("INSERT INTO top_owned VALUES(?,?,?,?)",
                    [(sid, el, c, top["n"]) for el, c in top["owned"].items()])
    for k, m in managers.items():
        cur.execute("INSERT INTO manager_snap VALUES(?,?,?)", (sid, k, json.dumps(m, ensure_ascii=False)))
    con.commit()
    return sid, bool(row)


def prev_snapshots(con, sid, ts):
    cur = con.cursor()
    prev = cur.execute("SELECT id, ts FROM snapshots WHERE id<? ORDER BY id DESC LIMIT 1", (sid,)).fetchone()
    t = dt.datetime.fromisoformat(ts)
    target = (t - dt.timedelta(days=6, hours=12)).isoformat()
    week = cur.execute("SELECT id, ts FROM snapshots WHERE id<? AND ts<=? ORDER BY id DESC LIMIT 1", (sid, target)).fetchone()
    if not week:
        week = cur.execute("SELECT id, ts FROM snapshots WHERE id<? ORDER BY id ASC LIMIT 1", (sid,)).fetchone()
    return prev, week


def diff_changes(con, sid, ts, rows_by_id, pool):
    cur = con.cursor()
    prev, week = prev_snapshots(con, sid, ts)
    ch = {"has_prev": bool(prev), "prev_ts": prev[1] if prev else None, "week_ts": week[1] if week else None,
          "price": [], "status": [], "new_in_pool": [], "left_pool": [], "own_up": [], "own_down": [], "form_up": []}
    trend = {}
    if not prev:
        return ch, trend

    def load(snap):
        d = {}
        for row in cur.execute("SELECT element, price, own, form, status, news, in_pool, score FROM player_snap WHERE snap_id=?", (snap,)):
            d[row[0]] = row
        return d

    p = load(prev[0])
    w = load(week[0]) if week else {}
    for el, r in rows_by_id.items():
        po = p.get(el)
        wo = w.get(el)
        t = {}
        if wo:
            t["d_price_w"] = r["price"] - wo[1]
            t["d_own_w"] = round(r["own"] - wo[2], 2)
            t["d_form_w"] = round(r["form"] - wo[3], 1)
            t["d_score_w"] = round(r["score"] - (wo[7] or 0), 1)
        if po:
            t["d_price_d"] = r["price"] - po[1]
            if r["price"] != po[1]:
                ch["price"].append({"id": el, "from": po[1], "to": r["price"]})
            if (po[4] != r["status"]) or ((po[5] or "") != r["news"]):
                if r["news"] or po[5]:
                    ch["status"].append({"id": el, "from": po[4], "to": r["status"], "news": r["news"]})
            inp = el in pool
            if inp and not po[6]:
                ch["new_in_pool"].append(el)
            if not inp and po[6]:
                ch["left_pool"].append(el)
        trend[el] = t
    ups = sorted([(trend[e].get("d_own_w", 0), e) for e in trend if "d_own_w" in trend[e]], reverse=True)
    ch["own_up"] = [{"id": e, "d": d} for d, e in ups[:10] if d > 0]
    ch["own_down"] = [{"id": e, "d": d} for d, e in ups[::-1][:10] if d < 0]
    fu = sorted([(trend[e].get("d_form_w", 0), e) for e in trend if "d_form_w" in trend[e]], reverse=True)
    ch["form_up"] = [{"id": e, "d": d} for d, e in fu[:10] if d > 0]
    return ch, trend


def friend_moves(con, sid, managers):
    """Что друзья продали/купили с прошлого снимка (по сохранённым составам)."""
    cur = con.cursor()
    prev = cur.execute("SELECT id FROM snapshots WHERE id<? ORDER BY id DESC LIMIT 1", (sid,)).fetchone()
    res = {}
    if not prev:
        return res
    for k, m in managers.items():
        if k == "me":
            continue
        row = cur.execute("SELECT json FROM manager_snap WHERE snap_id=? AND key=?", (prev[0], k)).fetchone()
        if not row:
            continue
        old = set(x["id"] for x in json.loads(row[0]).get("squad", []))
        new = set(x["id"] for x in m["squad"])
        res[k] = {"sold": sorted(old - new), "bought": sorted(new - old)}
    return res


def top_owned_change(con, sid, top):
    cur = con.cursor()
    prev = cur.execute("SELECT id FROM snapshots WHERE id<? ORDER BY id DESC LIMIT 1", (sid,)).fetchone()
    if not prev:
        return {}
    d = {}
    old = dict(cur.execute("SELECT element, cnt FROM top_owned WHERE snap_id=?", (prev[0],)).fetchall())
    for el, c in top["owned"].items():
        d[el] = c - old.get(el, 0)
    for el, c in old.items():
        if el not in top["owned"]:
            d[el] = -c
    return d


def store_history(con, pool, bst, workers=4, fixtures=None):
    """element-summary для игроков из пула -> player_gw (последние туры, форма по турам)."""
    fx_by_id = {}

    def one(el):
        return el, get("element-summary/%d/" % el, optional=True)

    with ThreadPoolExecutor(max_workers=workers) as ex:
        res = list(ex.map(one, sorted(pool)))
    cur = con.cursor()
    n = 0
    for el, js in res:
        if not js:
            continue
        for h in js.get("history", []):
            cur.execute("INSERT OR REPLACE INTO player_gw VALUES(?,?,?,?,?,?,?)",
                        (el, h["round"], h["total_points"], h["minutes"], fnum(h.get("expected_goal_involvements")),
                         h.get("opponent_team", 0), 1 if h.get("was_home") else 0))
            n += 1
    con.commit()
    seasons.store(con, res)             # history_past: итоги прошлых сезонов (без лишних запросов)
    if fixtures:
        probs.store_matches(con, res, fixtures)   # по матчу: минуты, старт, xG, xA, xGC, DC — для CS %/DC %/голов
    return n


def past_fdr(fixtures):
    """(team_id, event, opp_id) -> сложность матча для этой команды (для сыгранных туров)."""
    out = {}
    for f in fixtures:
        ev = f.get("event")
        if ev is None:
            continue
        out[(f["team_h"], ev, f["team_a"])] = f.get("team_h_difficulty")
        out[(f["team_a"], ev, f["team_h"])] = f.get("team_a_difficulty")
    return out


def gw_series(con, el, team=None, fdr=None, tshort=None, upto=8):
    """Последние upto туров: очки/минуты за тур + каждый матч (соперник, дом/выезд, сложность, очки)."""
    cur = con.cursor()
    gws = [g for (g,) in cur.execute("SELECT DISTINCT gw FROM player_gw WHERE element=? ORDER BY gw DESC LIMIT ?",
                                     (el, upto)).fetchall()]
    if not gws:
        return []
    rows = cur.execute("SELECT gw, pts, minutes, opp, home FROM player_gw WHERE element=? AND gw>=? ORDER BY gw",
                       (el, min(gws))).fetchall()
    out = {}
    for g, p, m, o, h in rows:
        s = out.setdefault(g, {"gw": g, "pts": 0, "min": 0, "m": []})
        s["pts"] += p or 0
        s["min"] += m or 0
        s["m"].append({"opp": (tshort or {}).get(o, "?"), "h": bool(h), "pts": p or 0, "min": m or 0,
                       "fdr": (fdr or {}).get((team, g, o))})
    return [out[g] for g in sorted(out)]


# ----------------------------------------------------------------------------- вывод
def money(x):
    return "%.1f" % (x / 10.0) if x is not None else "-"


def write_brief(path, data, rows_by_id):
    meta = data["meta"]
    L = []
    P = lambda s="": L.append(s)
    nm = lambda i: "%s (%s)" % (rows_by_id[i]["name"], rows_by_id[i]["tname"]) if i in rows_by_id else str(i)
    rivals_txt = "/".join(v for k, v in (data.get("league_names") or {}).items() if k != "me") or "соперников"
    P("# FPL BRIEF для Claude — %s" % meta["generated"])
    P()
    P("Ближайший тур: GW%s, дедлайн %s (UTC). Последний сыгранный: GW%s." % (meta["gw_next"], meta["deadline"], meta["gw_cur"]))
    P("Задача Claude: принять окончательное решение — кого продать/купить, капитан, состав; ПЕРЕД этим проверить новости (травмы, пресс-конференции, вероятные составы), чего нет в API.")
    P("Правило лиги: игроки НЕ повторяются между составами. Помечено: ЗАНЯТ — у соперников (%s)." % rivals_txt)
    P()
    me = data["me"]
    P("## Мой состав (Женя) — банк £%s, свободных трансферов: %s (оценка), стоимость £%s" % (
        money(data["sugg"]["bank"]), data["sugg"]["ft"], money(me["value"])))
    for s in me["squad"]:
        r = rows_by_id[s["id"]]
        flag = " ⚠ %s" % r["news"] if r["news"] else ""
        mark = " (C)" if s["captain"] else (" (V)" if s["vice"] else "")
        P("- %s %s%s | цена %s, продажа %s | форма %.1f, ppg %.1f, xP1 %.1f, xP5 %.1f | календарь: %s%s" % (
            r["pos"], nm(s["id"]), mark, money(s["now"]), money(s["sell"]), r["form"], r["ppg"], r["xp1"], r["xp5"],
            " ".join("%s%s%d" % (f["opp"], "H" if f["h"] else "A", f["fdr"]) for f in r["fix"]), flag))
    lu = data["sugg"]["lineup"]
    P()
    P("Автосостав (по xP1): %s | капитан %s, вице %s | сумма xP %.1f" % (
        lu["formation"], nm(lu["captain"]) if lu["captain"] else "-", nm(lu["vice"]) if lu["vice"] else "-", lu["xp_total"]))
    P()
    # v1.19: шансы моих игроков на ближайший тур (по данным FPL; это модель, не новости)
    byid = {r["id"]: r for r in data["players"]}
    P("## Шансы моих игроков на GW%s (CS %% · DC %% · гол %% · ассист %% · стандарты)" % meta["gw_next"])
    for s_ in data["me"]["squad"]:
        r = byid.get(s_["id"])
        q = ((r or {}).get("pr") or [{}])[0]
        if not r or not q or q.get("blank"):
            continue
        sp = ", ".join("%s №%s" % ({"pen": "пен", "fk": "штр", "cor": "угл"}[k], v) for k, v in sorted((r.get("sp") or {}).items(), key=lambda x: x[1]))
        P("- %s (%s %s): CS %s · DC %s · гол %s · ассист %s%s" % (r["name"], r["tname"], r["pos"],
          q.get("cs") if q.get("cs") is not None else "—", q.get("dc") if q.get("dc") is not None else "—",
          q.get("g"), q.get("a"), (" · " + sp) if sp else ""))
    P()
    P("## Друзья")
    for k in [k_ for k_ in data["league"] if k_ != "me"]:
        m = data["league"].get(k)
        if not m:
            continue
        P("### %s — %s очк., банк £%s, FT≈%s, хитов потеряно %s очк., очков на скамейке за сезон %s, фишки: %s" % (
            m["name"], m["overall_pts"], money(m["bank"]), m["ft_estimate"], m["hits_lost"], m["bench_lost"],
            ", ".join("%s(GW%s)" % (c.get("label", c["name"]), c["event"]) for c in m["chips"]) or "нет"))
        P("Состав: " + ", ".join(nm(s["id"]) + ("(C)" if s["captain"] else "") for s in m["squad"]))
        tr = m["transfers_recent"]
        if tr:
            P("Последние трансферы: " + "; ".join("GW%s: %s → %s" % (t["gw"], nm(t["out"]), nm(t["in"])) for t in tr))
    cl = data.get("claude_lineup")
    if cl:
        P()
        P("## Рекомендация Claude на GW%s (claude_picks.json, обновлено %s)%s" % (cl["gw"], cl["updated"], " — УСТАРЕЛА, обнови" if cl["stale"] else ""))
        P("Старт: %s | запас: %s | капитан %s, вице %s | %s" % (", ".join(nm(i) for i in cl["xi"]), ", ".join(nm(i) for i in cl["bench"]), nm(cl["captain"]) if cl["captain"] else "-", nm(cl["vice"]) if cl["vice"] else "-", cl["status"]))
        for e in cl["errors"]:
            P("⚠ " + e)
    if data.get("watch"):
        P()
        P("## Скаут-лист (под наблюдением)")
        me_name = (data.get("league_names") or {}).get("me") or "пользователь"
        if any(w.get("source") == "user" for w in data["watch"]):
            P("Пометка «ДОБАВИЛ %s» — игрок добавлен вручную кнопкой в дашборде: оцени его (новости, бюджет, занят ли) и дай комментарий." % me_name.upper())
        for w in sorted(data["watch"], key=lambda x: x["prio"]):
            r = rows_by_id.get(w["id"])
            if not r:
                continue
            P("- [P%s]%s %s | £%s | форма %.1f, xP5 %.1f | %s%s | %s → %s" % (
                w["prio"], (" [ДОБАВИЛ %s%s]" % (me_name.upper(), (" " + w["added"]) if w.get("added") else "")) if w.get("source") == "user" else "",
                nm(w["id"]), money(r["price"]), r["form"], r["xp5"],
                ("ЗАНЯТ: %s" % r["taken_by"]) if r.get("taken_by") else "свободен",
                (" ⚠ %s" % r["news"]) if r["news"] else "", w["note"], w["trigger"]))
    if data.get("blacklist"):
        P()
        P("Чёрный список (не рекомендовать): " + ", ".join(nm(i) for i in data["blacklist"]))
    rel = [e for e in data.get("bl_track", []) if e["status"] == "released" and not e["pin"]]
    if rel:
        P("★ ОСВОБОДИЛИСЬ из чёрного списка (друг больше не держит — теперь можно рекомендовать): " + ", ".join(
            "%s (был у %s)" % (nm(e["id"]), data["league_names"].get(e["owner"], e["owner"])) for e in rel))
    unv = [e for e in data.get("bl_track", []) if e["status"] == "unverified"]
    if unv:
        P("Не подтверждены (ходы друзей на новый тур не видны до дедлайна): " + ", ".join(nm(e["id"]) for e in unv))
    for k, mv in (data.get("friend_moves") or {}).items():
        if mv["sold"] or mv["bought"]:
            P("Ходы %s с прошлого снимка: продал %s; купил %s" % (data["league_names"].get(k, k),
              ", ".join(nm(i) for i in mv["sold"]) or "—", ", ".join(nm(i) for i in mv["bought"]) or "—"))
    if data["conflicts"]:
        P()
        P("⚠ ДУБЛИ в составах: " + ", ".join(nm(c) for c in data["conflicts"]))
    P()
    P("## Предложения расчёта (проверь новостями!)")
    P("Одиночные ходы (прирост xP за 5 туров, net — с учётом хита):")
    for s in data["sugg"]["single"][:8]:
        P("- %s → %s | +%.1f xP5 (net %.1f) | банк после £%s | занят: %s" % (
            nm(s["out"]), nm(s["inn"]), s["gain"], s["net"], money(s["bank_after"]), "нет"))
    P("Двойные ходы:")
    for p in data["sugg"]["double"][:5]:
        a, b = p["a"], p["b"]
        P("- %s → %s + %s → %s | +%.1f xP5 (net %.1f, хит %s) | банк после £%s" % (
            nm(a["out"]), nm(a["inn"]), nm(b["out"]), nm(b["inn"]), p["gain"], p["net"], p["hit"], money(p["bank_after"])))
    P("Слабые звенья: " + ", ".join(nm(i) for i in data["sugg"]["weak"]))
    P()
    P("## Топ по позициям (только свободные игроки, по score)")
    for pos in ("GK", "DEF", "MID", "FWD"):
        P("### " + pos)
        lst = [r for r in data["players"] if r["pos"] == pos and not r["taken_by"] and not r["mine"] and r["score"] > 0][:12]
        for r in lst:
            P("- %s £%s | score %.0f | форма %.1f, ppg %.1f, xGI90 %.2f, DC90 %.1f | топ%d: %s/%s | own %.1f%% | xP5 %.1f | %s%s" % (
                nm(r["id"]), money(r["price"]), r["score"], r["form"], r["ppg"], r["xgi90"], r["dc90"], data["top"]["n"],
                r["top_cnt"], data["top"]["n"], r["own"], r["xp5"],
                " ".join("%s%s%d" % (f["opp"], "H" if f["h"] else "A", f["fdr"]) for f in r["fix"]),
                (" ⚠ " + r["news"]) if r["news"] else ""))
    P()
    P("## Топ-%d мира: движения (трансферы с GW%s)" % (data["top"]["n"], meta["gw_cur"]))
    P("Купили: " + ", ".join("%s×%d" % (nm(i), c) for i, c in data["top"]["ins_list"][:12]))
    P("Продали: " + ", ".join("%s×%d" % (nm(i), c) for i, c in data["top"]["outs_list"][:12]))
    P("Капитаны: " + ", ".join("%s×%d" % (nm(i), c) for i, c in data["top"]["caps_list"][:5]))
    ch = data["changes"]
    P()
    P("## Изменения с прошлого снимка (%s)" % (ch.get("prev_ts") or "снимка ещё нет"))
    if ch["price"]:
        P("Цены: " + ", ".join("%s %s→%s" % (nm(c["id"]), money(c["from"]), money(c["to"])) for c in ch["price"][:20]))
    if ch["status"]:
        P("Статусы/новости: " + "; ".join("%s: %s %s" % (nm(c["id"]), c["to"], c["news"]) for c in ch["status"][:20]))
    if ch["new_in_pool"]:
        P("Новые в топ-списках: " + ", ".join(nm(i) for i in ch["new_in_pool"][:20]))
    if ch["left_pool"]:
        P("Вылетели из топ-списков: " + ", ".join(nm(i) for i in ch["left_pool"][:20]))
    if ch["own_up"]:
        P("Растёт владение за неделю: " + ", ".join("%s +%.1f%%" % (nm(c["id"]), c["d"]) for c in ch["own_up"]))
    P()
    P("## Травмы/сомнения среди моих и топ-кандидатов")
    for r in data["players"]:
        if r["news"] and (r["mine"] or r["score"] >= 40):
            P("- %s: %s (шанс %s)" % (nm(r["id"]), r["news"], r["chance"]))
    P()
    L.extend(analytics.brief_lines(data, nm, data["league_names"]))
    P()
    ev_ = data.get("events") or {}
    if ev_.get("price") or ev_.get("status"):
        P("## События за 48 ч (журнал: цены и статусы, время UTC)")
        for e_ in ev_.get("price", [])[:15]:
            P("- %s цена %s → %s (%s) · владение %.1f%%, чистый поток %+d" % (nm(e_["id"]), money(e_["old"]), money(e_["new"]), e_["ts"][5:16].replace("T", " "), e_["own"], e_["net"]))
        for e_ in ev_.get("status", [])[:20]:
            P("- %s статус %s→%s, шанс %s→%s (%s): %s" % (nm(e_["id"]), e_["old_status"], e_["new_status"], e_["old_chance"], e_["new_chance"], e_["ts"][5:16].replace("T", " "), (e_["news"] or "")[:90]))
        P()
    P("## Точность прогноза (бэктест)")
    for l_ in backtest.brief_lines(data.get("backtest")):
        P(l_)
    P()
    P("## Что должен сделать Claude")
    P("1. Проверить новости (пресс-конференции, травмы, ротация, вероятные составы) по моим игрокам и кандидатам.")
    P("2. Сверить кандидатов со списком ЗАНЯТ (%s) и с новыми" % rivals_txt + " ходами друзей.")
    P("3. Выбрать ходы с учётом бюджета/FT и дать финальный состав, капитана, вице.")
    P("4. Напомнить чипы и фикстуры (BB/WC/FH), сохранить решения в references/league-state.md.")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(L))


DESIGNS = {1: "dashboard_template.html", 2: "dashboard_template_v2.html"}  # 1 — классический, 2 — светлый (по умолчанию)


def design_of(cfg):
    try:
        d = int(cfg.get("design", 2))
    except (TypeError, ValueError):
        d = 2
    return d if d in DESIGNS else 2


def write_dashboards(out_dir, data, cfg):
    """Пишет оба дизайна (dashboard_v1.html, dashboard_v2.html) и dashboard.html — выбранный в config.json → design."""
    with open(os.path.join(HERE, "dashboard_core.js"), "r", encoding="utf-8") as f:
        core = f.read()
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    pages = {}
    for num, name in DESIGNS.items():
        with open(os.path.join(HERE, name), "r", encoding="utf-8") as f:
            tpl = f.read()
        html = tpl.replace("/*__CORE__*/", core, 1).replace("/*__DATA__*/null", payload, 1)
        pages[num] = html
        with open(os.path.join(out_dir, "dashboard_v%d.html" % num), "w", encoding="utf-8") as f:
            f.write(html)
    with open(os.path.join(out_dir, "dashboard.html"), "w", encoding="utf-8") as f:
        f.write(pages[design_of(cfg)])


def save_config_history(cfg_path):
    """Если config.json изменился — кладём копию в data/config_history (храним 5 последних): можно откатиться."""
    try:
        d = os.path.join(_data_dir(), "config_history")
        os.makedirs(d, exist_ok=True)
        with open(cfg_path, "rb") as f:
            cur = f.read()
        files = sorted(x for x in os.listdir(d) if x.startswith("config_") and x.endswith(".json"))
        if files:
            with open(os.path.join(d, files[-1]), "rb") as f:
                if f.read() == cur:
                    return
        name = "config_%s.json" % dt.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        with open(os.path.join(d, name), "wb") as f:
            f.write(cur)
        _trim(d, "config_", ".json", 5)
    except Exception:
        pass


def write_run_log(out_dir, line):
    """out/run.log — одна строка на запуск (храним последние 300)."""
    try:
        fp = os.path.join(out_dir, "run.log")
        lines = []
        if os.path.exists(fp):
            with open(fp, "r", encoding="utf-8") as f:
                lines = f.read().splitlines()
        lines.append(line)
        with open(fp, "w", encoding="utf-8") as f:
            f.write("\n".join(lines[-300:]) + "\n")
    except Exception:
        pass


# ----------------------------------------------------------------------------- главный поток
def main():
    global OFFLINE, FORCE
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true", help="использовать mock/ вместо сети")
    ap.add_argument("--no-history", action="store_true")
    ap.add_argument("--refresh", action="store_true", help="игнорировать кэш и перекачать всё заново")
    ap.add_argument("--no-open", action="store_true", help="не открывать дашборд в браузере после расчёта")
    ap.add_argument("--serve", action="store_true", help="после расчёта держать дашборд на 127.0.0.1 с настройками (пока открыто окно)")
    ap.add_argument("--config", default=os.path.join(HERE, "config.json"))
    args = ap.parse_args()
    OFFLINE = args.offline
    FORCE = args.refresh
    with open(args.config, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    FRIENDS.update(cfg["entries"].values())
    if not OFFLINE:
        prune_cache()
    OUT_DIR = os.environ.get("FPL_OUT_DIR") or os.path.join(HERE, "out")
    os.makedirs(OUT_DIR, exist_ok=True)

    print("1/6 Загружаю bootstrap-static и календарь…")
    bst = get("bootstrap-static/")
    fixtures = get("fixtures/")
    events = bst["events"]
    cur_ev = next((e for e in events if e.get("is_current")), None)
    nxt_ev = next((e for e in events if e.get("is_next")), None)
    gw_next = nxt_ev["id"] if nxt_ev else (cur_ev["id"] + 1 if cur_ev else 1)
    gw_cur = cur_ev["id"] if cur_ev else gw_next - 1
    deadline = (nxt_ev or {}).get("deadline_time", "")

    print("2/6 Считаю рейтинги (GW%d → ближайший тур GW%d)…" % (gw_cur, gw_next))
    prior90 = seasons.load_prior_map(os.path.join(_data_dir(), "fpl.db"))
    rows, teams = compute_players(bst, fixtures, cfg, gw_cur, gw_next, prior90)
    rows_by_id = {r["id"]: r for r in rows}

    print("3/6 Загружаю составы: %s…" % ", ".join(cfg["names"].get(k, k) for k in cfg["entries"]))
    managers = {}
    for key, eid in cfg["entries"].items():
        managers[key] = load_manager(key, eid, bst, gw_cur, gw_next, cfg)
        managers[key]["name"] = cfg["names"].get(key, key)
    taken = {}
    for k, m in managers.items():
        if k == "me":
            continue
        for s in m["squad"]:
            taken[s["id"]] = managers[k]["name"]
    mine_ids = set(s["id"] for s in managers["me"]["squad"])
    conflicts = [i for i in mine_ids if i in taken]
    # чёрный список (config.json -> blacklist): не рекомендуем, но статистику собираем.
    # Запись: "Cherki:MCI@stas" (владелец после @ — для слежения: когда он продаст, игрок освободится).
    holdings = {k: set(x["id"] for x in m["squad"]) for k, m in managers.items() if k != "me"}
    verified = {k: managers[k]["source"] in ("picks_next", "manual") for k in holdings}
    alias = {}
    for k in holdings:
        alias[k.lower()] = k
        alias[cfg["names"].get(k, k).lower()] = k
    bl_track = []
    for entry in cfg.get("blacklist") or []:
        if isinstance(entry, dict):
            spec, owner, pin = entry.get("player", ""), entry.get("owner"), bool(entry.get("pin"))
        else:
            spec, _, owner = str(entry).partition("@")
            owner, pin = (owner or None), False
        try:
            el = resolve_player(spec, bst)
        except ValueError as ex:
            print("  ! blacklist:", ex)
            continue
        if el in mine_ids:
            continue
        okey = alias.get((owner or "").strip().lower())
        holder = next((k for k in holdings if el in holdings[k]), None)
        if holder:
            status, okey = "held", holder
        elif okey:
            status = "released" if verified[okey] else "unverified"
        else:
            status = "manual"
        bl_track.append({"id": el, "owner": okey, "status": status, "pin": pin})
        if status != "released" or pin:
            taken.setdefault(el, "чёрный список")
    bl_ids = [e["id"] for e in bl_track if e["status"] != "released" or e["pin"]]
    for e in bl_track:
        if e["status"] == "released" and not e["pin"]:
            print("  ★ %s больше не у %s — можно убрать из чёрного списка (теперь рекомендуется)" % (
                rows_by_id[e["id"]]["name"], cfg["names"].get(e["owner"], e["owner"])))

    checklist = []
    for k, m in managers.items():
        nm_ = cfg["names"].get(k, k)
        if m["source"] == "manual":
            checklist.append({"k": k, "name": nm_, "status": "ok", "text": "состав введён вручную (config.json → pending)"})
        elif m["source"] == "picks_next":
            checklist.append({"k": k, "name": nm_, "status": "ok", "text": "из API: дедлайн прошёл, состав актуален"})
        else:
            checklist.append({"k": k, "name": nm_, "status": "warn",
                              "text": "из API на дедлайн прошлого тура — ходы на ближайший тур не видны. Скинь Claude скрин состава (или внеси в pending)."})
    league_std = get("leagues-classic/%s/standings/" % cfg["league_id"], optional=True) if cfg.get("league_id") else None

    print("4/6 Смотрю топ-%d мира (составы и трансферы лидеров)…" % cfg.get("top_managers", 50))
    top = load_top(bst, gw_cur, gw_next, cfg)

    friends_ids = set(taken.keys())
    top_ids = set(top["owned"].keys())
    pool = pool_ids(rows, cfg, mine_ids | friends_ids | top_ids)

    print("5/6 Сохраняю снимок в базу и считаю изменения…")
    ts = dt.datetime.utcnow().replace(microsecond=0).isoformat()
    con = db_open()
    probs.ensure_schema(con)
    backtest.ensure_schema(con)
    eventlog.ensure_schema(con)
    seasons.ensure_schema(con)
    sid, updated = save_snapshot(con, ts, gw_cur, rows, pool, top, managers)
    print("   снимок за %s: %s" % (ts[:10], "обновлён (один на день)" if updated else "создан"))
    # «широкий рынок»: все, кто реально играет (>= wide_min_minutes за сезон), + все отслеживаемые.
    # Для них качаем историю по турам и показываем в поиске/вкладке «Игроки» (рекомендации по-прежнему из пула).
    wide_min = cfg.get("wide_min_minutes", 90)
    watch_early = set()
    for w in cfg.get("watchlist") or []:
        spec = w if isinstance(w, str) else w.get("player", "")
        if isinstance(w, dict) and isinstance(w.get("fpl_id"), int):
            watch_early.add(w["fpl_id"])
            continue
        for s_ in (spec, spec.split(":")[0]):
            try:
                watch_early.add(resolve_player(s_, bst))
                break
            except ValueError:
                pass
    wide_ids = (set(pool) | mine_ids | friends_ids | watch_early | set(e["id"] for e in bl_track)
                | {r["id"] for r in rows if r["minutes"] >= wide_min})
    if not args.no_history:
        print("   …качаю историю игроков по турам (%d игроков: пул %d + остальные играющие)" % (len(wide_ids), len(pool)))
        store_history(con, wide_ids, bst, fixtures=fixtures)
    try:
        n_pe, n_se = eventlog.log_changes(con, ts, bst)
        since = (dt.datetime.utcnow() - dt.timedelta(hours=48)).replace(microsecond=0).isoformat()
        events = eventlog.recent(con, since)
        print("   журнал событий: смен цены %d, смен статуса %d" % (n_pe, n_se))
    except Exception as ex:
        events = {"price": [], "status": []}
        WARNINGS.append("Журнал событий не записан: %s" % ex)
    # журнал честных прогнозов (последний до дедлайна) + ретро-оценка точности
    backtest.log_forecast(con, sid, ts, gw_next, rows, gw_cur)
    fin_gw = max([e["id"] for e in bst["events"] if e.get("finished")] or [0])
    try:
        bt = backtest.build(con, bst, fixtures, fin_gw, cfg.get("prior_k", 4))
    except Exception as ex:          # бэктест — вспомогательный, не должен ронять расчёт
        bt = {"ok": False, "note": "Бэктест не посчитан: %s" % ex}
        WARNINGS.append(bt["note"])
    changes, trend = diff_changes(con, sid, ts, rows_by_id, pool)
    # во вкладке «Изменения» бывают игроки вне пула — им тоже нужны имена (иначе дашборд покажет #id)
    chg_ids = set()
    for v_ in changes.values():
        if isinstance(v_, list):
            for x in v_:
                chg_ids.add(x.get("id") if isinstance(x, dict) else x)
    top_delta = top_owned_change(con, sid, top)
    f_moves = friend_moves(con, sid, managers)

    print("6/6 Рекомендации и отчёты…")
    sugg = suggestions(managers["me"], rows_by_id, rows, taken, cfg, gw_next)
    insur = insurance(managers["me"], rows_by_id, rows, taken, cfg)

    lg = []
    if league_std:
        for r in league_std["standings"]["results"]:
            lg.append({"entry": r["entry"], "name": r["entry_name"], "manager": r["player_name"], "total": r["total"],
                       "rank": r["rank"], "event_total": r["event_total"]})
    ctx = {"bst": bst, "fixtures": fixtures, "rows": rows, "R": rows_by_id, "managers": managers, "taken": taken,
           "cfg": cfg, "gw_cur": gw_cur, "gw_next": gw_next, "sugg": sugg, "mine_ids": mine_ids, "con": con,
           "league_table": lg, "verified": verified}
    ana = analytics.build(ctx)
    ana["warnings"] = WARNINGS + ana.get("warnings", [])

    def _ids(o, acc):
        if isinstance(o, dict):
            for k, v in o.items():
                if k in ("id", "out", "in", "captain", "vice") and isinstance(v, int):
                    acc.add(v)
                elif k == "moves":
                    for pair in v:
                        acc.update(pair if isinstance(pair, (list, tuple)) else [])
                else:
                    _ids(v, acc)
        elif isinstance(o, (list, tuple)):
            for v in o:
                _ids(v, acc)
        return acc

    extra = set()
    for m_ in sugg["single"]:
        extra.update([m_["out"], m_["inn"]])
    for p_ in sugg["double"]:
        extra.update([p_["a"]["out"], p_["a"]["inn"], p_["b"]["out"], p_["b"]["inn"]])
    for v_ in insur.values():
        extra.update(v_)
    extra |= _ids(ana, set())
    show_ids = set(pool) | extra | set(e["id"] for e in bl_track) | set(i for v_ in f_moves.values() for i in v_["sold"] + v_["bought"])
    # v1.19: сила команд, CS %/xG по турам, вероятности игроков, владение за 1/3/7 дней
    t_str, lg_avg, t_src = probs.team_strength(con, teams, fixtures)
    t_fix = probs.team_fixtures(t_str, lg_avg, fixtures, teams, gw_next)
    probs.save_team_snap(con, sid, t_fix)
    t_chg, t_chg_ts = probs.team_changes(con, sid)
    usage = probs.player_usage(con, fixtures, gw_cur)
    el_raw = {e["id"]: e for e in bst["elements"]}
    own_d, own_used = probs.own_deltas(con, sid, ts)
    ga_ratio = probs.fpl_ratios(bst)
    S_all = seasons.load(con)
    players_out = []
    fdr_p = past_fdr(fixtures)
    tshort = {t["id"]: t["short_name"] for t in bst["teams"]}
    for r in sorted([x for x in rows if x["id"] in show_ids or x["id"] in wide_ids], key=lambda x: -x["score"]):
        d = dict(r)
        d["wide"] = r["id"] not in show_ids  # вне пула: только для поиска/карточки, не для рекомендаций
        d["taken_by"] = taken.get(r["id"], "")
        d["mine"] = r["id"] in mine_ids
        d["top_cnt"] = top["owned"].get(r["id"], 0)
        d["top_in"] = top["ins"].get(r["id"], 0)
        d["top_out"] = top["outs"].get(r["id"], 0)
        d["top_delta"] = top_delta.get(r["id"], 0)
        d["series"] = gw_series(con, r["id"], r["team"], fdr_p, tshort)
        d["seasons"] = seasons.card(S_all.get(r["id"], []), r["price"])
        d.update(trend.get(r["id"], {}))
        d["net_tr"] = r["tin"] - r["tout"]
        d["pr"] = probs.player_probs(r, el_raw[r["id"]], usage, t_str, lg_avg, t_fix, gw_next, ga_ratio)
        d["sp"] = probs.set_pieces(el_raw[r["id"]])
        d["own_d"] = own_d.get(r["id"], {})
        players_out.append(d)

    def tl(dct):
        return sorted(dct.items(), key=lambda kv: -kv[1])

    top_out = {"n": top["n"], "ins_list": tl(top["ins"])[:25], "outs_list": tl(top["outs"])[:25],
               "caps_list": tl(top["caps"])[:8], "chips": top["chips"],
               "owned_list": tl(top["owned"])[:40]}
    for k in ("ins", "outs", "caps", "owned"):
        pass
    top_pub = dict(top_out)

    data = {
        "meta": {"generated": ts + "Z", "gw_cur": gw_cur, "gw_next": gw_next, "deadline": deadline,
                 "season": cfg.get("season"), "league_id": cfg.get("league_id"), "offline": OFFLINE, "snapshots": con.execute("SELECT COUNT(*) FROM snapshots").fetchone()[0]},
        "me": managers["me"], "league": managers, "league_table": lg, "conflicts": conflicts,
        "players": players_out, "changes": changes, "top": top_pub, "sugg": sugg, "insurance": insur,
        "teams": {t["id"]: t["short_name"] for t in bst["teams"]},
        "teams_model": {"src": t_src, "avg": round(lg_avg, 3), "gws": probs.TEAM_GWS,
                        "str": {t: {"att": round(v["att"], 3), "def": round(v["def"], 3), "n": v["n"]} for t, v in t_str.items()},
                        "fix": t_fix, "chg": t_chg, "chg_ts": t_chg_ts, "ratios": ga_ratio, "sp": probs.team_set_pieces(bst)},
        "own_used": own_used,
        "live": probs.build_live(get, bst, fixtures, managers, cur_ev),
        "all_names": {r["id"]: {"name": r["name"], "team": r["tname"], "pos": r["pos"], "price": r["price"]} for r in rows
                      if r["id"] in show_ids or r["id"] in mine_ids or r["id"] in friends_ids or r["id"] in chg_ids},
    }
    # имена для игроков из трансферов/капитанов топ-50, которых нет в списках (иначе дашборд покажет «#id»)
    _pos = {1: "GK", 2: "DEF", 3: "MID", 4: "FWD"}
    _els = {e["id"]: e for e in bst["elements"]}
    for i_, _c in top_out["ins_list"] + top_out["outs_list"] + top_out["caps_list"] + top_out["owned_list"]:
        if i_ not in data["all_names"] and i_ in _els:
            e_ = _els[i_]
            data["all_names"][i_] = {"name": e_["web_name"], "team": tshort.get(e_["team"], ""),
                                     "pos": _pos.get(e_["element_type"], ""), "price": e_["now_cost"]}
    data["league_names"] = cfg["names"]
    # скаут-лист (config.json -> watchlist): игроки под наблюдением с заметкой и триггером
    # source: "user" — добавил пользователь кнопкой в дашборде (v1.17), иначе — Claude
    watch = []
    el_ids = {e["id"] for e in bst["elements"]}
    for w in cfg.get("watchlist") or []:
        spec = w if isinstance(w, str) else w.get("player", "")
        d_ = {} if isinstance(w, str) else w
        el = d_.get("fpl_id") if d_.get("fpl_id") in el_ids else None
        if el is None:
            try:
                try:
                    el = resolve_player(spec, bst)
                except ValueError:
                    el = resolve_player(spec.split(":")[0], bst)  # клуб указан неверно — ищем по имени
            except ValueError:
                WARNINGS.append("watchlist: не нашёл игрока '%s' — проверь написание в config.json" % spec)
                continue
        watch.append({"id": el, "player": spec, "prio": d_.get("prio", 3), "note": d_.get("note", ""),
                      "trigger": d_.get("trigger", ""), "source": d_.get("source", "claude"), "added": d_.get("added", "")})
    data_watch = watch
    data["blacklist"] = bl_ids
    # рекомендованный Claude состав (tool/claude_picks.json) — ведёт Claude, дашборд только показывает
    data["claude_lineup"] = load_claude_picks(managers["me"], bst, gw_next)
    data["watch"] = data_watch
    data["bl_track"] = bl_track
    data["holdings"] = {k: sorted(v) for k, v in holdings.items()}
    data["verified"] = verified
    data["friend_moves"] = f_moves
    data["checklist"] = checklist
    data["backtest"] = bt
    data["events"] = events
    for k_ in ("plan", "chips", "threats", "market", "luck", "race", "warnings"):
        data[k_] = ana.get(k_)
    out_dir = OUT_DIR
    with open(os.path.join(out_dir, "data.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    write_brief(os.path.join(out_dir, "claude_brief.md"), data, rows_by_id)
    write_dashboards(out_dir, data, cfg)
    print("\nГотово:")
    print("  out/dashboard.html  — красивый дашборд, дизайн %d (открой в браузере); оба дизайна: out/dashboard_v1.html, out/dashboard_v2.html" % design_of(cfg))
    print("  out/claude_brief.md — скорми этот файл Claude для решения")
    print("  out/data.json       — все данные")
    try:
        analytics.export_csv(out_dir, data, rows_by_id)
        print("  out/export/*.csv    — таблицы для Excel")
    except Exception as ex:
        print("  (экспорт CSV не удался: %s)" % ex)
    if not OFFLINE:
        save_config_history(args.config)
    for w_ in data.get("warnings") or []:
        print("  ⚠", w_)
    removed = prune(con, cfg.get("retention_days", 90))
    n_snap = con.execute("SELECT COUNT(*) FROM snapshots").fetchone()[0]
    con.close()
    write_run_log(out_dir, "%s GW%s сеть=%d кэш=%d устар=%d предупреждений=%d" % (
        ts, gw_next, STATS["net"], STATS["cache"], STATS["stale"], len(data.get("warnings") or [])))
    print("\nСеть: %d запросов, из кэша: %d, из устаревшего кэша (сбой сети): %d. Снимков в базе: %d%s." % (
        STATS["net"], STATS["cache"], STATS["stale"], n_snap, ", удалено старых: %d" % removed if removed else ""))
    # сразу открываем дашборд в браузере по умолчанию (отключить: --no-open или "open_browser": false в config.json)
    if args.serve:
        return  # браузер откроет serve.py по адресу http://127.0.0.1 — там работают настройки
    if not args.no_open and cfg.get("open_browser", True) and not os.environ.get("FPL_NO_OPEN"):
        try:
            import webbrowser
            path = os.path.abspath(os.path.join(out_dir, "dashboard.html"))
            if hasattr(os, "startfile"):
                os.startfile(path)  # Windows: стандартный браузер
            else:
                webbrowser.open("file://" + path)
            print("Дашборд открыт в браузере.")
        except Exception as ex:
            print("Не удалось открыть браузер автоматически (%s). Открой вручную: %s" % (ex, os.path.join(out_dir, "dashboard.html")))


if __name__ == "__main__":
    lock = None
    run_error = None
    try:
        if "--offline" not in sys.argv:
            lock = acquire_lock()
        main()
    except SystemExit:
        raise
    except Exception as ex:
        print("ОШИБКА:", ex)
        if "--serve" not in sys.argv:
            raise
        import traceback
        traceback.print_exc()
        run_error = ["Расчёт не удался: %s. Проверь ID в ⚙ Настройках и нажми «Сохранить и пересчитать»." % ex]
    finally:
        if lock:
            try:
                os.remove(lock)
            except Exception:
                pass
    # окно run.bat: после расчёта держим дашборд с настройками, пока окно открыто (Ctrl+C или крестик — выход)
    if "--serve" in sys.argv:
        if "--config" in sys.argv[:-1]:
            os.environ["FPL_CONFIG"] = os.path.abspath(sys.argv[sys.argv.index("--config") + 1])
        import serve
        serve.run(no_open="--no-open" in sys.argv, error=run_error)
