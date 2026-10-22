# -*- coding: utf-8 -*-
"""Добить оставшиеся смешения алфавитов в отчёте по бенчмарку."""
import io
import os

ROOT = os.environ["AV_ROOT"]
p = os.path.join(ROOT, "doc", "reports", "REPORT-g2p-benchmark.md")
s = io.open(p, encoding="utf-8").read()

PAIRS = [
    ("コンниЧа", "コンニチャ"),      # комбинированный японский
    ("ビェニャк殿", "ビェニャク殿"),  # имя + фамилия
    ("相決リ矧ги", "相決リ矧ギ"),    # плотничный термин
    ("しгучти", "しぐち"),           # имя
    ("クレнаи", "クレナイ"),         # название фильма
]
for a, b in PAIRS:
    n = s.count(a)
    if n:
        s = s.replace(a, b)
        print("  ok: %s -> %s (%d)" % (a, b, n))
    else:
        print("  ! не найдено:", a)
io.open(p, "w", encoding="utf-8", newline="\n").write(s)
print("готово")
