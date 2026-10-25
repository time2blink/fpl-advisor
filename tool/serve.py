"""
Локальный режим дашборда с настройками (v1.15).

run.bat -> fpl_tool.py --serve: после расчёта дашборд открывается по адресу http://127.0.0.1:<порт>/
и работает, пока открыто окно run.bat. Закрыл окно (или Ctrl+C) — всё остановилось, в фоне ничего не остаётся.

Что умеет (кнопка ⚙ рядом с названием команды на главной):
  GET  /api/settings          — текущие ID: мой, соперники (1–5), мини-лига
  POST /api/check   {id}      — проверить ID менеджера в FPL (команда, имя, его мини-лиги)
  POST /api/settings {...}    — сохранить в config.json (старый конфиг кладётся в data/config_history)
  POST /api/watch {action,id,player,prio,note,trigger} — скаут-лист: add (пометка source=user) / remove (v1.17)
  POST /api/run               — пересчитать (запускает fpl_tool.py заново) и вернуть хвост лога

Безопасность: слушаем только 127.0.0.1; каждый запрос к /api/ должен нести одноразовый токен,
который сервер вписывает в отдаваемый dashboard.html (чужой сайт в браузере его не знает).
"""
import http.server
import json
import os
import secrets
import socket
import subprocess
import sys
import threading
import urllib.request
import webbrowser

HERE = os.path.dirname(os.path.abspath(__file__))
CFG = os.environ.get("FPL_CONFIG") or os.path.join(HERE, "config.json")
OUT = os.environ.get("FPL_OUT_DIR") or os.path.join(HERE, "out")
API = os.environ.get("FPL_BASE", "https://fantasy.premierleague.com/api/")
MAX_RIVALS = 5
TOKEN = secrets.token_urlsafe(24)
RUN_LOCK = threading.Lock()
STATE = {"error": None}


def load_cfg():
    with open(CFG, "r", encoding="utf-8") as f:
        return json.load(f)


def save_cfg(cfg):
    try:
        import fpl_tool
        fpl_tool.save_config_history(CFG)  # копия прежнего конфига — можно откатиться
    except Exception:
        pass
    tmp = CFG + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, CFG)


def fpl_entry(eid):
    """Публичные данные менеджера из FPL: команда, имя, классические мини-лиги (без общих)."""
    req = urllib.request.Request(API + "entry/%d/" % eid, headers={"User-Agent": "Mozilla/5.0 FPL-Advisor"})
    with urllib.request.urlopen(req, timeout=15) as r:
        js = json.loads(r.read().decode("utf-8"))
    leagues = [{"id": l["id"], "name": l["name"]} for l in (js.get("leagues") or {}).get("classic", [])
               if l.get("league_type") == "x"]
    return {"id": eid, "team": js.get("name", ""), "first": js.get("player_first_name", ""),
            "manager": ("%s %s" % (js.get("player_first_name", ""), js.get("player_last_name", ""))).strip(),
            "leagues": leagues}


def _design():
    try:
        d = int(load_cfg().get("design", 2))
    except Exception:
        d = 2
    return d if d in (1, 2) else 2


def settings_view(cfg):
    ent, names = cfg.get("entries", {}), cfg.get("names", {})
    return {"me": {"id": ent.get("me"), "name": names.get("me", "")},
            "rivals": [{"key": k, "id": v, "name": names.get(k, k)} for k, v in ent.items() if k != "me"],
            "league_id": cfg.get("league_id"), "max_rivals": MAX_RIVALS}


def _int(v):
    try:
        v = int(str(v).strip())
        return v if v > 0 else None
    except (TypeError, ValueError):
        return None


