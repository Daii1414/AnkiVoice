# -*- coding: utf-8 -*-
"""robust_tests.py — тесты устойчивости voice_pipeline (без GPU и без синтеза).

Запуск:  python robust_tests.py     (Anki должен быть открыт)

Проверяет, что инструмент переживает чужие конфигурации:
  1. системный прокси в окружении не ломает локальные запросы;
  2. plain(): HTML-теги, [sound:], HTML-сущности; скобки фуриганы целы;
  3. битый voices.json -> понятная ошибка (не traceback);
  4. save_voices атомарен (нет .tmp-остатка);
  5. kanaize-кэш: повтор = тот же результат;
  6. notes_info (чанкинг) == notesInfo целиком;
  7. port_pid: закрытый порт -> None, открытый -> pid+имя процесса;
  8. второй экземпляр пайплайна получает ошибку блокировки;
  9. неверно указанный путь движка -> ошибка перечисляет этот путь;
 10. check --fast работает (без скачивания аудио).
"""
import os
import sys
import io
import json
import subprocess
import http.server
import threading
import socketserver

CODE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(CODE)          # корень репозитория: там лежит voice_pipeline.py
sys.path.insert(0, CODE)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "app"))
PY = sys.executable
ENV = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8",
           GPT_SOVITS_ROOT=os.environ.get("GPT_SOVITS_ROOT", ""))

import voice_pipeline as vp

fails = []


def check(name, cond, extra=""):
    print("%s %-52s %s" % ("OK  " if cond else "FAIL", name, extra))
    if not cond:
        fails.append(name)


def run_py(code, env=ENV):
    return subprocess.run([PY, "-c", code], env=env, capture_output=True,
                          text=True, timeout=120)


BOOT = "import sys; sys.path.insert(0, r'%s'); import voice_pipeline as vp;" % ROOT

# 1. прокси: мёртвый прокси в окружении не мешает локальным запросам
env = dict(ENV, HTTP_PROXY="http://127.0.0.1:9", HTTPS_PROXY="http://127.0.0.1:9")
r = run_py(BOOT + "print(vp.ac('version'))", env=env)
check("прокси в окружении не ломает AnkiConnect",
      r.returncode == 0 and r.stdout.strip().isdigit(), r.stdout.strip()[:60])

# 2. plain(): чистка поля (strip_media=True — для текстов на синтез)
cases = [
    ('<div>大工は相欠[あいが]き</div>', '大工は相欠[あいが]き', True),
    ('A &amp; B', 'A & B', True),
    ('文[sound:foo.ogg]終わり', '文 終わり', True),
    ('文[sound:foo.ogg]終わり', '文[sound:foo.ogg]終わり', False),  # для check — тег цел
    ('相欠[あいが]き', '相欠[あいが]き', True),        # скобки фуриганы НЕ трогаем
    ('Текст&nbsp;здесь', 'Текст здесь', True),
]
bad = [c for c in cases if vp.plain(c[0], strip_media=c[2]) != c[1]]
check("plain(): теги/сущности/[sound:] по флагу, фуригана цела",
      not bad, str(bad)[:120])

# 3. битый voices.json -> понятная ошибка
cfgp = vp.VOICES_FILE
backup = io.open(cfgp, encoding="utf-8").read()
try:
    io.open(cfgp, "w", encoding="utf-8").write("{сломанный json")
    r = run_py(BOOT + "vp.load_voices()")
    check("битый voices.json -> понятная ошибка (не traceback)",
          r.returncode != 0 and "повреждён" in (r.stderr + r.stdout)
          and "Traceback" not in r.stderr, (r.stdout or r.stderr)[:80])
finally:
    io.open(cfgp, "w", encoding="utf-8", newline="").write(backup)

# 4. атомарная запись
vp.save_voices(vp.load_voices())
check("save_voices атомарен (нет .tmp-остатка)", not os.path.exists(cfgp + ".tmp"))

# 5. kanaize-кэш
a = vp.kanaize("圧縮応力")
b = vp.kanaize("圧縮応力")
check("kanaize-кэш: повтор идентичен", a == b and bool(a), a)

# 6. notes_info (чанкинг) == notesInfo целиком
ids = vp.ac("findNotes", query='deck:"Тест100"')[:9]
whole = vp.ac("notesInfo", notes=ids)
chunked = vp.notes_info(ids, chunk=4)
check("notes_info (чанки по 4) == notesInfo целиком",
      [n["noteId"] for n in whole] == [n["noteId"] for n in chunked])

# 7. port_pid
closed = vp.port_pid(18880)
srv = socketserver.TCPServer(("127.0.0.1", 18880), http.server.SimpleHTTPRequestHandler)
threading.Thread(target=srv.serve_forever, daemon=True).start()
pid = vp.port_pid(18880)
name = vp.port_process_name(pid) if pid else ""
srv.shutdown()
check("port_pid: закрытый порт -> None", closed is None)
check("port_pid: слушает python -> pid+имя",
      bool(pid) and "python" in name.lower(), "%s/%s" % (pid, name))

# 8. блокировка второго экземпляра
vp.acquire_lock()
r = run_py(BOOT + "vp.acquire_lock(); print('LOCKED-OK')")
check("второй экземпляр получает ошибку блокировки",
      r.returncode != 0 and "уже запущен" in (r.stdout + r.stderr)
      and "LOCKED-OK" not in r.stdout, (r.stdout or "").strip()[:60])
vp._LOCK_HANDLE.close()

# 9. неверный путь движка -> ошибка перечисляет путь
env = dict(ENV, GPT_SOVITS_ROOT=r"C:\НеСуществует\GPT-SoVITS")
r = run_py(BOOT +
           "vp._read_engine_local_file = lambda: None;"
           "vp._read_engine_gui_config = lambda: None;\n"
           "vp.ENGINE = vp.resolve_engine();\n"
           "try:\n    vp.require_engine()\n"
           "except SystemExit as e:\n    print(e)", env=env)
check("битый путь движка -> ошибка перечисляет указанный путь",
      "НЕ подошли" in r.stdout and "НеСуществует" in r.stdout,
      r.stdout.strip()[:100])

# 10. check --fast
r = subprocess.run([PY, os.path.join(ROOT, "app", "voice_pipeline.py"), "check",
                    "--deck", "Тест100", "--fast"],
                   env=ENV, capture_output=True, text=True, timeout=300)
first = (r.stdout or "").strip().splitlines()[0] if r.stdout.strip() else ""
check("check --fast выполняется", r.returncode in (0, 1), first)

print("\n%s" % ("ВСЁ ХОРОШО" if not fails
                else "ПРОВАЛОВ: %d -> %s" % (len(fails), fails)))
sys.exit(1 if fails else 0)
