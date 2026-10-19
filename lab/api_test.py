# -*- coding: utf-8 -*-
"""Сквозной тест HTTP-API веб-интерфейса AnkiVoice.

Проверяет не «что страница открылась», а поведение API: что каждая команда
отвечает словами, а не HTTP 500, что негативные сценарии отклоняются
понятно, что SSE отдаёт лог. Запускается к уже поднятому серверу.

    python api_test.py http://127.0.0.1:8794
"""
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8794"
PROXY = urllib.request.build_opener(urllib.request.ProxyHandler({}))
PASS, FAIL = [], []


def req(path, body=None, timeout=20):
    """Возвращает (http-код, объект). Тело-ошибка кодируется не как исключение."""
    data = None if body is None else json.dumps(body).encode("utf-8")
    r = urllib.request.Request(
        BASE + path, data=data,
        headers={"Content-Type": "application/json"} if data else {})
    try:
        with PROXY.open(r, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", "replace")
            code = resp.status
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        code = e.code
    except Exception as e:
        return -1, {"error": "соединение: %r" % (e,)}
    try:
        return code, json.loads(raw)
    except Exception:
        return code, {"_raw": raw[:200]}


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print("  %-4s %s%s" % ("OK" if cond else "FAIL", name,
                           ("  <- " + str(detail)) if (detail and not cond) else ""))


print("=== страница и статус ===")
code, _ = req("/", timeout=10)
# "/" отдаёт HTML, а не JSON — req вернёт _raw
check("GET / отдаёт HTML", code == 200, code)

code, st = req("/api/state")
check("GET /api/state -> 200", code == 200, code)
check("в state есть папка движка", "path" in st, list(st))
check("в state есть голоса", isinstance(st.get("voices"), dict), st.get("voices"))
check("reading_off подписан", bool(st.get("reading_off")), st.get("reading_off"))

print("\n=== негативные сценарии (должны отвечать словами, не 500) ===")
for name, path, body in [
    ("колода без имени -> 400", "/api/fields", None),
    ("голос без имени -> 400", "/api/voice", {"name": ""}),
    ("неизвестная команда -> 400", "/api/run", {"kind": "wtf"}),
    ("check без колоды -> 400", "/api/run", {"kind": "check"}),
    ("test без голоса -> 400", "/api/run", {"kind": "test"}),
    ("voice без голоса -> 400", "/api/run", {"kind": "voice"}),
    ("глупый путь -> ошибка", "/api/fs?kind=file&path=" +
     urllib.parse.quote("Z:\\нет\\такой"), None),
    ("путь вне диска -> ошибка", "/api/fs?kind=file&path=" +
     urllib.parse.quote("://??"), None),
    ("голос с кривым именем -> 400", "/api/voice/add",
     {"name": "плохое имя", "gpt": "a", "sovits": "b", "ref": "c",
      "prompt_text": "d"}),
]:
    if path.startswith("/api/fields"):
        code, j = req("/api/fields")            # без query -> пустая колода
    else:
        code, j = req(path, body)
    check(name, code in (400, 404) and bool(j.get("error")),
          "код=%s тело=%s" % (code, str(j)[:160]))
    if not j.get("error"):
        print("      тело: %s" % str(j)[:200])

print("\n=== файловый браузер ===")
code, j = req("/api/fs?kind=file&ext=ckpt&path=")
check("корень отдаёт диски", isinstance(j.get("drives"), list) and j["drives"],
      j)
code, j = req("/api/fs?kind=file&ext=ckpt&path=C:\\")
check("C:\\ читается", code == 200 and "dirs" in j, j)

print("\n=== голоса ===")
voices = st.get("voices", {})
check("голосов больше нуля", len(voices) > 0, len(voices))
if voices:
    first = sorted(voices)[0]
    v = voices[first]
    check("у голоса есть gpt/sovits/ref",
          all(k in v for k in ("gpt", "sovits", "ref")), list(v))
    check("флаг files_ok присутствует", "ok" in v, list(v))
    print("      пример: %s -> gpt=%s ref_ok=%s" % (first, v.get("gpt"), v.get("ok")))

print("\n=== сохранение голоса (запись/откат) ===")
if voices:
    name = sorted(voices)[0]
    orig = dict(voices[name])
    code, j = req("/api/voice", {"name": name, "ref": orig.get("ref", ""),
                                 "prompt_text": orig.get("prompt_text", ""),
                                 "prompt_lang": orig.get("prompt_lang", "ja"),
                                 "temperature": orig.get("temperature", 0.6),
                                 "top_p": orig.get("top_p", 0.6),
                                 "top_k": orig.get("top_k", 20),
                                 "speed": orig.get("speed", 1.0),
                                 "seed": orig.get("seed", 42)})
    check("сохранение голоса -> 200", code == 200 and j.get("ok"), (code, j))

print("\n=== doctor ===")
code, d = req("/api/doctor", timeout=180)
check("doctor -> 200", code == 200, code)
check("doctor сообщает anki", "anki" in d, d)
check("doctor сообщает пути", "code_dir" in d and "config_file" in d, d)

print("\n=== незавершённый лог ===")
code, j = req("/api/log?since=0", timeout=5)
check("лог без запусков отвечает 404 со словом",
      code == 404 and bool(j.get("error")), (code, j))

print("\n" + "=" * 46)
print("Итого: %d OK, %d FAIL" % (len(PASS), len(FAIL)))
for f in FAIL:
    print("  FAIL: %s" % f)
sys.exit(1 if FAIL else 0)
