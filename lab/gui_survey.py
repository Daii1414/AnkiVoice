"""Разбор anki_gui.py: объём интерфейса для оценки переработки."""
import re

s = open(r"E:\TTS-проект\anki_gui.py", encoding="utf-8").read()
print("строк кода:", s.count("\n"))
print("Notebook (вкладки):", s.count("Notebook"))
print()
print("--- виджеты ---")
for w in ("Button", "Label", "Entry", "Combobox", "Text", "Scrollbar",
          "Canvas", "Progressbar", "Treeview", "Checkbutton", "Radiobutton"):
    print("  %-12s %d" % (w, len(re.findall(r"\b" + w + r"\(", s))))
print()
print("--- вкладки ---")
for m in re.finditer(r"text=[\"']([^\"']{2,30})[\"']", s):
    pass
tabs = re.findall(r"nb\.add\(\s*(\w+)\s*,\s*text=[\"']([^\"']+)[\"']", s)
for frame, name in tabs:
    print("  %-14s %s" % (frame, name))
print()
print("--- обработчики команд (запуск пайплайна) ---")
for m in re.finditer(r"pipeline_cmd\([^)]*", s):
    print("  " + m.group(0)[:90])
