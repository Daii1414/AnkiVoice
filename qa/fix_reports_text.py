# -*- coding: utf-8 -*-
"""Чистка текста отчётов: китайские иероглифы, английские вставки,
кириллические «двойники» японских знаков, сломанные слова."""
import io
import os

ROOT = os.environ["AV_ROOT"]

# --- отчёт по бенчмарку чтения --------------------------------------------
p = os.path.join(ROOT, "doc", "reports", "REPORT-g2p-benchmark.md")
s = io.open(p, encoding="utf-8").read()
PAIRS = [
    # китайские иероглифы внутри русской фразы
    ("(`g2p_core.py`,\u9577\u671f \u52a9\u624b, JSON-\u043f\u0440\u043e\u0442\u043e\u043a\u043e\u043b)",
     "(`g2p_core.py` \u2014 \u0434\u043e\u043b\u0433\u043e\u0432\u0440\u0435\u043c\u0435\u043d\u043d\u0430\u044f "
     "\u043f\u0430\u043c\u044f\u0442\u044c, JSON-\u043f\u0440\u043e\u0442\u043e\u043a\u043e\u043b)"),
    # английская вставка
    ("kanaize deliberately \u043e\u0441\u0442\u0430\u0432\u043b\u044f\u0435\u0442",
     "kanaize \u043d\u0430\u043c\u0435\u0440\u0435\u043d\u043d\u043e \u043e\u0441\u0442\u0430\u0432\u043b\u044f\u0435\u0442"),
    ("\u043f\u0440\u044f\u043c\u043e\u0435\u0441\u043e\u043e\u0442\u0432\u0435\u0442\u0441\u0442\u0432\u0438\u0435",
     "\u043f\u0440\u044f\u043c\u043e\u0435 \u0441\u043e\u043e\u0442\u0432\u0435\u0442\u0441\u0442\u0432\u0438\u0435"),
    ("\u043a\u043e\u0440\u0440\u0435\u043a\u0442\u043d\u043e\u0441\u0442\u044c \u043d\u0430\u0448\u0435\u0433\u043e "
     "\u0437\u0430\u0442\u043e\u0440\u0430",
     "\u043a\u043e\u0440\u0440\u0435\u043a\u0442\u043d\u043e\u0441\u0442\u044c \u043d\u0430\u0448\u0435\u0433\u043e "
     "\u0437\u0430\u043c\u0435\u0440\u0430"),
    # кириллические двойники японских знаков
    ("\u3068\u043e\u043d\u043e", "\u30c8\u30ce"),
    ("\u30c9\u043d\u043e", "\u30c9\u30ce"),
    ("\u30c8\u043d\u043e", "\u30c8\u30ce"),
    # сломанные слова
    ("\u0445\u0432\u043e\u0441\u0442\u043e\u0432\u0430\u044f \u0430\u043f\u043e\u0441\u0442\u0440\u043e\u0444\u0430",
     "\u0430\u043f\u043e\u0441\u0442\u0440\u043e\u0444\u0430 \u0432 \u043a\u043e\u043d\u0446\u0435"),
    ("\u041f\u0440\u043e\u0448\u043b\u0438 additionally",
     "\u041f\u0440\u043e\u0448\u043b\u0438"),
    ("\u041e\u0431\u0430 \u0434\u0432\u0438\u0436\u043a\u0430 \u0447\u0438\u0442\u0430\u044e\u0442 \u0438\u0445 "
     "\u043f\u043e \u043e\u0431\u0449\u0435\u043c\u0443 \u0441\u043b\u043e\u0432\u0430\u0440\u044e "
     "\u043d\u0435\u043f\u0440\u0430\u0432\u0438\u043b\u044c\u043d\u043e",
     "\u041e\u0431\u0449\u0438\u0439 \u0441\u043b\u043e\u0432\u0430\u0440\u044c \u0447\u0438\u0442\u0430\u0435\u0442 "
     "\u0438\u0445 \u043d\u0435\u043f\u0440\u0430\u0432\u0438\u043b\u044c\u043d\u043e"),
    ("\u0447\u0430\u0441\u0442\u0438\u0447\u043d\u0430\u044f notaция",
     "\u0447\u0430\u0441\u0442\u0438\u0447\u043d\u0430\u044f \u043d\u043e\u0442\u0430\u0446\u0438\u044f"),
]
for a, b in PAIRS:
    if a in s:
        s = s.replace(a, b)
        print("  ok:", b[:46])
    else:
        print("  ! не найдено:", a[:46])
io.open(p, "w", encoding="utf-8", newline="\n").write(s)

# --- отчёт по качеству ----------------------------------------------------
p = os.path.join(ROOT, "doc", "reports", "REPORT-quality-v2.md")
s = io.open(p, encoding="utf-8").read()
for a, b in (("\uff76\uff9e\uff8d\uff9e\uff73", "\u30ac\u30ad\u30e7\u30a6"),
             ("\uff8a\uff9e\uff8d\u309a\u309a\u309a\u30fc", "\u30d1\u30d8\u30fc\u30fc")):
    if a in s:
        s = s.replace(a, b)
        print("  ok (quality):", b)
    else:
        print("  ! не найдено (quality):", a)
io.open(p, "w", encoding="utf-8", newline="\n").write(s)

# --- EN README: ссылка на английские замеры -------------------------------
p = os.path.join(ROOT, "README.en.md")
s = io.open(p, encoding="utf-8").read()
if "doc/reports/MEASUREMENTS.md" in s:
    s = s.replace("doc/reports/MEASUREMENTS.md", "doc/reports/MEASUREMENTS.en.md")
    io.open(p, "w", encoding="utf-8", newline="\n").write(s)
    print("  ok: EN README -> MEASUREMENTS.en.md")
print("готово")
