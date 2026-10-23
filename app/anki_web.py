# -*- coding: utf-8 -*-
"""anki_web.py — AnkiVoice: локальный веб-интерфейс пайплайна озвучки.

Почему веб, а не tkinter:
  * живой лог и прогресс потоком (SSE), без мёртвых надписей статуса;
  * вкладки/карточки/тёмная тема рисует браузер — выглядит современно;
  * выбор файлов и папок — модалка внутри страницы, работает везде;
  * сервер слушает ТОЛЬКО 127.0.0.1 — наружу ничего не отдаётся.

Сервер — только stdlib (http.server + threading). Вся работа (синтез, веса,
AnkiConnect) выполняется тем же способом, что и в tkinter-окне: дочерним
процессом voice_pipeline.py из папки GPT-SoVITS (см. anki_gui.pipeline_cmd).
Ничего из логики синтеза здесь не дублируется.

Запуск:
    anki_web.py            — поднять сервер и открыть страницу в браузере
    anki_web.py --no-open  — не открывать браузер (для отладки)
"""

import argparse
import hashlib
import json
import os
import re
import secrets
import socket
import sys
import tempfile
import threading
import time
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# pyruntime собран с safe_path=True: папка скрипта сама в sys.path не
# добавляется. Без этой строки `import anki_gui` падает при любом способе
# запуска — и из папки, и из замороженного exe.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import anki_gui as ag          # переиспользуем конфиг, AnkiConnect, запуск пайплайна
from anki_web_page import HTML

# Ключ этого запуска: страница приложения его знает, чужие страницы — нет.
# Локальный сервер виден любому сайту в браузере, поэтому запросы без
# правильного ключа (или с чужим Origin) отбрасываются.
TOKEN = secrets.token_hex(16)


def page_html():
    """Страница с подставленным ключом запуска."""
    return HTML.replace("__AVTOKEN__", TOKEN)

CREATE_NO_WINDOW = ag.CREATE_NO_WINDOW

READING_OFF = "Не подставлять (движок сам)"

GITHUB_REPO = "Daii1414/AnkiVoice"
GITHUB_API = "https://api.github.com/repos/" + GITHUB_REPO
RELEASES_URL = "https://github.com/" + GITHUB_REPO + "/releases"
GPT_SOVITS_RELEASES = "https://github.com/RVC-Boss/GPT-SoVITS/releases"
INDEXTTS_RELEASES = "https://github.com/index-tts/index-tts"
ANKI_CONNECT_CODE = "2055492159"
ANKI_CONNECT_URL = "https://ankiweb.net/shared/info/" + ANKI_CONNECT_CODE
UPDATE_TTL = 300                    # секунд; кнопка «Проверить» обходит кэш


# ============================================================ состояние запуска
class Run(object):
    """Один запущенный пайплайн: накапливает строки и прогресс."""

    def __init__(self, title, args):
        self.id = "%d" % int(time.time() * 1000)
        self.title = title
        self.args = list(args)
        self.lines = []
        self.cond = threading.Condition()
        self.running = True
        self.code = None
        self.proc = None
        self.total = None      # операций к озвучке (если пайплайн сообщил)
        self.done_n = 0
        self.failed = 0

    def push(self, line):
        self._note(line)
        with self.cond:
            self.lines.append(line)
            self.cond.notify_all()

    def _note(self, line):
        m = re.search(r"К озвучке:\s*(\d+)", line)
        if m:
            self.total = int(m.group(1))
        if line.startswith("OK   ["):
            self.done_n += 1
        elif line.startswith("FAIL ["):
            self.failed += 1

    def finish(self, code):
        with self.cond:
            self.running = False
            self.code = code
            self.cond.notify_all()

    def snapshot(self):
        return {
            "id": self.id, "title": self.title, "args": self.args,
            "running": self.running, "code": self.code,
            "total": self.total, "done": self.done_n, "failed": self.failed,
            "nlines": len(self.lines),
        }


STATE_LOCK = threading.Lock()
CURRENT = None          # type: Run | None
LAST_RUN = None         # последний завершённый — чтобы лог не пропадал


def _mode_ru(mode):
    """Режим чтения словами: в журнале не должно быть ключей конфига."""
    return {"both": "слово + предложение", "sentence": "только предложение",
            "expression": "только слово"}.get(mode, mode)


def _voice_ru(name):
    """Имя голоса для журнала — то же, что человек видит в списке."""
    if not name:
        return "по умолчанию"
    try:
        v = read_voices_file().get("voices", {}).get(name) or {}
    except Exception:
        v = {}
    return v.get("display") or name


def _run_headline(args):
    """Первая строка журнала — по-человечески, а не флагами командной строки."""
    if not args:
        return "Запуск"
    if args[0] == "voice":
        def val(flag):
            return args[args.index(flag) + 1] if flag in args else ""

        deck = val("--deck")
        voice = _voice_ru(val("--voice"))
        mode = _mode_ru(val("--mode") or "both")
        limit = val("--limit")
        what = ("лимит %s карточек" % limit) if limit else "вся колода"
        return ("Начинаю озвучку: колода «%s», голос «%s», режим «%s», %s."
                % (deck, voice, mode, what))
    return "» " + " ".join(args)


def start_run(title, args, on_line=None):
    """Запускает пайплайн. Возвращает (run, error)."""
    global CURRENT, LAST_RUN
    if not args:
        return None, "Не собрались аргументы запуска — проверь выбор голоса и колоды."
    cfg = ag.load_config()
    kind = ag.engine_kind(cfg)
    if kind == ag.ENGINE_INDEX:
        # IndexTTS: нужна его папка, а питон движка GPT-SoVITS — только ради
        # QC и проверки произношения (если его нет, работаем на встроенном
        # рантайме приложения: акустическая проверка останется, а распознавание
        # произношения — нет).
        path = (cfg.get("indextts_path") or "").strip()
        if not path:
            auto = ag.find_indextts_automatic()
            if auto:
                path = auto
        if not path:
            return None, ("Не указана папка IndexTTS — укажи её во вкладке "
                          "«Приложение».")
        problems = ag.validate_indextts(path)
        if problems:
            return None, ("Папка IndexTTS не подходит:\n  • "
                          + "\n  • ".join(problems))
        gpt_path = (cfg.get("gptsovits_path") or "").strip()
        if not os.path.isfile(os.path.join(gpt_path, "runtime", "python.exe")):
            gpt_path = ""
    else:
        path = (cfg.get("gptsovits_path") or "").strip()
        if not path:
            auto = ag.find_gptsovits_automatic()
            if auto:
                path = auto
        if not path:
            return None, ("Не указана папка GPT-SoVITS — укажи её во вкладке "
                          "«Приложение».")
        problems = ag.validate_gptsovits(path)
        if problems:
            return None, ("Папка GPT-SoVITS не подходит:\n  • "
                          + "\n  • ".join(problems))
        gpt_path = path

    with STATE_LOCK:
        if CURRENT and CURRENT.running:
            return None, "Уже идёт операция «%s» — дождись её конца." % CURRENT.title
        run = Run(title, args)
        CURRENT = run

    run.push(_run_headline(args))

    def _line(line):
        run.push(line)
        if on_line:
            on_line(line)

    def _done(code):
        # важно: присваивание во вложенной функции создаёт ЛОКАЛЬНУЮ
        # переменную, если не объявить global здесь (global в start_run на
        # эту вложенную функцию не действует) — и lastRun оставался None.
        global LAST_RUN
        run.finish(code)
        LAST_RUN = run

    try:
        r = ag.pipeline_cmd(gpt_path, args, _line, _done)
    except Exception as e:
        run.finish(-1)
        run.push("!! Ошибка запуска: %r" % (e,))
        return None, "Не удалось запустить пайплайн: %r" % (e,)

    with STATE_LOCK:
        run.proc = r
    return run, None


