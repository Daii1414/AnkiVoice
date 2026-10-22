# -*- coding: utf-8 -*-
"""После переезда кода в app/ — поправить пути в скриптах лаборатории."""
import io
import os
import re

ROOT = os.environ["AV_ROOT"]
LAB = os.path.join(ROOT, "lab")
APP = os.path.join(ROOT, "app")

# 1. sys.path: добавить папку с модулями приложения
for name in ("i18n_check.py", "integration_check.py", "qc_unit.py",
             "test_v12_features.py", "web_js_check.py", "robust_tests.py"):
    p = os.path.join(LAB, name)
    s = io.open(p, encoding="utf-8").read()
    if "app" in s and 'os.path.join(ROOT, "app")' in s:
        continue
    if 'sys.path.insert(0, ROOT)' in s:
        s = s.replace('sys.path.insert(0, ROOT)',
                      'sys.path.insert(0, ROOT)\nsys.path.insert(0, os.path.join(ROOT, "app"))', 1)
    elif name == "web_js_check.py":
        s = s.replace('sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))',
                      'sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))\n'
                      'sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname('
                      'os.path.abspath(__file__))), "app"))', 1)
    io.open(p, "w", encoding="utf-8", newline="\n").write(s)
    print("  sys.path:", name)

# 2. пути к файлам модулей
for name in ("i18n_check.py", "readme_check.py", "test_v12_features.py"):
    p = os.path.join(LAB, name)
    s = io.open(p, encoding="utf-8").read()
    before = s
    for mod in ("anki_web_page.py", "anki_web.py", "anki_gui.py",
                "voice_pipeline.py", "i18n_en.py"):
        s = s.replace('os.path.join(ROOT, "%s")' % mod,
                      'os.path.join(ROOT, "app", "%s")' % mod)
        s = s.replace('read("%s")' % mod, 'read("app/%s")' % mod)
    if s != before:
        io.open(p, "w", encoding="utf-8", newline="\n").write(s)
        print("  пути к модулям:", name)

# 3. robust_tests: запуск пайплайна как скрипта
p = os.path.join(LAB, "robust_tests.py")
s = io.open(p, encoding="utf-8").read()
s = s.replace('os.path.join(ROOT, "voice_pipeline.py")',
              'os.path.join(ROOT, "app", "voice_pipeline.py")')
s = s.replace("ROOT = os.path.dirname(CODE)          #",
              "ROOT = os.path.dirname(CODE)          #")
io.open(p, "w", encoding="utf-8", newline="\n").write(s)
print("  robust_tests: путь к пайплайну")

# 4. fmt_check: пропускать папку app? нет — её надо проверять, но исключить .venv
p = os.path.join(LAB, "fmt_check.py")
s = io.open(p, encoding="utf-8").read()
s = s.replace('"lab\\\\pylibs"}', '"lab\\\\pylibs", "app\\\\__pycache__"}')
io.open(p, "w", encoding="utf-8", newline="\n").write(s)
print("  fmt_check: пропуски")
print("готово")
