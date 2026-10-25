#!/usr/bin/env python3
"""Собирает dist/FPL_Advisor_for_friend.zip — анализатор для друга (Стаса/Ромы).

Копирует tool/ без личной истории (cache/, out/, data/, mock/, __pycache__/, claude_picks.json,
ярлык с путём Жени) и с очищенным config.json (pending/blacklist/watchlist пустые).
Оригинальные файлы не меняются: всё пишется сразу в zip.
"""
import json
import os
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DIST = os.path.join(ROOT, "dist")
ZIP_NAME = "FPL_Advisor_for_friend.zip"
FOLDER = "FPL_Advisor"  # папка внутри zip

SKIP_DIRS = {"cache", "out", "data", "mock", "__pycache__", ".claude"}
SKIP_FILES = {"claude_picks.json", "FPL Advisor.lnk", "config.json",
              "pack.py", "make_friend_pack.bat"}
SKIP_EXT = {".pyc", ".pyo", ".db", ".lock", ".log", ".tmp"}

README = """FPL Advisor — анализатор мини-лиги FPL

1. Поставь Python 3.8 или новее: https://www.python.org/downloads/
   В первом окне установщика ОБЯЗАТЕЛЬНО отметь галку «Add python.exe to PATH».
2. Распакуй этот архив в любую папку (например, Документы\\FPL_Advisor).
3. Открой папку FPL_Advisor и дважды кликни run.bat.
   Откроется чёрное окно, через ~30 секунд в браузере появится дашборд.
4. Сначала там будет чужая команда — это нормально. Нажми ⚙ рядом с названием
   команды (вверху «Обзора»).
5. Впиши свой ID и ID соперников, при желании — ID мини-лиги.
   ID — число из адреса страницы «Очки»: fantasy.premierleague.com/entry/1234567/event/8
6. Нажми «Сохранить и пересчитать». Страница обновится сама примерно через 30 секунд.

Важно: окно run.bat не закрывай, пока пользуешься настройками и пересчётом.
Закрыл окно — всё остановилось (в фоне ничего не остаётся). В следующий раз
снова двойной клик по run.bat — данные обновятся.

Ярлык на рабочий стол: один раз дважды кликни create_shortcut.bat.
Подробности — README_TOOL.md и INSTALL.md в папке FPL_Advisor.
"""


def clean_config(path):
    with open(path, encoding="utf-8") as f:
        cfg = json.load(f)
    cfg["pending"] = {}
    cfg["blacklist"] = []
    cfg["watchlist"] = []
    return json.dumps(cfg, ensure_ascii=False, indent=2) + "\n"


def iter_files():
    for dirpath, dirnames, filenames in os.walk(HERE):
        rel_dir = os.path.relpath(dirpath, HERE)
        if rel_dir == ".":
            dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        else:
            dirnames[:] = sorted(d for d in dirnames if d != "__pycache__")
        for name in sorted(filenames):
            if rel_dir == "." and name in SKIP_FILES:
                continue
            if os.path.splitext(name)[1].lower() in SKIP_EXT:
                continue
            full = os.path.join(dirpath, name)
            yield full, os.path.relpath(full, HERE).replace(os.sep, "/")


def build(dest_dir=DIST):
    os.makedirs(dest_dir, exist_ok=True)
    target = os.path.join(dest_dir, ZIP_NAME)
    tmp = target + ".tmp"
    n = 0
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        for full, rel in iter_files():
            z.write(full, FOLDER + "/" + rel)
            n += 1
        z.writestr(FOLDER + "/config.json", clean_config(os.path.join(HERE, "config.json")).encode("utf-8"))
        # BOM + CRLF — чтобы Блокнот на любой Windows показал кириллицу правильно
        z.writestr("ПРОЧТИ_МЕНЯ.txt", ("﻿" + README.replace("\n", "\r\n")).encode("utf-8"))
        n += 2
    os.replace(tmp, target)
    return target, n


def main():
    try:
        target, n = build()
    except Exception as ex:
        print("Не получилось собрать архив: %s" % ex)
        return 1
    size = os.path.getsize(target) / 1024.0
    print("Готово: %s (%d файлов, %.0f КБ)" % (target, n, size))
    print("Личное очищено: pending, blacklist, watchlist; без cache/out/data/mock и claude_picks.json.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
