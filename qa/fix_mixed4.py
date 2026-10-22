# -*- coding: utf-8 -*-
"""Оставшиеся смешения алфавитов — правка по кодпоинтам (без набора текста руками)."""
import io
import os

ROOT = os.environ["AV_ROOT"]
p = os.path.join(ROOT, "doc", "reports", "REPORT-g2p-benchmark.md")
s = io.open(p, encoding="utf-8").read()

PAIRS = [
    # ビ ェ н и ャ к 殿  ->  ビェニック殿
    ("\u30d3\u30a7\u043d\u0438\u30e3\u043a\u6bbf", "\u30d3\u30a7\u30cb\u30c3\u30af\u6bbf"),
    # а и じ る с и  ->  あいじるし
    ("\u0430\u0438\u3058\u308b\u0441\u0438", "\u3042\u3044\u3058\u308b\u3057"),
    # し く ч т и  ->  しくち
    ("\u3057\u304f\u0447\u0442\u0438", "\u3057\u304f\u3061"),
]
for a, b in PAIRS:
    n = s.count(a)
    if n:
        s = s.replace(a, b)
        print("  ok: заменено %d" % n)
    else:
        print("  ! не найдено")
io.open(p, "w", encoding="utf-8", newline="\n").write(s)
print("готово")
