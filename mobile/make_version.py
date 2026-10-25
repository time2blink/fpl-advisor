"""Готовит релиз приложения из changelog.json (первая версия в массиве = выпускаемая):
  * mobile/version.json   — что приложение увидит как «доступное обновление» (версия, описание, ссылки на APK);
  * android/.../build.gradle — versionName и versionCode (1.2 -> 102), чтобы Android считал APK новее.
Запуск: python -X utf8 mobile/make_version.py   (потом — android/release.ps1, см. mobile/HANDOFF.md, раздел «Обновление APK»)."""
import json
import pathlib
import re

HERE = pathlib.Path(__file__).parent
REPO = "time2blink/fpl-advisor-data"
GRADLE = HERE.parent / "android" / "android" / "app" / "build.gradle"

cur = json.loads((HERE / "changelog.json").read_text(encoding="utf-8"))["versions"][0]
ver = cur["version"]
parts = [int(x) for x in ver.split(".")] + [0, 0]
code = parts[0] * 10000 + parts[1] * 100 + parts[2]          # 1.2 -> 10200, 1.2.1 -> 10201

out = {
    "version": ver,
    "code": code,
    "date": cur.get("date"),
    "title": cur.get("title", ""),
    "items": cur.get("items", []),
    "apk_url": "https://github.com/%s/releases/latest/download/fpl-advisor.apk" % REPO,
    "page_url": "https://github.com/%s/releases/latest" % REPO,
}
(HERE / "version.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

if GRADLE.exists():
    g = GRADLE.read_text(encoding="utf-8")
    g2 = re.sub(r"versionCode\s+\d+", "versionCode %d" % code, g, count=1)
    g2 = re.sub(r'versionName\s+"[^"]*"', 'versionName "%s"' % ver, g2, count=1)
    GRADLE.write_text(g2, encoding="utf-8")
print("version.json:", ver, "code", code)
