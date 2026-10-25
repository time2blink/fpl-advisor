package app.fpladvisor.mobile;

import android.app.PendingIntent;
import android.appwidget.AppWidgetManager;
import android.appwidget.AppWidgetProvider;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.graphics.Color;
import android.text.SpannableString;
import android.text.Spanned;
import android.text.TextUtils;
import android.text.style.AbsoluteSizeSpan;
import android.text.style.StrikethroughSpan;
import android.view.View;
import android.widget.RemoteViews;

import java.util.ArrayList;
import java.util.List;

/** Виджет 4×2: отсчёт до дедлайна, банк и трансферы, три главных дела. Тап по делу открывает нужный экран. */
public class DeadlineWidget extends AppWidgetProvider {

    @Override
    public void onUpdate(Context ctx, AppWidgetManager mgr, int[] ids) {
        final PendingResult pr = goAsync();
        final Context app = ctx.getApplicationContext();
        new Thread(() -> {
            try { render(app, mgr, ids, false); } finally { pr.finish(); }
        }).start();
    }

    /** Из приложения: обновить все виджеты (с принудительной загрузкой). */
    static void refreshAll(Context ctx, boolean forceNet) {
        final Context app = ctx.getApplicationContext();
        new Thread(() -> {
            AppWidgetManager mgr = AppWidgetManager.getInstance(app);
            int[] ids = mgr.getAppWidgetIds(new ComponentName(app, DeadlineWidget.class));
            if (ids.length > 0) render(app, mgr, ids, forceNet);
        }).start();
    }

    private static void render(Context ctx, AppWidgetManager mgr, int[] ids, boolean forceNet) {
        WidgetData w = WidgetData.load(ctx, forceNet);
        for (int id : ids) mgr.updateAppWidget(id, build(ctx, w));
    }

    private static PendingIntent open(Context ctx, String go, int code) {
        Intent i = new Intent(ctx, MainActivity.class).setFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP);
        if (go != null && !go.isEmpty()) i.putExtra("go", go);
        return PendingIntent.getActivity(ctx, code, i, PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
    }

    private static CharSequence big(String num, String unit) {
        SpannableString s = new SpannableString(num + unit);
        s.setSpan(new AbsoluteSizeSpan(15, true), num.length(), s.length(), Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);
        return s;
    }

    static RemoteViews build(Context ctx, WidgetData w) {
        RemoteViews v = new RemoteViews(ctx.getPackageName(), R.layout.widget_deadline);
        v.setOnClickPendingIntent(R.id.w_root, open(ctx, "home", 10));
        if (!w.ok()) {
            v.setTextViewText(R.id.w_count, "—");
            v.setTextViewText(R.id.w_label, "Нет данных");
            v.setTextViewText(R.id.w_date, "Откройте приложение");
            return v;
        }
        v.setTextViewText(R.id.w_pill, "Тур " + w.gwNext());
        v.setTextViewText(R.id.w_date, w.deadlineText());
        v.setTextViewText(R.id.w_bank, w.bank());
        v.setTextViewText(R.id.w_ft, "FT " + w.ft());

        long left = w.deadlineMs() - System.currentTimeMillis();
        List<WidgetData.Item> todo = w.todo();
        int open = WidgetData.openCount(todo);
        if (left <= 0) {
            v.setTextViewText(R.id.w_label, "Дедлайн");
            v.setTextViewText(R.id.w_count, "прошёл");
        } else {
            long min = left / 60000, d = min / 1440, h = (min % 1440) / 60, m = min % 60;
            v.setTextViewText(R.id.w_label, "До дедлайна");
            if (d > 0) v.setTextViewText(R.id.w_count, TextUtils.concat(big(d + "", " дн "), big(h + "", " ч")));
            else if (h > 0) v.setTextViewText(R.id.w_count, TextUtils.concat(big(h + "", " ч "), big(m + "", " мин")));
            else v.setTextViewText(R.id.w_count, big(m + "", " мин"));
        }
        // цвет сигнала: красный меньше 2 ч, жёлтый есть дела, зелёный всё готово
        int pill = left > 0 && left < 2 * 3600_000L ? R.drawable.widget_pill_bad : open > 0 ? R.drawable.widget_pill_warn : R.drawable.widget_pill_ok;
        v.setInt(R.id.w_pill, "setBackgroundResource", pill);
        v.setTextColor(R.id.w_pill, pill == R.drawable.widget_pill_bad ? Color.WHITE : Color.parseColor("#3A1C00"));

        int[] rows = {R.id.w_t1, R.id.w_t2, R.id.w_t3};
        // сначала невыполненные, затем готовые
        ArrayList<WidgetData.Item> sorted = new ArrayList<>();
        for (WidgetData.Item it : todo) if (!"ok".equals(it.kind)) sorted.add(it);
        for (WidgetData.Item it : todo) if ("ok".equals(it.kind)) sorted.add(it);
        for (int i = 0; i < rows.length; i++) {
            if (i >= sorted.size()) { v.setViewVisibility(rows[i], View.GONE); continue; }
            WidgetData.Item it = sorted.get(i);
            boolean done = "ok".equals(it.kind);
            SpannableString s = new SpannableString(it.title);
            if (done) s.setSpan(new StrikethroughSpan(), 0, s.length(), Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);
            v.setViewVisibility(rows[i], View.VISIBLE);
            v.setTextViewText(rows[i], s);
            v.setTextColor(rows[i], done ? Color.parseColor("#8CFFFFFF") : Color.WHITE);
            int dot = done ? R.drawable.widget_dot_ok : "cap".equals(it.kind) ? R.drawable.widget_dot_cap : R.drawable.widget_dot_warn;
            v.setTextViewCompoundDrawables(rows[i], dot, 0, 0, 0);
            v.setOnClickPendingIntent(rows[i], open(ctx, it.go, 20 + i));
        }
        return v;
    }
}