def stop_run():
    with STATE_LOCK:
        run = CURRENT
    if not run or not run.running:
        return False
    h = run.proc
    if h and h.stop():
        run.push("⏹ Процесс остановлен вручную.")
        return True
    return False


def current_run():
    with STATE_LOCK:
        return CURRENT


# ================================================================== справочники
def guess_fields(fl):
    """Автоподбор полей колоды — логика та же, что в anki_gui._guess_fields."""
    low = [x.lower() for x in fl]

    def find(pred, default=""):
        for x, l in zip(fl, low):
            if pred(l):
                return x
        return default

    sent_src = find(lambda l: l == "sentence" or ("sentence" in l and "audio" not in l),
                    fl[0] if fl else "")
    sent_aud = find(lambda l: "sentence" in l and "audio" in l, "")
    word_src = find(lambda l: l in ("expression", "word", "front")
                    or ("expression" in l and "audio" not in l
                        and "reading" not in l and "furigana" not in l),
                    fl[0] if fl else "")
    word_aud = find(lambda l: ("expression" in l or "word" in l) and "audio" in l, "")
    furi = find(lambda l: l == "expressionfurigana"
                or ("furigana" in l and "sentence" not in l)
                or ("reading" in l and "expression" in l), "")
    return {"sentence_src": sent_src, "sentence_audio": sent_aud,
            "word_src": word_src, "word_audio": word_aud,
            "furigana_src": furi}


def deck_fields(deck):
    """Поля карточек колоды + автоподбор ролей.

    Нужно, чтобы озвучка работала, даже если пользователь не заходил
    на вкладку «Поля колоды»: пустые имена полей подставляются по
    фактическим полям выбранной колоды, а не остаются пустыми.
    """
    try:
        fl = ag.list_note_fields(deck)
    except Exception:
        return [], {}
    return fl, (guess_fields(fl) if fl else {})


def pron_status():
    """(доступно ли, описание) — проверка произношения через faster-whisper.

    Смотрим по файлам: в питоне движка есть ли faster-whisper и есть ли
    скачанная модель. Саму модель грузит пайплайн (он и так живёт
    в питоне движка).
    """
    try:
        # lab/ лежит рядом с кодом (в установленном виде) или на уровень выше
        # (в репозитории) — тот же порядок поиска, что и в voice_pipeline.
        lab = None
        for p in (os.path.join(ag.code_dir(), "lab"),
                  os.path.join(ag.repo_root(), "lab")):
            if os.path.isdir(p):
                lab = p
                break
        if lab is None:
            return False, "не найдена папка lab/ с модулями проверки"
        if lab not in sys.path:
            sys.path.insert(0, lab)
        import pron_check
    except Exception as e:
        return False, ("модуль проверки не импортируется (%s)"
                       % (repr(e)[:80],))
    cfg = ag.load_config()
    eng = (cfg.get("gptsovits_path") or "").strip()
    if not eng:
        return False, "не указана папка GPT-SoVITS"
    site = os.path.join(eng, "runtime", "Lib", "site-packages")
    try:
        has_fw = any(n.lower().startswith("faster_whisper")
                     for n in os.listdir(site))
    except OSError:
        has_fw = False
    if not has_fw:
        return False, "в питоне движка нет faster-whisper"
    models = pron_check.cached_models()
    if not models:
        return False, "нет скачанной модели faster-whisper"
    return True, models[0][0]


def read_voices_file():
    p = os.path.join(ag.code_dir(), "voices.json")
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"voices": {}}


def _read_last_run():
    """Итог последнего прогона (пишет voice_pipeline в %APPDATA%/AnkiVoice).

    Путь дублируется намеренно: веб-слой не импортирует voice_pipeline
    (тяжёлый и не нужен ему целиком), а файл — простой JSON.
    """
    p = os.path.join(os.environ.get("APPDATA") or "",
                     "AnkiVoice", "last_run.json")
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return {}


