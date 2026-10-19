# -*- coding: utf-8 -*-
"""Сквозной тест HTTP-API веб-интерфейса AnkiVoice.

Проверяет не «что страница открылась», а поведение API: что каждая команда
отвечает словами, а не HTTP 500, что негативные сценарии отклоняются
понятно, что SSE отдаёт лог. Запускается к уже поднятому серверу.

    python api_test.py http://127.0.0.1:8794
"""
import json
import os
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


def probe_status(path, timeout=8):
    """Только HTTP-код, тело не читаем.

    Нужно для /api/log: это поток (SSE), который сервер сам не закрывает,
    поэтому обычный req() на нём дойдёт до таймаута и вернёт -1 даже
    на полностью здоровом ответе.
    """
    try:
        with PROXY.open(urllib.request.Request(BASE + path),
                        timeout=timeout) as resp:
            return resp.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        return -1


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
# карточка «Где лежат файлы» заполняется из state, а не только по кнопке
# «Диагностика» — раньше ключа не было и витрина висела пустой.
check("в state есть путь к конфигу", bool(st.get("config_file")),
      st.get("config_file"))

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

print("\n=== сохранение голоса (запись + откат файла) ===")
# API при сохранении дописывает дефолтные параметры (temperature, top_p, …),
# поэтому «откатить» через тот же API нельзя — тест оставлял бы в репозитории
# мусор (hayane получал параметры, которых у него не было). Держим файл
# каким был: снимаем байты до записи и возвращаем их после.
VOICES_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "voices.json")
if voices:
    name = sorted(voices)[0]
    orig = dict(voices[name])
    sent = {"name": name, "ref": orig.get("ref", ""),
            "prompt_text": orig.get("prompt_text", ""),
            "prompt_lang": orig.get("prompt_lang", "ja"),
            "temperature": orig.get("temperature", 0.6),
            "top_p": orig.get("top_p", 0.6),
            "top_k": orig.get("top_k", 20),
            "speed": orig.get("speed", 1.0),
            "seed": orig.get("seed", 42)}
    with open(VOICES_FILE, "rb") as _f:
        raw_before = _f.read()
    code, j = req("/api/voice", sent)
    check("сохранение голоса -> 200", code == 200 and j.get("ok"), (code, j))
    code, st = req("/api/state", timeout=60)
    back = ((st.get("voices") or {}).get(name) or {})
    check("запись дошла до файла",
          code == 200 and back.get("temperature") == sent["temperature"],
          (code, back.get("temperature")))
    with open(VOICES_FILE, "wb") as _f:
        _f.write(raw_before)
    with open(VOICES_FILE, "rb") as _f:
        check("voices.json возвращён байт-в-байт", _f.read() == raw_before, VOICES_FILE)

print("\n=== doctor ===")
code, d = req("/api/doctor", timeout=180)
check("doctor -> 200", code == 200, code)
check("doctor сообщает anki", "anki" in d, d)
check("doctor сообщает пути", "code_dir" in d and "config_file" in d, d)

print("\n=== лог ===")
_, st = req("/api/state", timeout=20)
if st.get("run") or st.get("last"):
    # живой сервер: лог уже есть, поток обязан отвечать 200
    code = probe_status("/api/log?since=0")
    check("лог при существующем запуске отвечает 200", code == 200, code)
else:
    # свежий сервер: лога нет, нужен понятный 404, а не 500
    code, j = req("/api/log?since=0", timeout=5)
    check("лог без запусков отвечает 404 со словом",
          code == 404 and bool(j.get("error")), (code, j))

print("\n" + "=" * 46)
print("Итого: %d OK, %d FAIL" % (len(PASS), len(FAIL)))
for f in FAIL:
    print("  FAIL: %s" % f)
sys.exit(1 if FAIL else 0)