def apply_settings(body):
    """Проверяет и пишет ID в config.json. Ключи соперников с тем же ID сохраняются (чтобы не терять pending/чёрный список)."""
    cfg = load_cfg()
    me = _int((body.get("me") or {}).get("id"))
    if not me:
        raise ValueError("Укажи свой ID (число из адреса страницы «Очки» в FPL).")
    rivals = []
    for r in body.get("rivals") or []:
        rid = _int(r.get("id"))
        if rid:
            rivals.append({"id": rid, "name": (r.get("name") or "").strip()})
    if not 1 <= len(rivals) <= MAX_RIVALS:
        raise ValueError("Нужно от 1 до %d соперников." % MAX_RIVALS)
    ids = [me] + [r["id"] for r in rivals]
    if len(set(ids)) != len(ids):
        raise ValueError("ID повторяются: у каждого менеджера свой ID, и свой ID не указывай как соперника.")
    league = body.get("league_id")
    league = _int(league) if str(league or "").strip() else None

    old_ent, old_names = cfg.get("entries", {}), cfg.get("names", {})
    by_id = {v: k for k, v in old_ent.items() if k != "me"}
    new_ent, new_names, used = {"me": me}, {}, set()
    me_name = (body.get("me") or {}).get("name", "").strip()
    if not me_name:
        me_name = old_names.get("me") if old_ent.get("me") == me else ""
    for r in rivals:
        k = by_id.get(r["id"])
        if not k or k in used:
            k = next("r%d" % i for i in range(1, 20) if "r%d" % i not in used and "r%d" % i not in old_ent)
        used.add(k)
        new_ent[k] = r["id"]
        new_names[k] = r["name"] or (old_names.get(k) if old_ent.get(k) == r["id"] else "")
    # пустые имена — берём имя менеджера из FPL
    for k, eid in new_ent.items():
        cur = me_name if k == "me" else new_names.get(k)
        if not cur:
            try:
                cur = fpl_entry(eid)["first"] or str(eid)
            except Exception:
                cur = "ID %d" % eid
        new_names[k] = cur
    new_names = {k: new_names[k] for k in new_ent}

    # pending (ручные составы до дедлайна) действует только для того же менеджера
    pend = cfg.get("pending") or {}
    dropped = [k for k in list(pend) if old_ent.get(k) != new_ent.get(k)]
    for k in dropped:
        pend.pop(k, None)
    if pend or "pending" in cfg:
        cfg["pending"] = pend
    cfg["entries"], cfg["names"], cfg["league_id"] = new_ent, new_names, league
    save_cfg(cfg)
    return {"ok": True, "settings": settings_view(cfg), "dropped_pending": dropped,
            "me_changed": old_ent.get("me") != me}


def apply_watch(body):
    """Скаут-лист из дашборда (v1.17): add — добавить/обновить игрока с пометкой source=user, remove — убрать.
    Игрок задаётся fpl_id + player ('Имя:КЛУБ'); записи Claude без fpl_id находим по строке player."""
    cfg = load_cfg()
    wl = cfg.get("watchlist") or []
    act = body.get("action")
    fid = _int(body.get("id"))
    spec = str(body.get("player") or "").strip()[:60]
    if not fid or not spec:
        raise ValueError("Не указан игрок.")

    def same(w):
        if isinstance(w, str):
            return w == spec
        return w.get("fpl_id") == fid or w.get("player") == spec or (body.get("raw") and w.get("player") == body.get("raw"))

    if act == "remove":
        new = [w for w in wl if not same(w)]
        if len(new) == len(wl):
            raise ValueError("Этого игрока нет в скаут-листе.")
        cfg["watchlist"] = new
        save_cfg(cfg)
        return {"ok": True, "removed": fid}
    if act != "add":
        raise ValueError("Неизвестное действие.")
    try:
        prio = min(3, max(1, int(body.get("prio") or 2)))
    except (TypeError, ValueError):
        prio = 2
    note = str(body.get("note") or "").strip()[:300]
    trig = str(body.get("trigger") or "").strip()[:200]
    import datetime
    entry = {"player": spec, "fpl_id": fid, "prio": prio, "note": note, "trigger": trig,
             "source": "user", "added": datetime.date.today().isoformat()}
    for i, w in enumerate(wl):
        if same(w):
            old = w if isinstance(w, dict) else {}
            if old.get("source", "claude") != "user":  # запись Claude: меняем только приоритет/заметку, авторство не трогаем
                entry = dict(old, prio=prio, fpl_id=fid, note=note or old.get("note", ""), trigger=trig or old.get("trigger", ""))
            wl[i] = entry
            break
    else:
        wl.append(entry)
    cfg["watchlist"] = wl
    save_cfg(cfg)
    return {"ok": True, "entry": entry}