def write_voices_file(cfg):
    p = os.path.join(ag.code_dir(), "voices.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def store_path(p, eng):
    """Относительный путь, если файл лежит внутри папки движка (как в GUI)."""
    if not p:
        return ""
    p = os.path.expanduser(p)
    try:
        if eng and os.path.commonpath(
                [os.path.abspath(p), os.path.abspath(eng)]) == os.path.abspath(eng):
            return os.path.relpath(p, eng)
    except Exception:
        pass
    return p


def resolve_path(p, eng):
    """Путь к файлу голоса.

    Относительный путь ищем в папке движка, а если там файла нет — в папке
    другого движка: у IndexTTS голос — это референс, а референсы часто
    лежат в папке GPT-SoVITS (там их нашли при сканировании).
    """
    if not p:
        return ""
    p = os.path.expanduser(p)
    if os.path.isabs(p):
        return p
    first = os.path.normpath(os.path.join(eng or "", p))
    if os.path.exists(first):
        return first
    cfg = ag.load_config() or {}
    idx = (cfg.get("indextts_path") or "").strip()
    other = (cfg.get("gptsovits_path") or "").strip() if eng == idx \
        else (cfg.get("indextts_path") or "").strip()
    if other:
        alt = os.path.normpath(os.path.join(other, p))
        if os.path.exists(alt):
            return alt
    return first


def voice_files_ok(v, eng):
    # У IndexTTS голос — это один референс: весов модели (.ckpt/.pth) у
    # голоса нет, они общие у движка.
    keys = ("ref",) if ag.engine_kind() == ag.ENGINE_INDEX else ("gpt", "sovits", "ref")
    for key in keys:
        p = v.get(key, "")
        if not p or not os.path.exists(resolve_path(p, eng)):
            return False
    return True


# ================================================================ мастер настройки
def _test_audio(voice):
    if not voice or not re.match(r"^[\w\-.]+$", voice):
        return ""
    for ext in ("ogg", "wav"):
        p = os.path.join(ag.code_dir(), "test_%s.%s" % (voice, ext))
        if os.path.isfile(p):
            return p
    return ""


def setup_status():
    """Один снимок для мастера: что уже готово и что делать дальше."""
    cfg = ag.load_config()
    kind = ag.engine_kind(cfg)
    is_index = kind == ag.ENGINE_INDEX
    if is_index:
        path = (cfg.get("indextts_path") or "").strip()
        auto = ""
        if not path:
            auto = ag.find_indextts_automatic() or ""
            if auto:
                path = auto
        problems = ag.validate_indextts(path) if path else ["Папка IndexTTS не указана"]
    else:
        path = (cfg.get("gptsovits_path") or "").strip()
        auto = ""
        if not path:
            auto = ag.find_gptsovits_automatic() or ""
            if auto:
                path = auto
        problems = ag.validate_gptsovits(path) if path else ["Папка GPT-SoVITS не указана"]

    vfile = read_voices_file()
    voices = vfile.get("voices", {})
    rows, ready = [], []
    need_keys = ("ref",) if is_index else ("gpt", "sovits", "ref")
    for name, v in sorted(voices.items()):
        missing = []
        for key in need_keys:
            p = v.get(key, "")
            if not p or not os.path.exists(resolve_path(p, path)):
                missing.append(key)
        ok = not missing
        rows.append({
            "name": name,
            "display": v.get("display") or name,
            "ok": ok,
            "missing": missing,
        })
        if ok:
            ready.append(name)

    default = vfile.get("default_voice") or ""
    last_test = (cfg.get("last_test_voice") or "").strip()
    test_voice = (last_test if last_test in ready else
                  (default if default in ready else (ready[0] if ready else "")))
    test_path = _test_audio(test_voice)
    if not test_path and not last_test:
        for name in ready:
            p = _test_audio(name)
            if p:
                test_voice, test_path = name, p
                break
    anki_ok = ag.anki_status()
    server_ok = ag.tts_status()
    engine_ok = bool(path) and not problems
    # Для работы нужны три вещи: движок на месте, Anki отвечает и есть хоть
    # один голос с полным набором файлов. Тестовая фраза необязательна:
    # без неё озвучка всё равно работает, поэтому она не решает, готов ли
    # мастер — иначе он ругался бы на каждом запуске.
    core = engine_ok and anki_ok and bool(ready)
    done = bool(cfg.get("setup_done"))
    complete = core and done

    return {
        "version": ag.APP_VERSION,
        "complete": complete,
        "core": core,
        "done": done,
        "engine": {
            "ok": engine_ok,
            "kind": kind,
            "path": path,
            "auto": auto,
            "problems": problems,
            "expected": ("checkpoints\\config.yaml и .venv"
                         if is_index else "runtime\\python.exe и api_v2.py"),
            "download_url": (INDEXTTS_RELEASES if is_index
                             else GPT_SOVITS_RELEASES),
            "hint": (("Поставь IndexTTS 2.5: git clone "
                      "https://github.com/index-tts/index-tts, затем "
                      "uv sync --extra webui и скачай веса в checkpoints. "
                      "Папку укажи здесь.")
                     if is_index else
                     ("Скачай Windows-пакет GPT-SoVITS v2Pro со страницы релизов, "
                      "распакуй в папку без кириллицы (например, D:\\GPT-SoVITS) "
                      "и укажи её здесь. Внутри должны лежать runtime\\python.exe "
                      "и api_v2.py.")),
        },
        "anki": {
            "ok": anki_ok,
            "code": ANKI_CONNECT_CODE,
            "url": ANKI_CONNECT_URL,
            "hint": ("Открой Anki → Инструменты → Дополнения → Получить "
                     "дополнения, вставь код %s, перезапусти Anki." % ANKI_CONNECT_CODE),
        },
        "server": {
            "ok": server_ok,
            "hint": ("Первый запуск движка занимает 1–2 минуты: он грузит "
                     "веса и CUDA. Дальше сервер поднимается сам."),
        },
        "voices": {
            "ok": bool(ready),
            "ready": ready,
            "all": rows,
            "default": default,
            "hint": ("Нет ни одного голоса с полным набором файлов. "
                     "Открой вкладку «Голос»: добавь голос или нажми "
                     "«Обновить веса в движке»."),
        },
        "test": {
            "ok": bool(test_path),
            "voice": test_voice,
            "display": (voices.get(test_voice) or {}).get("display") or test_voice,
            "path": test_path,
            "url": ("/api/audio?voice=" + urllib.parse.quote(test_voice)
                    if test_voice else ""),
            "text": "既存建築物の改修では、耐火性能と耐震性能の確認が重要です。",
        },
    }


# ============================================================== обновления
UPDATE_LOCK = threading.Lock()
UPDATE = {
    "phase": "idle",          # idle | downloading | verifying | done | error
    "received": 0,
    "total": 0,
    "error": "",
    "path": "",
    "expected": "",
    "actual": "",
    "tag": "",
    "asset": "",
}
UPDATE_CACHE = {"at": 0.0, "data": None}


def _github_json(url, timeout=30):
    req = urllib.request.Request(url, headers={
        "User-Agent": "AnkiVoice/" + ag.APP_VERSION,
        "Accept": "application/vnd.github+json",
    })
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def release_info(force=False):
    """Последний стабильный релиз GitHub + выбранный установщик и SHA256."""
    now = time.time()
    with UPDATE_LOCK:
        if (not force and UPDATE_CACHE["data"]
                and now - UPDATE_CACHE["at"] < UPDATE_TTL):
            return UPDATE_CACHE["data"]
    rel = _github_json(GITHUB_API + "/releases/latest")
    tag = (rel.get("tag_name") or "").strip()
    latest = tag[1:] if tag.lower().startswith("v") else tag
    body = rel.get("body") or ""
    asset = None
    for a in rel.get("assets") or []:
        if re.match(r"^AnkiVoice-Setup-[0-9A-Za-z._-]+\.exe$",
                    a.get("name") or ""):
            asset = a
            break
    sha = ""
    if asset:
        digest = (asset.get("digest") or "").strip().lower()
        if digest.startswith("sha256:"):
            sha = digest[7:]
    if not sha:
        m = re.search(r"SHA256[^\n:]*[:\s]+([0-9a-fA-F]{64})", body)
        if m:
            sha = m.group(1)
    data = {
        "ok": True,
        "current": ag.APP_VERSION,
        "tag": tag,
        "latest": latest,
        "available": ag.version_tuple(latest) > ag.version_tuple(ag.APP_VERSION),
        "name": rel.get("name") or tag,
        "body": body[:20000],
        "url": rel.get("html_url") or RELEASES_URL,
        "published": rel.get("published_at") or "",
        "asset": ({"name": asset.get("name"), "size": asset.get("size") or 0,
                   "url": asset.get("browser_download_url") or "",
                   "sha256": sha} if asset else None),
        "checked_at": int(now),
    }
    with UPDATE_LOCK:
        UPDATE_CACHE["at"] = now
        UPDATE_CACHE["data"] = data
    return data


def update_snapshot():
    with UPDATE_LOCK:
        d = dict(UPDATE)
    if d["total"]:
        d["percent"] = min(100, int(d["received"] * 100 / d["total"]))
    else:
        d["percent"] = 0
    return d


def _update_set(**kw):
    with UPDATE_LOCK:
        UPDATE.update(kw)


def start_update_download():
    with UPDATE_LOCK:
        if UPDATE["phase"] in ("checking", "downloading", "verifying"):
            # снимок собираем здесь же: update_snapshot() берёт тот же
            # нереентерабельный UPDATE_LOCK и повесил бы поток навсегда
            d = dict(UPDATE)
            d["percent"] = (min(100, int(d["received"] * 100 / d["total"]))
                            if d["total"] else 0)
            return d, None
        # ставим фазу ДО сетевого запроса: два быстрых клика иначе могли
        # запустить два потока, пишущих в один .part
        UPDATE.update(phase="checking", received=0, total=0, error="",
                      path="", expected="", actual="", tag="", asset="")
    try:
        info = release_info()
    except Exception as e:
        _update_set(phase="error", error="Не удалось проверить обновления: %s" % (e,))
        return None, "Не удалось проверить обновления: %s" % (e,)
    if not info.get("available"):
        _update_set(phase="idle")
        return None, "Установленная версия уже последняя."
    asset = info.get("asset") or {}
    if not asset.get("url"):
        _update_set(phase="error",
                    error="В релизе нет установщика AnkiVoice-Setup-*.exe.")
        return None, "В релизе нет установщика AnkiVoice-Setup-*.exe."
    expected = (asset.get("sha256") or "").lower()
    if not re.match(r"^[0-9a-f]{64}$", expected):
        msg = ("В релизе нет SHA256 установщика — скачивание "
               "без проверки запрещено.")
        _update_set(phase="error", error=msg)
        return None, msg
    name = os.path.basename(asset.get("name") or "")
    if not re.match(r"^AnkiVoice-Setup-[0-9A-Za-z._-]+\.exe$", name):
        safe = re.sub(r"[^0-9A-Za-z._-]+", "_",
                      info["tag"] or info["latest"])
        name = "AnkiVoice-Setup-%s.exe" % safe
    path = os.path.join(tempfile.gettempdir(), name)
    _update_set(phase="downloading", received=0,
                total=int(asset.get("size") or 0), error="", path="",
                expected=expected, actual="", tag=info["tag"],
                asset=asset.get("name") or name)
    threading.Thread(target=_download_update,
                     args=(asset["url"], path, expected, int(asset.get("size") or 0)),
                     daemon=True).start()
    return update_snapshot(), None


def _download_update(url, path, expected, size):
    part = path + ".part"
    try:
        if urllib.parse.urlparse(url).scheme != "https":
            raise RuntimeError("ссылка на установщик не HTTPS")
        req = urllib.request.Request(url, headers={
            "User-Agent": "AnkiVoice/" + ag.APP_VERSION})
        h = hashlib.sha256()
        got = 0
        with urllib.request.urlopen(req, timeout=120) as r:
            total = int(r.headers.get("Content-Length") or 0) or size
            _update_set(total=total or 0)
            with open(part, "wb") as f:
                while True:
                    chunk = r.read(256 * 1024)
                    if not chunk:
                        break
                    f.write(chunk)
                    h.update(chunk)
                    got += len(chunk)
                    with UPDATE_LOCK:
                        UPDATE["received"] = got
        actual = h.hexdigest()
        _update_set(phase="verifying", actual=actual,
                    received=got, total=got)
        if actual.lower() != expected.lower():
            raise RuntimeError("SHA256 не совпал: ожидался %s, получен %s"
                               % (expected, actual))
        os.replace(part, path)
        _update_set(phase="done", path=path, actual=actual, error="")
    except Exception as e:
        try:
            if os.path.exists(part):
                os.remove(part)
        except Exception:
            pass
        _update_set(phase="error", error=str(e)[:800])


def launch_update():
    with UPDATE_LOCK:
        path = UPDATE.get("path") or ""
        expected = UPDATE.get("expected") or ""
    if not path or not os.path.isfile(path):
        return False, "Установщик ещё не скачан."
    if not re.match(r"^[0-9a-f]{64}$", expected):
        return False, "Нет ожидаемого SHA256 — запуск запрещён."
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    if h.hexdigest().lower() != expected:
        return False, "Файл изменился после скачивания — SHA256 не совпал."
    try:
        os.startfile(path)
    except Exception as e:
        return False, "Не удалось открыть установщик: %r" % (e,)
    return True, None


# ================================================================== файловый
# модальный выбор файлов внутри страницы (в вебе нет системного диалога)
FS_EXTS = {
    "ckpt": (".ckpt",), "pth": (".pth",),
    "audio": (".wav", ".mp3", ".flac", ".m4a", ".ogg", ".opus"),
}


def fs_list(path, kind, exts):
    path = path or ""
    if not path:
        # корень: буквы дисков
        drives = ["%s:\\" % c for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
                  if os.path.exists("%s:\\" % c)]
        return {"path": "", "parent": "", "drives": drives,
                "dirs": [], "files": [], "kind": kind}
    path = os.path.abspath(os.path.expanduser(path))
    if not os.path.isdir(path):
        return {"error": "Это не папка: %s" % path}
    try:
        names = sorted(os.listdir(path), key=lambda s: s.lower())
    except Exception as e:
        return {"error": "Не удалось прочитать папку: %r" % (e,)}
    dirs, files = [], []
    for n in names:
        if n.startswith("."):
            continue
        full = os.path.join(path, n)
        if os.path.isdir(full):
            dirs.append(n)
        elif kind == "dir":
            pass
        else:
            if not exts or n.lower().endswith(tuple(exts)):
                files.append(n)
    parent = os.path.dirname(path.rstrip("\\/")) if os.path.dirname(path) != path else ""
    return {"path": path, "parent": parent, "drives": [], "dirs": dirs,
            "files": files, "kind": kind}


# ================================================================== HTTP-обработчик
class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass                        # консоль не засоряем

    # ------------------------------------------------------------- ответы
    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        if not isinstance(body, bytes):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj, ensure_ascii=False))

    def _err(self, msg, code=400, **extra):
        obj = {"error": msg}
        obj.update(extra)
        self._json(obj, code)

    def _guard(self, need_token=True):
        """Пропускаем только наши же запросы.

        Локальный сервер доступен любому сайту, открытому в браузере: без
        проверки источника чужая страница могла бы запустить озвучку,
        скачать обновление или закрыть приложение. Проверяем Host (защита
        от подмены DNS), Origin (защита от запросов с чужого сайта) и
        служебный ключ этого запуска.
        """
        try:
            port = int(self.server.server_address[1])
        except Exception:
            port = 0
        host = (self.headers.get("Host") or "").strip()
        try:
            hname, hport = host.rsplit(":", 1)
            hport = int(hport)
        except Exception:
            hname, hport = host, port
        if hname.lower() not in ("127.0.0.1", "localhost", "[::1]", "::1"):
            self.close_connection = True
            self._err("Запрос отклонён: адрес не локальный", 403)
            return False
        if port and hport != port:
            self._err("Запрос отклонён: порт не тот", 403)
            return False
        origin = (self.headers.get("Origin") or "").strip()
        if origin:
            netloc = urllib.parse.urlparse(origin).netloc.lower()
            try:
                oname, oport = netloc.rsplit(":", 1)
                oport = int(oport)
            except Exception:
                oname, oport = netloc, port
            if oname not in ("127.0.0.1", "localhost", "[::1]", "::1") or \
                    (port and oport != port):
                self.close_connection = True
                self._err("Запрос отклонён: чужой источник", 403)
                return False
        if need_token:
            tok = (self.headers.get("X-AV-Token") or "").strip()
            if not tok:
                # теги <audio>/<img> не умеют слать заголовки — принимаем
                # служебный ключ и в строке запроса
                q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
                tok = (q.get("t") or [""])[0].strip()
            if tok != TOKEN:
                self.close_connection = True
                self._err("Запрос отклонён: нет служебного ключа "
                          "(страница устарела — обновите её, F5)", 403)
                return False
        return True

    def _body(self):
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            n = 0
        raw = self.rfile.read(n) if n else b""
        if not raw:
            return {}
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception:
            return {}

    # ------------------------------------------------------------- GET
    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        # Без ключа отдаём только саму страницу; все /api/* требуют
        # служебный ключ (заголовок или ?t= — для <audio>/<img> и
        # EventSource, которые не умеют заголовки). Раньше GET отдавал
        # конфиг, дерево файловой системы и лог любому локальному процессу.
        if not self._guard(need_token=u.path not in ("/", "/index.html")):
            return
        q = dict(urllib.parse.parse_qsl(u.query))
        path = u.path

        if path in ("/", "/index.html"):
            self._send(200, page_html(), "text/html; charset=utf-8")
            return
        if path == "/api/state":
            self._json(self.api_state())
            return
        if path == "/api/decks":
            self._json({"decks": self._decks()})
            return
        if path == "/api/fields":
            deck = q.get("deck", "")
            if not deck:
                return self._err("Не указана колода")
            fl = ag.list_note_fields(deck)
            self._json({"deck": deck, "fields": fl, "guess": guess_fields(fl)})
            return
        if path == "/api/fs":
            ext = q.get("ext", "")
            exts = FS_EXTS.get(ext, tuple(x for x in ext.split(",") if x)) if ext else ()
            out = fs_list(q.get("path", ""), q.get("kind", "file"), exts)
            # ошибка каталога — это 400, как и в остальных эндпоинтах
            # (раньше отдавалась с кодом 200 и полем error — страница это
            # переживала, но API был неединообразен)
            return self._err(out["error"], 400) if out.get("error") \
                else self._json(out)
        if path == "/api/doctor":
            self._json(self._doctor())
            return
        if path == "/api/setup":
            self._json(setup_status())
            return
        if path == "/api/update/check":
            try:
                self._json(release_info(force=bool(q.get("force"))))
            except Exception as e:
                self._json({"ok": False,
                            "error": "Не удалось проверить обновления: %s" % (e,)},
                           502)
            return
        if path == "/api/update/status":
            self._json(update_snapshot())
            return
        if path == "/api/audio":
            self._audio(q.get("voice", ""))
            return
        if path == "/api/log":
            self._stream(q)
            return
        self._err("Нет такого адреса", 404)

    # ------------------------------------------------------------- POST
    def do_POST(self):
        # тело читаем ДО проверки: иначе при отказе останутся байты в сокете
        # и следующий запрос по тому же соединению разберётся неверно
        b = self._body()
        if not self._guard(need_token=True):
            return
        u = urllib.parse.urlparse(self.path)
        path = u.path

        if path == "/api/config":
            cfg = ag.load_config()
            # --- 1. проверка папки движка ДО записи ---
            # Кнопка «Проверить» ничего не меняет (приходит check_path), а
            # неверную папку мы больше не пишем в конфиг: после этого озвучка
            # невозможна, пока путь не исправят руками.
            if b.get("check_path"):
                key = "indextts_path" if ag.engine_kind(cfg) == ag.ENGINE_INDEX \
                    else "gptsovits_path"
                p = (b.get(key) or "").strip()
                if not p:
                    self._json({"ok": True, "problems": [], "saved": False})
                    return
                probs = ag.validate_indextts(p) if key == "indextts_path" \
                    else ag.validate_gptsovits(p)
                self._json({"ok": not probs, "problems": probs, "saved": False})
                return
            for key in ("gptsovits_path", "indextts_path"):
                if key in b:
                    p = (b.get(key) or "").strip()
                    if not p:
                        continue          # пустую папку разрешаем (движок ищется сам)
                    probs = ag.validate_indextts(p) if key == "indextts_path" \
                        else ag.validate_gptsovits(p)
                    if probs:
                        self._json({"ok": False, "problems": probs,
                                    "saved": False})
                        return
            if "gptsovits_path" in b:
                old = (cfg.get("gptsovits_path") or "").strip()
                new = (b.get("gptsovits_path") or "").strip()
                if new != old:
                    cfg["setup_done"] = False
            if "indextts_path" in b:
                old = (cfg.get("indextts_path") or "").strip()
                new = (b.get("indextts_path") or "").strip()
                if new != old:
                    cfg["setup_done"] = False
            if "engine" in b and (b.get("engine") or "") != (cfg.get("engine") or ""):
                cfg["setup_done"] = False
            for k in ("gptsovits_path", "indextts_path", "indextts_url", "engine",
                      "engine_confirmed", "theme", "deck", "voice", "mode",
                      "sentence_src", "sentence_audio", "word_src",
                      "word_audio", "furigana_src", "reading", "limit",
                      "verify_pronunciation", "asr_model", "lang"):
                if k in b:
                    v = b[k]
                    if isinstance(v, str):
                        # NUL-байт ломает пайплайн (embedded null character)
                        v = v.replace("\x00", "")
                    cfg[k] = v
            # настройки полей — ещё и в профиль колоды: у разных колод
            # названия полей разные
            field_keys = ("sentence_src", "sentence_audio", "word_src",
                          "word_audio", "furigana_src", "reading")
            pdeck = (b.get("profile_deck") or b.get("deck") or "").strip()
            if pdeck and any(k in b for k in field_keys):
                profs = cfg.setdefault("profiles", {})
                prof = profs.setdefault(pdeck, {})
                for k in field_keys:
                    if k in b:
                        prof[k] = b[k]
            ag.save_config(cfg)
            # сразу проверяем папку ВЫБРАННОГО движка — говорим, что не так
            if ag.engine_kind(cfg) == ag.ENGINE_INDEX:
                p = (cfg.get("indextts_path") or "").strip()
                problems = ag.validate_indextts(p) if p else ["папка не указана"]
                auto = ag.find_indextts_automatic() if problems else ""
            else:
                p = (cfg.get("gptsovits_path") or "").strip()
                problems = ag.validate_gptsovits(p) if p else ["папка не указана"]
                auto = ag.find_gptsovits_automatic() if problems else ""
            self._json({"ok": True, "problems": problems, "auto": auto})
            return

        if path == "/api/voice":
            return self._save_voice(b)

        if path == "/api/voice/add":
            return self._add_voice(b)

        if path == "/api/run":
            return self._run(b)

        if path == "/api/stop":
            ok = stop_run()
            self._json({"ok": ok, "error": None if ok else "Нечего останавливать"})
            return

        if path == "/api/setup/server":
            cfg = ag.load_config()
            if ag.engine_kind(cfg) == ag.ENGINE_INDEX:
                eng = (cfg.get("indextts_path") or "").strip() or \
                    (ag.find_indextts_automatic() or "")
                if not eng:
                    return self._err("Сначала укажи папку IndexTTS.")
                problems = ag.validate_indextts(eng)
                if problems:
                    return self._err("Папка IndexTTS не подходит: "
                                     + "; ".join(problems))
                if ag.tts_status():
                    return self._json({"ok": True, "already": True,
                                       "message": "Сервис IndexTTS уже запущен."})
                run, err = start_run("Подготовка сервиса IndexTTS",
                                     ["indextts-server", "--wait", "900"])
                if err:
                    return self._err(err)
                return self._json({"ok": True, "run": run.snapshot()})
            eng = (cfg.get("gptsovits_path") or "").strip() or \
                (ag.find_gptsovits_automatic() or "")
            if not eng:
                return self._err("Сначала укажи папку GPT-SoVITS.")
            problems = ag.validate_gptsovits(eng)
            if problems:
                return self._err("Папка GPT-SoVITS не подходит: "
                                 + "; ".join(problems))
            if ag.tts_status():
                return self._json({"ok": True, "already": True,
                                   "message": "Сервер уже запущен."})
            run, err = start_run("Подготовка сервера GPT-SoVITS",
                                 ["server", "--wait", "600"])
            if err:
                return self._err(err)
            return self._json({"ok": True, "run": run.snapshot()})

        if path == "/api/setup/done":
            st = setup_status()
            if not st["engine"]["ok"]:
                return self._err("Сначала укажи рабочую папку GPT-SoVITS.")
            if not st["anki"]["ok"]:
                return self._err("Сначала подключи AnkiConnect.")
            if not st["voices"]["ok"]:
                return self._err("Сначала добавь голос с весами и референсом.")
            voice = (b.get("voice") or st["test"]["voice"] or "").strip()
            if not voice or not _test_audio(voice):
                return self._err("Сначала синтезируй тестовую фразу выбранным голосом.")
            cfg = ag.load_config()
            cfg["setup_done"] = True
            cfg["last_test_voice"] = voice
            ag.save_config(cfg)
            return self._json({"ok": True, "setup": setup_status()})

        if path == "/api/setup/reset":
            cfg = ag.load_config()
            cfg["setup_done"] = False
            cfg.pop("last_test_voice", None)
            ag.save_config(cfg)
            return self._json({"ok": True, "setup": setup_status()})

        if path == "/api/update/download":
            snap, err = start_update_download()
            if err:
                return self._err(err)
            return self._json({"ok": True, "update": snap})

        if path == "/api/update/run":
            ok, err = launch_update()
            if not ok:
                return self._err(err)
            return self._json({"ok": True})

        if path == "/api/shutdown":
            self._json({"ok": True})
            stop_run()      # гасим и дочерний пайплайн, иначе он останется
            threading.Thread(target=self.server.shutdown, daemon=True).start()
            return

        self._err("Нет такого адреса", 404)

    # ------------------------------------------------------------- данные
    def _decks(self):
        if not ag.anki_status():
            return []
        try:
            return [list(x) for x in ag.list_decks()]
        except Exception:
            return []

    def api_state(self):
        cfg = ag.load_config()
        kind = ag.engine_kind(cfg)
        # Папка движка — по ВЫБРАННОМУ движку: от неё зависят и пути голосов.
        # Раньше считалась папка GPT-SoVITS, и при IndexTTS голоса выглядели
        # готовыми, хотя референс искался не там.
        if kind == ag.ENGINE_INDEX:
            path = (cfg.get("indextts_path") or "").strip() or \
                (ag.find_indextts_automatic() or "")
            problems = ag.validate_indextts(path) if path else ["Папка IndexTTS не указана"]
            auto = ""
        else:
            path = (cfg.get("gptsovits_path") or "").strip() or \
                (ag.find_gptsovits_automatic() or "")
            problems = ag.validate_gptsovits(path) if path else ["Папка GPT-SoVITS не указана"]
            auto = ""
            if not (cfg.get("gptsovits_path") or "").strip():
                auto = ag.find_gptsovits_automatic() or ""

        vfile = read_voices_file()
        voices = vfile.get("voices", {})
        eng = path
        view = {}
        for name, v in voices.items():
            d = dict(v)
            d["ok"] = voice_files_ok(v, eng)
            view[name] = d

        run = current_run()
        return {
            "cfg": cfg,
            "engine": kind,
            "version": ag.APP_VERSION,
            "pron": dict(zip(("ok", "msg"), pron_status())),
            "setup_done": bool(cfg.get("setup_done")),
            "path": path,
            "auto": auto,
            "problems": problems,
            "voices": view,
            "default_voice": vfile.get("default_voice"),
            "anki": ag.anki_status(),
            "tts": ag.tts_status(),
            "code_dir": ag.code_dir(),
            "config_file": ag.CONFIG_FILE,
            "anki_media": ag.anki_media_folder(),
            "log_file": ag.CRASH_LOG,
            "run": run.snapshot() if run else None,
            "last": (LAST_RUN.snapshot() if LAST_RUN and not LAST_RUN.running
                     else None),
            "last_run": _read_last_run(),
            "reading_off": READING_OFF,
        }

    def _doctor(self):
        cfg = ag.load_config()
        kind = ag.engine_kind(cfg)
        if kind == ag.ENGINE_INDEX:
            path = (cfg.get("indextts_path") or "").strip() or \
                (ag.find_indextts_automatic() or "")
            problems = ag.validate_indextts(path) if path else ["Папка IndexTTS не указана"]
            label = "IndexTTS 2.5"
        else:
            path = (cfg.get("gptsovits_path") or "").strip() or \
                (ag.find_gptsovits_automatic() or "")
            problems = ag.validate_gptsovits(path) if path else ["Папка GPT-SoVITS не указана"]
            label = "GPT-SoVITS"
        rep = {
            "code_dir": ag.code_dir(),
            "config_file": ag.CONFIG_FILE,
            "engine": kind,
            "engine_label": label,
            "engine_path": path,
            "gptsovits_path": path,
            "local_problems": ag.validate_local(),
            "problems": problems,
            "anki": ag.anki_status(),
            "tts_server": ag.tts_status(),
            "anki_media": ag.anki_media_folder(),
            "log_file": ag.CRASH_LOG,
        }
        if path and not rep["problems"]:
            voices, default = ag.load_voices()
            rep["voices"] = sorted(voices)
            rep["default_voice"] = default
        rep["ok"] = (not rep["problems"] and not rep["local_problems"]
                     and rep["anki"])
        return rep

    def _audio(self, voice):
        if not voice or not re.match(r"^[\w\-.]+$", voice):
            return self._err("Плохое имя голоса")
        for ext in ("ogg", "wav"):
            p = os.path.join(ag.code_dir(), "test_%s.%s" % (voice, ext))
            if os.path.isfile(p):
                with open(p, "rb") as f:
                    data = f.read()
                ctype = ("audio/ogg" if ext == "ogg" else "audio/wav")
                self._send(200, data, ctype)
                return
        self._err("Файла теста ещё нет — нажми «Прослушать»", 404)

    # ------------------------------------------------------------- лог (SSE)
    def _stream(self, q):
        run = current_run()
        if run is None:
            # отдаём последний завершённый — чтобы лог не пропадал при
            # перезагрузке страницы
            run = LAST_RUN
        if run is None:
            return self._err("Лога ещё нет", 404)
        try:
            since = int(q.get("since", 0))
        except ValueError:
            since = 0

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "keep-alive")
        self.end_headers()

        try:
            while True:
                with run.cond:
                    if since >= len(run.lines) and run.running:
                        run.cond.wait(15)      # keep-alive вместо пустого кадра
                    batch = run.lines[since:]
                    since += len(batch)
                    finished = not run.running and since >= len(run.lines)
                if batch:
                    for line in batch:
                        payload = json.dumps({"line": line}, ensure_ascii=False)
                        self.wfile.write(("data: %s\n\n" % payload).encode("utf-8"))
                    self.wfile.flush()
                elif not finished:
                    self.wfile.write(b": ping\n\n")
                    self.wfile.flush()
                if finished:
                    snap = run.snapshot()
                    payload = json.dumps({"done": snap}, ensure_ascii=False)
                    self.wfile.write(("data: %s\n\n" % payload).encode("utf-8"))
                    self.wfile.flush()
                    break
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass                            # страницу закрыли — это нормально

    # ------------------------------------------------------------- команды
    def _save_voice(self, b):
        name = (b.get("name") or "").strip()
        if not name:
            return self._err("Не выбран голос")
        cfg = read_voices_file()
        v = dict(cfg.get("voices", {}).get(name, {}))
        eng = (ag.load_config().get("gptsovits_path") or "")
        v["ref"] = store_path((b.get("ref") or "").strip(), eng)
        v["prompt_text"] = (b.get("prompt_text") or "") if not b.get("noref") else ""
        v["prompt_lang"] = (b.get("prompt_lang") or "ja").strip() or "ja"
        v["aux"] = [store_path(a, eng) for a in (b.get("aux") or []) if a]
        try:
            v["temperature"] = round(float(b.get("temperature", 0.6)), 2)
            v["top_p"] = round(float(b.get("top_p", 0.6)), 2)
            v["top_k"] = int(round(float(b.get("top_k", 20))))
            v["speed"] = round(float(b.get("speed", 1.0)), 2)
            v["seed"] = int(b.get("seed", 42))
        except (TypeError, ValueError):
            return self._err("Проверь числовые значения sampling")
        cfg.setdefault("voices", {})[name] = v
        write_voices_file(cfg)
        self._json({"ok": True, "voice": v})

    def _add_voice(self, b):
        name = (b.get("name") or "").strip()
        if not name or not re.match(r"^[\w\-.]+$", name):
            return self._err("Имя голоса — латиница/цифры/«_», без пробелов")
        cfg = read_voices_file()
        if name in cfg.get("voices", {}):
            return self._err("Голос «%s» уже есть" % name)
        is_index = ag.engine_kind() == ag.ENGINE_INDEX
        # У IndexTTS голос — это один референс: весов у голоса нет.
        need = ("ref",) if is_index else ("gpt", "sovits", "ref", "prompt_text")
        for k in need:
            if not (b.get(k) or "").strip():
                return self._err("Заполни поле: %s" % k)
        cfg = ag.load_config()
        eng = ((cfg.get("indextts_path") or "") if is_index
               else (cfg.get("gptsovits_path") or ""))
        entry = {
            "display": (b.get("display") or name).strip(),
            "ref": store_path(b["ref"].strip(), eng),
            "aux": [],
            "prompt_text": (b.get("prompt_text") or "").strip(),
            "prompt_lang": (b.get("prompt_lang") or "ja").strip() or "ja",
            "temperature": 0.6, "top_p": 0.6, "top_k": 20,
            "speed": 1.0, "seed": 42,
        }
        if not is_index:
            entry["gpt"] = store_path(b["gpt"].strip(), eng)
            entry["sovits"] = store_path(b["sovits"].strip(), eng)
        else:
            entry["lang"] = (b.get("lang") or "JA").strip() or "JA"
        cfg.setdefault("voices", {})[name] = entry
        write_voices_file(cfg)
        self._json({"ok": True, "name": name})

    def _run(self, b):
        kind = b.get("kind")
        if kind == "voice":
            args, title, err = self._args_voice(b)
            if err:
                return self._err(err)
            # поля не заполнены — отвечаем словами, а не падаем в 500
            if not args:
                return self._err("Сначала выбери голос и колоду")
        elif kind == "check":
            deck = (b.get("deck") or "").strip()
            if not deck:
                return self._err("Сначала выбери колоду")
            args = ["check", "--deck", deck,
                    "--sentence-audio", (b.get("sentence_audio") or "").strip(),
                    "--word-audio", (b.get("word_audio") or "").strip()]
            title = "Проверка колоды «%s»" % deck
        elif kind == "test":
            voice = (b.get("voice") or "").strip()
            if not voice:
                return self._err("Сначала выбери голос")
            args = ["test", "--voice", voice,
                    "--text", (b.get("text") or "既存建築物の改修では、耐火性能と耐震性能の確認が重要です。"),
                    "--speed", "%.2f" % float(b.get("speed") or 1.0),
                    "--seed", str(int(b.get("seed") or 42))]
            title = "Тест синтеза «%s»" % voice
        elif kind == "verify":
            deck = (b.get("deck") or "").strip()
            if not deck:
                return self._err("Сначала выбери колоду")
            args = ["verify", "--deck", deck,
                    "--mode", "sentence",
                    # содержание проверяем по предложениям: изолированное
                    # слово распознаётся ненадежно, порога нет
                    "--sentence-audio", (b.get("sentence_audio") or "").strip(),
                    "--word-audio", (b.get("word_audio") or "").strip()]
            title = "Проверка произношения «%s»" % deck
        elif kind == "selftest":
            args, title = ["selftest"], "Самопроверка пайплайна"
        elif kind == "retry":
            # перезапуск неудавшихся операций прошлого прогона
            lr = _read_last_run()
            if not (lr.get("failed_ids") or []):
                return self._err("Перепробовать нечего: у прошлого прогона "
                                 "ошибок нет")
            args, title = ["voice", "--retry"], \
                "Перепробовать неудашиеся (%d)" % len(lr["failed_ids"])
        elif kind == "scan":
            args, title = ["scan", "--apply", "--json"], "Сканирование весов в движке"
        elif kind == "qc-deck":
            args, title = ["qc-deck"], "Сборка колоды «Брак»"
        elif kind == "verdicts":
            args, title = ["verdicts"], "Сводка по вердиктам"
        else:
            return self._err("Неизвестная операция. Обнови приложение.")

        run, err = start_run(title, args)
        if err:
            return self._err(err)
        return self._json({"ok": True, "run": run.snapshot()})

    def _args_voice(self, b):
        voice = (b.get("voice") or "").strip()
        deck = (b.get("deck") or "").strip()
        if not voice:
            return None, None, "Сначала выбери голос"
        if not deck:
            return None, None, "Сначала выбери колоду"
        # поля: что прислал клиент, иначе — автоподбор по полям колоды,
        # иначе — умолчания пайплайна (пустые флаги не передаём)
        g = {}
        if not (b.get("sentence_src") or "").strip() \
                or not (b.get("word_src") or "").strip():
            _fl, g = deck_fields(deck)

        def fld(key, guess_key):
            v = (b.get(key) or "").strip()
            if v:
                return v
            return (g.get(guess_key) or "").strip()

        args = ["voice", "--voice", voice, "--deck", deck,
                "--mode", (b.get("mode") or "both")]
        # ансамбль: выбранные дополнительные голоса — карточки распределятся
        # случайно и озвучатся партиями (по одному переключению весов на голос)
        voices = [str(v).strip() for v in (b.get("voices") or [])
                  if str(v).strip() and str(v).strip() != voice]
        if voices:
            args += ["--voices", ",".join([voice] + voices)]
        if b.get("only_new"):
            # ежедневный сценарий: только карточки без тега av_voiced
            args.append("--new")
        if b.get("only_suspect"):
            args += ["--tag", "av_suspect"]
        for flag, key, guess_key in (
                ("--sentence-src", "sentence_src", "sentence_src"),
                ("--sentence-audio", "sentence_audio", "sentence_audio"),
                ("--word-src", "word_src", "word_src"),
                ("--word-audio", "word_audio", "word_audio")):
            v = fld(key, guess_key)
            if v:
                args += [flag, v]
        furi = fld("furigana_src", "furigana_src")
        if furi:
            args += ["--furigana-src", furi]
        # режим чтения: "" (авто — решение по карточке), mix, asis
        reading = (b.get("reading") or "").strip()
        if reading == READING_OFF:
            # старое значение из профилей v1.1: «движок читает сам»
            reading = "asis"
        args += ["--reading", reading]
        # Лимит карточек: целое число не меньше нуля. Пусто или 0 — вся колода
        # (с подтверждением в интерфейсе). Мусор раньше молча превращался в
        # «без лимита», и приложение озвучивало ВСЮ колоду — на «Архитектуре»
        # это 18 375 карточек.
        limit_raw = str(b.get("limit") or "").strip()
        limit = 0
        if limit_raw:
            try:
                limit = int(limit_raw)
            except (TypeError, ValueError):
                return None, None, ("Лимит карточек должен быть целым числом "
                                    "не меньше нуля.")
            if limit < 0:
                return None, None, ("Лимит карточек должен быть не меньше нуля. "
                                    "Пусто или 0 — вся колода.")
        if limit > 0:
            args += ["--limit", str(limit)]
        if b.get("force"):
            args.append("--force")
        return args, "Озвучка колоды «%s»" % deck, None

    def _args_guard(self, b):
        """Своя проверка, чтобы ответ был понятным, а не stack-trace."""
        return None


# ================================================================== запуск
def serve(open_browser=True, port=0):
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    httpd.daemon_threads = True
    real_port = httpd.server_address[1]
    url = "http://127.0.0.1:%d/" % real_port

    prob = ag._payload_problem()
    if prob:
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(
                0, prob.replace("\n", "\r\n"),
                "%s — сначала распакуй zip" % ag.APP_NAME, 0x10)
        except Exception:
            print(prob)
        return 1

    print("AnkiVoice — веб-интерфейс: %s" % url)
    if open_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever(poll_interval=0.3)
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
    return 0


def main():
    ap = argparse.ArgumentParser(description=ag.APP_NAME + " — веб-интерфейс")
    ap.add_argument("--no-open", action="store_true",
                    help="не открывать браузер автоматически")
    ap.add_argument("--port", type=int, default=0,
                    help="порт (0 — свободный автоматически)")
    a = ap.parse_args()
    sys.exit(serve(open_browser=not a.no_open, port=a.port))


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        import traceback
        msg = traceback.format_exc()
        try:
            with open(ag.CRASH_LOG, "a", encoding="utf-8") as f:
                f.write(msg + "\n")
        except Exception:
            pass
        print(msg)
        raise
