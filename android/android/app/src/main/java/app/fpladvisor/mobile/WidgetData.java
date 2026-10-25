package app.fpladvisor.mobile;

import android.content.Context;
import android.content.SharedPreferences;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Date;
import java.util.List;
import java.util.Locale;
import java.util.TimeZone;

/** Данные для виджетов: те же data.json и news.json, что читает приложение. Кэш в SharedPreferences. */
final class WidgetData {
    static final String BASE = "https://raw.githubusercontent.com/time2blink/fpl-advisor-data/main/";
    private static final String PREFS = "fpl_widget";
    private static final long STALE_MS = 20 * 60 * 1000L;

    static final class Item {
        final String kind, title, sub, go;
        Item(String kind, String title, String sub, String go) { this.kind = kind; this.title = title; this.sub = sub; this.go = go; }
    }

    JSONObject data, news;
    long fetchedAt;

    static WidgetData load(Context c, boolean forceNet) {
        SharedPreferences sp = c.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        WidgetData w = new WidgetData();
        try { w.data = new JSONObject(sp.getString("data", "")); } catch (Exception ignored) { }
        try { w.news = new JSONObject(sp.getString("news", "")); } catch (Exception ignored) { }
        w.fetchedAt = sp.getLong("ts", 0);
        if (forceNet || w.data == null || System.currentTimeMillis() - w.fetchedAt > STALE_MS) {
            String d = get("data.json"), n = get("news.json");
            SharedPreferences.Editor e = sp.edit();
            try { if (d != null) { w.data = new JSONObject(d); e.putString("data", d); } } catch (Exception ignored) { }
            try { if (n != null) { w.news = new JSONObject(n); e.putString("news", n); } } catch (Exception ignored) { }
            if (d != null) { w.fetchedAt = System.currentTimeMillis(); e.putLong("ts", w.fetchedAt); }
            e.apply();
        }
        return w;
    }

    private static String get(String name) {
        HttpURLConnection h = null;
        try {
            h = (HttpURLConnection) new URL(BASE + name + "?t=" + (System.currentTimeMillis() / 300000)).openConnection();
            h.setConnectTimeout(10000);
            h.setReadTimeout(15000);
            if (h.getResponseCode() != 200) return null;
            try (InputStream in = h.getInputStream()) {
                ByteArrayOutputStream bo = new ByteArrayOutputStream();
                byte[] b = new byte[8192];
                int r;
                while ((r = in.read(b)) > 0) bo.write(b, 0, r);
                return bo.toString("UTF-8");
            }
        } catch (Exception e) {
            return null;
        } finally {
            if (h != null) h.disconnect();
        }
    }

    boolean ok() { return data != null; }

    int gwNext() { return data.optJSONObject("meta") == null ? 0 : data.optJSONObject("meta").optInt("gw_next"); }

    long deadlineMs() {
        try {
            SimpleDateFormat f = new SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss'Z'", Locale.US);
            f.setTimeZone(TimeZone.getTimeZone("UTC"));
            Date d = f.parse(data.getJSONObject("meta").getString("deadline"));
            return d == null ? 0 : d.getTime();
        } catch (Exception e) { return 0; }
    }

    String deadlineText() {
        long ms = deadlineMs();
        if (ms == 0) return "";
        SimpleDateFormat f = new SimpleDateFormat("EEE, d MMM · HH:mm", new Locale("ru"));
        f.setTimeZone(TimeZone.getTimeZone("Europe/Kyiv"));
        return f.format(new Date(ms));
    }

    String bank() { return "£" + String.format(Locale.US, "%.1f", data.optJSONObject("me").optInt("bank") / 10.0); }

    int ft() { return data.optJSONObject("me").optInt("ft"); }

    private String playerName(int id) {
        JSONObject p = data.optJSONObject("players") == null ? null : data.optJSONObject("players").optJSONObject(String.valueOf(id));
        return p == null ? "#" + id : p.optString("name");
    }

    /** Список дел: news.todo от Claude, иначе запасной расчёт (капитан + игроки под вопросом). */
    List<Item> todo() {
        List<Item> out = new ArrayList<>();
        JSONArray t = news == null ? null : news.optJSONArray("todo");
        if (t != null && t.length() > 0) {
            for (int i = 0; i < t.length(); i++) {
                JSONObject o = t.optJSONObject(i);
                if (o != null) out.add(new Item(o.optString("k", "warn"), o.optString("title"), o.optString("sub"), o.optString("go", "home")));
            }
            return out;
        }
        JSONObject cl = data.optJSONObject("claude");
        if (cl == null) return out;
        out.add(new Item("cap", "Капитан — " + playerName(cl.optInt("captain")), "по модели", "squad"));
        int q = 0;
        JSONObject pl = data.optJSONObject("players");
        for (String k : new String[]{"xi", "bench"}) {
            JSONArray a = cl.optJSONArray(k);
            for (int i = 0; a != null && i < a.length(); i++) {
                JSONObject p = pl == null ? null : pl.optJSONObject(String.valueOf(a.optInt(i)));
                if (p != null && (!"a".equals(p.optString("status", "a")) || (!p.isNull("chance") && p.optInt("chance", 100) < 100))) q++;
            }
        }
        if (q > 0) out.add(new Item("warn", "Проверить игроков: " + q, "под вопросом", "news"));
        return out;
    }

    static int openCount(List<Item> items) {
        int n = 0;
        for (Item i : items) if (!"ok".equals(i.kind)) n++;
        return n;
    }
}
