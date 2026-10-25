package app.fpladvisor.mobile;

import android.content.Intent;
import android.os.Bundle;

import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        handleGo(getIntent(), 900);
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
        handleGo(intent, 0);
    }

    @Override
    public void onStop() {
        super.onStop();
        DeadlineWidget.refreshAll(this, true);   // после работы с приложением виджет подтягивает свежие данные
    }

    /** Тап по виджету: открыть нужную вкладку (home, squad, moves, news, league). */
    private void handleGo(Intent i, long delayMs) {
        final String go = i == null ? null : i.getStringExtra("go");
        if (go == null || !go.matches("[a-z]{3,10}") || getBridge() == null) return;
        i.removeExtra("go");
        getBridge().getWebView().postDelayed(() -> getBridge().getWebView().evaluateJavascript("location.hash='#" + go + "'", null), delayMs);
    }
}
