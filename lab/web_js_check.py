"""Проверка JS внутри anki_web_page.py через node --check.

Веб-страница — основа нового интерфейса. Ошибка в JS не падает при сборке
Python, а убивает страницу в браузере молча. Поэтому синтаксис скрипта
проверяем отдельно: вырезаем <script> и гоняем через node --check.
"""
import os
import re
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app"))
from anki_web_page import HTML  # noqa: E402

m = re.search(r"<script>(.*?)</script>", HTML, re.S)
if not m:
    print("FAIL: <script> не найден")
    sys.exit(1)

js = m.group(1)
fd, path = tempfile.mkstemp(suffix=".js")
os.close(fd)
with open(path, "w", encoding="utf-8") as f:
    f.write(js)

p = subprocess.run(["node", "--check", path],
                   capture_output=True, text=True, shell=False)
os.unlink(path)

if p.returncode == 0:
    print("JS syntax OK (%d строк)" % js.count("\n"))
else:
    print("FAIL:")
    print(p.stderr)
    sys.exit(1)
