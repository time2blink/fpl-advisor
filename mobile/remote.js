/* Живые данные: data.json из публичного репозитория (его собирает GitHub Actions раз в ~3 часа).
   Порядок: встроенный срез data.js -> сохранённая копия в localStorage (если свежее) -> фоновая загрузка. */
(function () {
  var BASE = 'https://raw.githubusercontent.com/time2blink/fpl-advisor-data/main/', KEY = 'fpl-data-v1';
  var gen = function (d) { return (d && d.meta && Date.parse(d.meta.generated)) || 0; };
  var valid = function (d) { return !!(d && d.players && d.me && d.me.squad && d.meta && d.claude && d.live); };
  var cached = null;
  try { cached = JSON.parse(localStorage.getItem(KEY)); } catch (e) {}
  if (valid(cached) && gen(cached) > gen(window.FPL)) window.FPL = cached;
  window.FPL_REMOTE = {
    base: BASE,
    /* bust=true — мимо кэша raw (при ручном обновлении); иначе ключ меняется раз в 5 минут. Возвращает новые данные или null. */
    fetch: function (bust) {
      var u = BASE + 'data.json?t=' + (bust ? Date.now() : Math.floor(Date.now() / 3e5));
      var c = new AbortController(), t = setTimeout(function () { c.abort(); }, 15000);
      return fetch(u, { cache: 'no-store', signal: c.signal })
        .then(function (r) { clearTimeout(t); if (!r.ok) throw new Error(r.status); return r.json(); })
        .then(function (d) {
          if (!valid(d)) throw new Error('bad data');
          if (gen(d) <= gen(window.FPL)) return null;
          try { localStorage.setItem(KEY, JSON.stringify(d)); } catch (e) {}
          return d;
        });
    }
  };
})();
