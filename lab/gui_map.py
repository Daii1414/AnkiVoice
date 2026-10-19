"""Карта функций текущего tkinter-интерфейса.

Нужно, чтобы веб-версия покрывала ВСЁ, что делает anki_gui.py: какие
действия, какие поля ввода, что показывает лог. Потерять функцию при
переработке — хуже, чем не перерабатывать.
"""
import re

s = open(r"E:\TTS-проект\anki_gui.py", encoding="utf-8").read()

print("=== кнопки (текст -> что запускает) ===")
for m in re.finditer(
        r"text=[\"']([^\"']{2,40})[\"'][^)]{0,400}?command=(\w+)", s, re.S):
    print("  %-26s -> %s" % (m.group(1), m.group(2)))

print("\n=== подписи полей ввода ===")
for m in re.finditer(
        r"(?:text|labeltext)=[\"']([^\"']{3,44})[\"']", s):
    t = m.group(1)
    if any(k in t for k in ("Колод", "Голос", "Поле", "GPT", "SoVITS",
                            "папк", "Папк", "режим", "Режим", "сид",
                            "Скорост", "скорост", "референ", "Референ")):
        print("  ", t)

print("\n=== переменные конфига ===")
cfg = re.findall(r"cfg\.get\(\"(\w+)\"", s)
from collections import Counter
for k, v in Counter(cfg).most_common(30):
    print("  %-22s %d упоминаний" % (k, v))

print("\n=== вызовы пайплайна (аргументы команд) ===")
for m in re.finditer(r"\[\s*\"(voice|check|scan|clone|make-deck|test|selftest)"
                     r"\"([^\]]*)\]", s):
    print("  %s %s" % (m.group(1), m.group(2).strip()[:80]))
