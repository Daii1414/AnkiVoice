"""Простая расшифровка лога: PowerShell читает UTF-8 вывод Python своей
кодовой страницей и пишет UTF-16LE. Восстанавливаем обратно."""
import sys

p = sys.argv[1]
raw = open(p, "rb").read()
s = raw.decode("utf-16-le", errors="ignore")
t = s.encode("cp437", errors="ignore").decode("utf-8", errors="ignore")
for l in [x for x in t.splitlines() if x.strip()]:
    print(l.rstrip()[:120])
