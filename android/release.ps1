# Публикует APK как релиз в публичном репо данных: приложение отдаёт его по ссылке из version.json.
# Порядок (подробно — mobile/HANDOFF.md, «Обновление APK»):
#   1. Новая запись первой в mobile/changelog.json
#   2. python -X utf8 mobile/make_version.py       (version.json + versionName/versionCode)
#   3. cd android; npm run sync; собрать APK в Android Studio (Build > Build APK)
#   4. powershell -File android\release.ps1 -Apk <путь к app-debug.apk или app-release.apk>   <- этот скрипт
#   5. github-check\sync.ps1, commit, push (и запустить workflow build-data): только после шага 4 приложения узнают о версии
param([Parameter(Mandatory = $true)][string]$Apk)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$v = Get-Content "$root\mobile\version.json" -Raw -Encoding UTF8 | ConvertFrom-Json
if (-not (Test-Path $Apk)) { throw "APK не найден: $Apk" }
$tmp = Join-Path $env:TEMP 'fpl-advisor.apk'          # имя файла фиксировано: ссылка releases/latest/download/fpl-advisor.apk
Copy-Item $Apk $tmp -Force
$notes = ($v.items | ForEach-Object { "- $($_.title): $($_.text)" }) -join "`n"
$repo = 'time2blink/fpl-advisor-data'
gh release create "v$($v.version)" $tmp --repo $repo --title "FPL Advisor $($v.version)" --notes "$($v.title)`n`n$notes" --latest
Write-Host "Релиз v$($v.version) создан: https://github.com/$repo/releases/tag/v$($v.version)"
