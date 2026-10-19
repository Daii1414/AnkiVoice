"""Подобрать обратное преобразование для лога пайплайна.

PowerShell прочитал UTF-8 вывод Python своей кодовой страницей и записал
UTF-16LE. Чтобы вернуть японский/кириллицу, перебираем пары
(кодовая страница чтения, кодовая страница обратной записи).
"""
import itertools
import sys

p = sys.argv[1] if len(sys.argv) > 1 else \
    r"C:\Users\daii\AppData\Local\Temp\real_deck.txt"
raw = open(p, "rb").read()
s = raw.decode("utf-16-le", errors="ignore")

CODECS = ("cp437", "cp866", "cp1251", "cp1252", "latin-1", "utf-8")

def looks_good(t):
    return (("音" in t) or ("語" in t) or ("Готово" in t) or ("брак" in t)
            or ("音声" in t) or ("準備" in t))

found = None
for enc, dec in itertools.product(CODECS, CODECS):
    if enc == dec:
        continue
    try:
        t = s.encode(enc, errors="ignore").decode(dec, errors="ignore")
    except Exception:
        continue
    if looks_good(t):
        found = (enc, dec, t)
        print("подошло: encode(%s) -> decode(%s)" % (enc, dec))
        break

if not found:
    print("не подобралось автоматически")
    raise SystemExit(1)

enc, dec, t = found
lines = [l for l in t.splitlines() if l.strip()]
ok = [l for l in lines if l.strip().startswith("OK")]
fail = [l for l in lines if "FAIL" in l]
retry = [l for l in lines if ("брак" in l or "повторяю" in l
                              or "пробую" in l or "сохранён" in l)]
print("строк: %d, OK: %d, FAIL: %d, повторов: %d"
      % (len(lines), len(ok), len(fail), len(retry)))
print()
if retry:
    print("=== спасения ===")
    for l in retry:
        print("  " + l.strip()[:108])
    print()
if fail:
    print("=== FAIL ===")
    for l in fail:
        print("  " + l.strip()[:108])
    print()
print("=== хвост ===")
for l in lines[-5:]:
    print("  " + l.strip()[:108])
