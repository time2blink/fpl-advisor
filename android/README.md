# android/ - Android-приложение FPL Advisor (Capacitor)

- `www/` - веб-часть, копируется из `../mobile` командой `node scripts/sync-web.mjs`, затем `npx cap sync`.
- `android/` - проект Android Studio. Нативная часть: виджет дедлайна (`DeadlineWidget.java`, `WidgetData.java`), переход по тапу (`MainActivity.java`).
- `dist/FPL-Advisor-debug.apk` - готовая отладочная сборка (ставится на телефон вручную).

Сборка (из `android/android`), нужен JDK 21 (Gradle не работает с Java 25 из Android Studio):

    $env:JAVA_HOME="C:\Program Files\Microsoft\jdk-21.0.12.101-hotspot"
    $env:ANDROID_HOME="$env:LOCALAPPDATA\Android\Sdk"
    .\gradlew.bat assembleDebug

Эмулятор: AVD `Medium_Phone_API_37.0`. Данные приложение и виджет берут из github.com/time2blink/fpl-advisor-data.
