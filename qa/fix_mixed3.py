# -*- coding: utf-8 -*-
"""Последние два смешения алфавитов в отчёте по бенчмарку."""
import io
import os

ROOT = os.environ["AV_ROOT"]
p = os.path.join(ROOT, "doc", "reports", "REPORT-g2p-benchmark.md")
s = io.open(p, encoding="utf-8").read()

OLD = ("\u5408\u5370 \u2192 \u3042\u3044\u3044\u3093 \u0432\u043c\u0435\u0441\u0442\u043e "
       "\u0430\u0438\u0436\u0438\u0440\u0441\u0438, "
       "\u4ed5\u53e3 \u2192 \u3057\u3050\u3061\u0432\u043c\u0435\u0441\u0442\u043e"
       "\u0448\u0438\u043a\u0447\u0442\u0438")
NEW = ("\u5408\u5370 \u2192 \u3042\u3044\u3044\u3093 \u0432\u043c\u0435\u0441\u0442\u043e "
       "\u3042\u3044\u3058\u308b\u3057, "
       "\u4ed5\u53e3 \u2192 \u3057\u3050\u3061 \u0432\u043c\u0435\u0441\u0442\u043e"
       "\u3057\u304f\u3061")

if OLD in s:
    s = s.replace(OLD, NEW, 1)
    print("  ok: строка про 合印 и 仕口")
else:
    print("  ! не найдено — печатаю строку как есть:")
    for l in s.split("\n"):
        if "\u5408\u5370" in l and "\u2192" in l:
            print("   ", l[:300])
io.open(p, "w", encoding="utf-8", newline="\n").write(s)