def run_tool():
    if not RUN_LOCK.acquire(blocking=False):
        return {"ok": False, "log": "Пересчёт уже идёт — подожди."}
    try:
        env = dict(os.environ, PYTHONUTF8="1")
        p = subprocess.run([sys.executable, os.path.join(HERE, "fpl_tool.py"), "--no-open", "--config", CFG], cwd=HERE, env=env,
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900)
        log = (p.stdout or "") + (p.stderr or "")
        print(log)
        STATE["error"] = None if p.returncode == 0 else log.strip().splitlines()[-1:]
        return {"ok": p.returncode == 0, "log": "\n".join(log.strip().splitlines()[-12:])}
    except subprocess.TimeoutExpired:
        return {"ok": False, "log": "Пересчёт не уложился в 15 минут."}
    finally:
        RUN_LOCK.release()


class H(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=OUT, **kw)

    def log_message(self, *a):
        pass  # не засоряем окно

    def _json(self, code, obj):
        b = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(b)

    def _authed(self):
        host = (self.headers.get("Host") or "").split(":")[0]
        return self.headers.get("X-FPL-Token") == TOKEN and host in ("127.0.0.1", "localhost")

    def do_GET(self):
        path = self.path.split("?")[0]
        if path in ("/", "/index.html"):
            self.send_response(302)
            self.send_header("Location", "/dashboard.html")
            self.end_headers()
            return
        if path in ("/dashboard.html", "/dashboard_v1.html", "/dashboard_v2.html"):
            # /dashboard.html — дизайн из config.json → design (оба дизайна уже собраны в out/)
            name = path[1:] if path != "/dashboard.html" else "dashboard_v%d.html" % _design()
            fp = os.path.join(OUT, name)
            if not os.path.exists(fp):
                fp = os.path.join(OUT, "dashboard.html")
            if not os.path.exists(fp):
                return self._json(404, {"error": "Дашборда ещё нет — расчёт не прошёл. Смотри окно run.bat."})
            with open(fp, "r", encoding="utf-8") as f:
                html = f.read()
            inj = "<script>window.FPL_SERVER=%s;</script>" % json.dumps({"token": TOKEN, "error": STATE["error"]},
                                                                         ensure_ascii=False)
            html = html.replace("<script>", inj + "<script>", 1)
            b = html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(b)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(b)
            return
        if path.startswith("/api/"):
            if not self._authed():
                return self._json(403, {"error": "нет доступа"})
            if path == "/api/settings":
                return self._json(200, settings_view(load_cfg()))
            return self._json(404, {"error": "нет такого адреса"})
        return super().do_GET()

    def do_POST(self):
        path = self.path.split("?")[0]
        if not self._authed():
            return self._json(403, {"error": "нет доступа"})
        try:
            n = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(n).decode("utf-8") or "{}") if n else {}
        except Exception:
            return self._json(400, {"error": "плохой запрос"})
        try:
            if path == "/api/check":
                eid = _int(body.get("id"))
                if not eid:
                    return self._json(400, {"error": "ID — это число"})
                try:
                    return self._json(200, fpl_entry(eid))
                except Exception:
                    return self._json(404, {"error": "FPL не знает менеджера с ID %s (или нет интернета)" % eid})
            if path == "/api/settings":
                return self._json(200, apply_settings(body))
            if path == "/api/design":
                d = _int(body.get("design"))
                if d not in (1, 2):
                    return self._json(400, {"error": "дизайн — 1 или 2"})
                cfg = load_cfg()
                cfg["design"] = d
                save_cfg(cfg)
                return self._json(200, {"ok": True, "design": d})
            if path == "/api/watch":
                return self._json(200, apply_watch(body))
            if path == "/api/run":
                return self._json(200, run_tool())
        except ValueError as ex:
            return self._json(400, {"error": str(ex)})
        return self._json(404, {"error": "нет такого адреса"})


def _port(pref):
    for p in [pref] + list(range(pref + 1, pref + 20)):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", p))
                return p
            except OSError:
                continue
    return 0


def run(no_open=False, error=None):
    STATE["error"] = error
    try:
        pref = int(load_cfg().get("serve_port", 8765))
    except Exception:
        pref = 8765
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", _port(pref)), H)
    url = "http://127.0.0.1:%d/dashboard.html" % srv.server_address[1]
    print("\n" + "=" * 64)
    print("Дашборд с настройками: %s" % url)
    print("Пока это окно открыто, работают ⚙ Настройки и кнопка «Пересчитать».")
    print("Закончил — просто закрой окно (или Ctrl+C). В фоне ничего не остаётся.")
    print("=" * 64)
    if not no_open:
        try:
            webbrowser.open(url)
        except Exception:
            pass
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
