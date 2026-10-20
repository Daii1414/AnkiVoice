# -*- coding: utf-8 -*-
"""voice_pipeline.py — единый пайплайн озвучки колод Anki голосами GPT-SoVITS.

Автономный пайплайн: скрипт лежит в любой папке (например, в репозитории на
GitHub), а движок GPT-SoVITS может стоять где угодно. Папка движка ищется
в таком приоритете (первый найденный берётся):
  1. переменная окружения GPT_SOVITS_ROOT=C:\\...\\GPT-SoVITS
  2. файл gptsovits_path.txt рядом с этим скриптом (одна строка — путь)
  3. %APPDATA%\\AnkiVoice\\config.json  ->  "gptsovits_path"  (его пишет AnkiVoice.exe;
     старый путь %APPDATA%\\AnkiTTS\\config.json тоже читается)
  4. сама папка скрипта (если скрипт лежит внутри GPT-SoVITS — старое поведение)

Быстрый старт (движок уже настроен, см. выше):
  pipeline.bat                                        -> интерактивное меню
  pipeline.bat list
  pipeline.bat add --name sakura ^
      --gpt GPT_weights_v2Pro/Sakura-e15.ckpt ^
      --sovits SoVITS_weights_v2Pro/Sakura_e8_s368.pth ^
      --ref "C:\\...\\sakura.wav" --prompt-text "..."
  pipeline.bat make-deck --voice sakura --query "deck:Архитектура" --limit 20
  pipeline.bat voice --voice sakura --deck "Sakura" --mode both
  pipeline.bat check --deck "Sakura"
  pipeline.bat selftest

Что делает автоматически:
  * поднимает API-сервер GPT-SoVITS, если он не запущен;
  * переключает веса голоса на лету (при нехватке памяти — перезапуск и повтор);
  * переводит текст карточек в хирагану (SudachiPy по словарю UniDic, запасной
    ход — pyopenjtalk), латиницу IEC/ISO/I形 -> катакана по буквам;
  * синтезирует слово и предложение, кладёт ogg в медиа Anki, пишет [sound:...] в поля;
  * проверяет результат (поля заполнены, файлы на месте).

Голоса хранятся в voices.json (рядом со скриптом). Референс обязан быть 3–10 секунд.
Относительные пути в voices.json (к весам и референсам) считаются от папки ДВИЖКА.
"""

import argparse
import base64
import hashlib
import html
import json
import os
import re
import unicodedata
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile

try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
try:
    if hasattr(sys.stdin, "reconfigure"):
        sys.stdin.reconfigure(encoding="utf-8")
except Exception:
    pass

# ------------------------------------------------------------------ модули чтения (lab/)
# Импортируются лениво, чтобы не падать при отсутствии lab/ (например, в
# собранном .exe без исходников). Функции _ensure_reading_modules() /
# _reading_modules() ниже инициализируют singleton при первом вызове.
_READING_MODULES = None


def _ensure_reading_modules():
    """Загружает модули системы чтения (provenance, domain_dict, resolver) из lab/."""
    global _READING_MODULES
    if _READING_MODULES is not None:
        return _READING_MODULES
    lab_path = os.path.join(CODE, "lab")
    if lab_path not in sys.path:
        sys.path.insert(0, lab_path)
    try:
        from g2p_provenance import ReadingSource, ReadingCandidate
        from domain_dict import DomainDictionary, ReadingSource as _RS2
        from g2p_resolver import ReadingResolver
        from g2p_candidates import CandidateGenerator
        try:
            from haqumei import Haqumei
            h = Haqumei(revert_long_vowels=True, revert_yotsugana=True)
        except Exception:
            h = None
        try:
            from sudachi_g2p import sudachi_client as _sc
        except Exception:
            _sc = None
        dd = DomainDictionary()
        gen = CandidateGenerator(domain_dict=dd, haqumei=h, sudachi_client=_sc)
        resolver = ReadingResolver(domain_dict=dd, generator=gen)
        _READING_MODULES = {
            "ReadingSource": ReadingSource,
            "ReadingCandidate": ReadingCandidate,
            "domain_dict": dd,
            "resolver": resolver,
        }
    except Exception as e:
        _READING_MODULES = {"_error": str(e)}
    return _READING_MODULES

# ------------------------------------------------------------------ константы
# CODE  — папка самого инструмента (этот скрипт, voices.json).
# ENGINE — папка установленного GPT-SoVITS (runtime\python.exe, api_v2.py, веса).
CODE = os.path.dirname(os.path.abspath(__file__))
VOICES_FILE = os.path.join(CODE, "voices.json")
ENGINE_LOCAL_FILE = os.path.join(CODE, "gptsovits_path.txt")

ENGINE = None             # заполняется resolve_engine() ниже
PYTHON = None             # ENGINE\runtime\python.exe
ACTIVE_VOICE_FILE = None  # ENGINE\logs\active_voice.txt
SERVER_LOG = None         # ENGINE\logs\api_v2_pipeline.log

ANKI_CONNECT = "http://127.0.0.1:8765"
TTS_HOST, TTS_PORT = "127.0.0.1", 9880
TTS_URL = "http://%s:%d" % (TTS_HOST, TTS_PORT)
DEFAULT_START_CONFIG = os.path.join("GPT_SoVITS", "configs", "tts_infer.yaml")

# Какие поля карточки читать (текст) и куда писать (звук). Можно переопределить
# на вкладке «Поля колоды» / через CLI — разные колоды называют поля по-разному.
DEFAULT_FIELDS = {
    "sentence_src": "Sentence",        # поле с текстом предложения
    "sentence_audio": "SentenceAudio",  # поле, куда писать звук предложения
    "word_src": "Expression",          # поле со словом (основное слово карточки)
    "furigana_src": "ExpressionFurigana",  # поле с фуриганой к основному слову
    "word_audio": "ExpressionAudio",   # поле, куда писать звук слова
    "reading": "off",                    # источник чтения: "off" — не подставлять
                                        # (движок читает само), имя поля — строго из него
}


def resolve_fields(**over):
    """DEFAULT_FIELDS + переопределения (пустые значения игнорируются)."""
    f = dict(DEFAULT_FIELDS)
    for k, v in (over or {}).items():
        if v:
            f[k] = v
    return f


def audio_fields(fields):
    """Список аудио-полей, которые нужно очищать при клоне и проверять."""
    return [fields["sentence_audio"], fields["word_audio"]]


# --------------------------------------------------- поиск папки GPT-SoVITS
def _is_engine(p):
    """Папка похожа на установку GPT-SoVITS: есть интерпретатор и api_v2.py."""
    return bool(p) and os.path.isfile(os.path.join(p, "runtime", "python.exe")) \
        and os.path.isfile(os.path.join(p, "api_v2.py"))


def _read_engine_local_file():
    try:
        with open(ENGINE_LOCAL_FILE, encoding="utf-8") as f:
            s = f.read().strip().strip('"').strip("'")
        return s or None
    except OSError:
        return None


def _read_engine_gui_config():
    for name in ("AnkiVoice", "AnkiTTS"):      # новое имя и старое (до переименования)
        cfgp = os.path.join(os.environ.get("APPDATA") or "", name, "config.json")
        try:
            with open(cfgp, encoding="utf-8") as f:
                p = (json.load(f) or {}).get("gptsovits_path")
                if p:
                    return p
        except OSError:
            continue
        except Exception:
            continue
    return None


def _norm(p):
    return os.path.abspath(os.path.expandvars(os.path.expanduser(p)))


def resolve_engine():
    """Папка движка: env -> gptsovits_path.txt -> конфиг AnkiVoice.exe -> своя папка."""
    for cand in (os.environ.get("GPT_SOVITS_ROOT"),
                 _read_engine_local_file(),
                 _read_engine_gui_config(),
                 CODE):                      # обратная совместимость: лежит внутри GPT-SoVITS
        if cand:
            cand = _norm(cand)
            if _is_engine(cand):
                return cand
            if cand != CODE and cand not in _BAD_ENGINES:
                _BAD_ENGINES.append(cand)   # запоминаем: пользователь указал, но путь битый
    return None


_BAD_ENGINES = []       # указанные, но не похожие на GPT-SoVITS пути


def require_engine():
    if not ENGINE:
        msg = ("Не найдена папка GPT-SoVITS. Укажи её одним из способов:\n"
               "  * переменная окружения  GPT_SOVITS_ROOT=C:\\...\\GPT-SoVITS\n"
               "  * файл gptsovits_path.txt рядом с voice_pipeline.py (одна строка — путь)\n"
               "  * запусти AnkiVoice.exe и выбери папку в окне (сохранится в конфиг)\n"
               "В папке должны быть runtime\\python.exe и файл api_v2.py.")
        if _BAD_ENGINES:
            msg += ("\n\nУказанные пути НЕ подошли (нет runtime\\python.exe или api_v2.py):"
                    + "".join("\n  * %s" % p for p in _BAD_ENGINES))
        raise SystemExit(msg)
    return ENGINE


# сразу резолвим (не бросает исключений: при отсутствии ENGINE останется None,
# а require_engine() даст понятную ошибку при попытке использовать движок)
ENGINE = resolve_engine()
if ENGINE:
    PYTHON = os.path.join(ENGINE, "runtime", "python.exe")
    ACTIVE_VOICE_FILE = os.path.join(ENGINE, "logs", "active_voice.txt")
    SERVER_LOG = os.path.join(ENGINE, "logs", "api_v2_pipeline.log")


# ------------------------------------------------------------ AnkiConnect
# Все локальные запросы (AnkiConnect и GPT-SoVITS) идут МИМО системного
# прокси: 127.0.0.1 — это localhost, а прокси-обвязка (корпоративный VPN,
# PAC-скрипт, настройки «Интернет-свойства») только ломает такие запросы.
_NO_PROXY = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def ac(action, **params):
    payload = {"action": action, "version": 6, "params": params}
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    for attempt in (1, 2):
        req = urllib.request.Request(
            ANKI_CONNECT, data=data,
            headers={"Content-Type": "application/json", "Origin": "http://localhost"},
        )
        try:
            with _NO_PROXY.open(req, timeout=120) as resp:
                out = json.loads(resp.read().decode("utf-8"))
            break
        except urllib.error.URLError as e:
            if attempt == 1:
                time.sleep(1.0)      # Anki мог перезаписывать коллекцию — повтор разок
                continue
            raise SystemExit("AnkiConnect недоступен (%s). Открой Anki и повтори." % e)
    if out.get("error"):
        raise SystemExit("AnkiConnect: %s" % out["error"])
    return out["result"]


def notes_info(ids, chunk=400):
    """notesInfo по частям: AnkiConnect на десятках тысяч id отвечает
    одним огромным JSON — режем на куски, стабильно и быстрее."""
    out = []
    for i in range(0, len(ids), chunk):
        out.extend(ac("notesInfo", notes=ids[i:i + chunk]))
    return out


TAG_RE = re.compile(r"<[^>]+>")
SOUND_TAG_RE = re.compile(r"\[(?:sound|audio):[^\]]*\]", re.IGNORECASE)


def plain(v, strip_media=False):
    """Поле карточки -> чистый текст.

    strip_media=True — для ТЕКСТОВ, которые уходят на синтез: [sound:...]
    вырезается, иначе API прочитает «звук двоеточие...» вслух. Для проверки
    «озвучено ли поле» (check_deck, build_jobs) strip_media=False — тег должен
    остаться видимым."""
    s = TAG_RE.sub("", v or "")
    if strip_media:
        s = SOUND_TAG_RE.sub(" ", s)
    s = html.unescape(s).replace("\xa0", " ")
    return s.strip()


# ----------------------------------------------------------- работа с голосами
def load_voices():
    if not os.path.exists(VOICES_FILE):
        return {"start_config": DEFAULT_START_CONFIG, "default_voice": None, "voices": {}}
    try:
        with open(VOICES_FILE, encoding="utf-8") as f:
            cfg = json.load(f)
    except ValueError as e:
        raise SystemExit(
            "voices.json повреждён (сломан JSON): %s\n"
            "Файл: %s\nПочини его или удали — голоса добавятся заново "
            "(pipeline.bat scan --apply)." % (e, VOICES_FILE))
    cfg.setdefault("voices", {})
    cfg.setdefault("start_config", DEFAULT_START_CONFIG)
    return cfg


def save_voices(cfg):
    # запись во временный файл + атомарная замена: обрыв/вылет не портит voices.json
    tmp = VOICES_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    os.replace(tmp, VOICES_FILE)


def get_voice(name=None):
    require_engine()
    cfg = load_voices()
    name = name or cfg.get("default_voice")
    if not name:
        raise SystemExit("Голос не задан. Сделай: voice_pipeline.py list")
    if name not in cfg["voices"]:
        raise SystemExit("Голос '%s' не найден. Доступны: %s"
                         % (name, ", ".join(sorted(cfg["voices"])) or "—"))
    v = dict(cfg["voices"][name])
    v["name"] = name
    for key in ("gpt", "sovits", "ref"):
        if v.get(key) and not os.path.isabs(v[key]):
            v[key] = os.path.join(ENGINE, v[key])
    v["aux"] = [a if os.path.isabs(a) else os.path.join(ENGINE, a)
                for a in v.get("aux") or []]
    return v


def ref_duration(path):
    try:
        import soundfile as sf
        info = sf.info(path)
        return info.duration
    except Exception:
        return None


# ------------------------------------------------------ поиск голосов в движке
def _epoch_of(name):
    m = re.search(r"[-_]e(\d+)", name)
    return int(m.group(1)) if m else -1


def _pretty_name(base):
    """MISHIMA_V2 -> Mishima V2"""
    parts = [p for p in re.split(r"[_\-\s]+", base) if p]
    return " ".join(p if p.isdigit() else p[:1].upper() + p[1:].lower()
                    for p in parts)


def _find_ref_for(engine, base):
    """Референсный файл голоса: ищем в корне движка аудио с именем голоса."""
    token = re.sub(r"[_\-\s]+", "", base).lower()
    if not token:
        return ""
    try:
        names = sorted(os.listdir(engine))
    except OSError:
        return ""
    best = None
    for name in names:
        p = os.path.join(engine, name)
        if not os.path.isfile(p):
            continue
        low = name.lower()
        if os.path.splitext(low)[1] not in (".wav", ".mp3", ".flac"):
            continue
        hay = re.sub(r"[_\-\s]+", "", os.path.splitext(low)[0])
        if token not in hay:
            continue
        score = (2 if low.startswith("ref_main") else
                 1 if low.startswith("ref") else 0)
        if best is None or score > best[0]:
            best = (score, name)
    return best[1] if best else ""


def scan_engine_voices(engine):
    """Обходит папки весов движка и собирает пары GPT(.ckpt) + SoVITS(.pth).

    Папки вида GPT_weights* / SoVITS_weights*; имена файлов: Base-eNN.ckpt и
    Base_eN_sM.pth, base у пары совпадает без учёта регистра. Версии
    (v2Pro / v2ProPlus) между собой НЕ смешиваются. Из эпох берётся самая
    свежая. Возвращает словари с путями относительно engine.
    """
    gpts, sovits = {}, {}
    for sub in sorted(os.listdir(engine)):
        low = sub.lower()
        if not os.path.isdir(os.path.join(engine, sub)):
            continue
        if low.startswith("gpt_weights"):
            bucket, ext = gpts, ".ckpt"
        elif low.startswith("sovits_weights"):
            bucket, ext = sovits, ".pth"
        else:
            continue
        fam = re.sub(r"^(gpt|sovits)_weights", "", low).strip("_") or "default"
        d = os.path.join(engine, sub)
        try:
            names = sorted(os.listdir(d))
        except OSError:
            continue
        for fn in names:
            if not fn.lower().endswith(ext):
                continue
            stem = os.path.splitext(fn)[0]
            base = re.sub(r"[-_]e\d+(_s\d+)?$", "", stem).strip()
            if not base:
                continue
            bucket.setdefault((fam, base.lower()), []).append(
                (_epoch_of(fn), os.path.join(sub, fn).replace("\\", "/"), base))

    out, seen = [], set()
    for key in sorted(gpts):
        fam, base_key = key
        if key not in sovits:
            continue                      # нет парного SoVITS — пропускаем
        _, gpt_rel, base = max(gpts[key], key=lambda t: t[0])
        _, sovits_rel, _ = max(sovits[key], key=lambda t: t[0])
        ver = ("v2Pro+" if "plus" in fam else
               "v2Pro" if fam == "v2pro" else
               "" if fam == "default" else fam)
        name = re.sub(r"[^a-z0-9_]+", "_", base_key).strip("_")
        if name in seen:
            name = name + "_" + re.sub(r"[^a-z0-9]+", "", fam)
        seen.add(name)
        out.append({
            "name": name,
            "display": _pretty_name(base) + (" · " + ver if ver else ""),
            "gpt": gpt_rel,
            "sovits": sovits_rel,
            "ref": _find_ref_for(engine, base),
        })
    return out


def _gpt_identity(path):
    """Путь к весам без номера эпохи — для узнавания уже известного голоса.

    'GPT_weights_v2ProPlus/Narator-e45.ckpt' и '.../Narator-e50.ckpt' —
    это один и тот же голос (просто разные эпохи), а не два разных.
    Сравнение по точному пути давало дубли с пустым референсом.
    """
    p = str(path or "").lower().replace("\\", "/")
    return re.sub(r"[-_]e\d+(_s\d+)?\.(ckpt|pth)$", r".\2", p)


def cmd_scan(args):
    engine = require_engine()
    found = scan_engine_voices(engine)
    cfg = load_voices()
    existing = cfg.setdefault("voices", {})
    known_gpt = {_gpt_identity(v.get("gpt", "")) for v in existing.values()}
    added = []
    for item in found:
        # голос уже зарегистрирован (иначе ключей) — в т.ч. той же модели,
        # но с другой эпохой: дубликаты с пустым референсом не нужны
        if _gpt_identity(item["gpt"]) in known_gpt:
            continue
        existing[item["name"]] = {
            "display": item["display"],
            "gpt": item["gpt"],
            "sovits": item["sovits"],
            "ref": item["ref"],
            "aux": [],
            "prompt_text": "",
            "prompt_lang": "ja",
        }
        known_gpt.add(_gpt_identity(item["gpt"]))
        added.append(item["name"])
    if added and args.apply:
        save_voices(cfg)
    if args.json:
        print(json.dumps({"found": len(found), "added": added,
                          "apply": bool(args.apply)}, ensure_ascii=False))
    else:
        print("Найдено пар весов: %d" % len(found))
        for it in found:
            mark = "+" if it["name"] in added else "="
            print("  %s %-22s %-24s ref=%s"
                  % (mark, it["name"], it["display"], it["ref"] or "—"))
        if added and not args.apply:
            print("Новые голоса НЕ записаны — запусти с --apply.")
        elif added:
            print("Добавлено в voices.json: %s" % ", ".join(added))
    return True


# --------------------------------------------------------- GPT-SoVITS: сервер
def tts_ready():
    try:
        s = socket.create_connection((TTS_HOST, TTS_PORT), timeout=2)
        s.close()
        return True
    except OSError:
        return False


def active_voice():
    try:
        with open(ACTIVE_VOICE_FILE, encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return None


def set_active_voice(name):
    os.makedirs(os.path.dirname(ACTIVE_VOICE_FILE), exist_ok=True)
    with open(ACTIVE_VOICE_FILE, "w", encoding="utf-8") as f:
        f.write(name)


def wait_port(want_up, timeout=300, what="порт"):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if tts_ready() == want_up:
            return True
        time.sleep(2)
    return False


def port_pid(port):
    """PID процесса, слушающего порт (Windows/netstat), либо None."""
    try:
        out = subprocess.run(["netstat", "-ano"], capture_output=True,
                             text=True, timeout=20)
        for line in out.stdout.splitlines():
            if "LISTENING" in line and (":%d " % port) in line:
                return line.split()[-1]
    except Exception:
        pass
    return None


def port_process_name(pid):
    try:
        out = subprocess.run(["tasklist", "/FI", "PID eq %s" % pid, "/FO", "CSV", "/NH"],
                             capture_output=True, text=True, timeout=20)
        line = out.stdout.strip().splitlines()[0]
        return line.split('","')[0].strip('"')
    except Exception:
        return "?"


def start_server(start_config, wait=600):
    require_engine()
    if tts_ready():
        # порт открыт — убедимся, что это НАШ сервер, а не чужая программа
        pid = port_pid(TTS_PORT)
        name = port_process_name(pid) if pid else ""
        if pid and "python" not in name.lower():
            raise SystemExit(
                "Порт %d занят программой '%s' (PID %s) — это не GPT-SoVITS.\n"
                "Закрой эту программу и повтори." % (TTS_PORT, name, pid))
        return
    os.makedirs(os.path.dirname(SERVER_LOG), exist_ok=True)
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    log = open(SERVER_LOG, "a", encoding="utf-8")
    subprocess.Popen(
        [PYTHON, "-u", "api_v2.py", "-a", TTS_HOST, "-p", str(TTS_PORT),
         "-c", os.path.relpath(start_config, ENGINE)],
        cwd=ENGINE, env=env, stdout=log, stderr=subprocess.STDOUT,
    )
    print("Запускаю GPT-SoVITS, ждём до %d с..." % wait)
    if not wait_port(True, wait):
        raise SystemExit("Сервер не поднялся за %d с, см. %s" % (wait, SERVER_LOG))
    time.sleep(1)
    print("GPT-SoVITS готов.")


def restart_server(start_config, wait=600):
    """Перезапуск через /control: процесс перезапускает сам себя тем же argv."""
    print("Перезапускаю сервер (нужна свежая память)...")
    try:
        _NO_PROXY.open(TTS_URL + "/control?command=restart", timeout=10).read()
    except Exception:
        pass                       # сокет обрывается — это ожидаемо
    wait_port(False, 60)
    if tts_ready():                # не упал — убиваем по порту (только python!)
        pid = port_pid(TTS_PORT)
        name = port_process_name(pid) if pid else ""
        if pid and "python" not in name.lower():
            raise SystemExit(
                "Порт %d держит чужая программа '%s' (PID %s) — не убиваю её.\n"
                "Закрой её сам и повтори." % (TTS_PORT, name, pid))
        try:
            if pid:
                subprocess.run(["taskkill", "/PID", pid, "/F"],
                               capture_output=True, timeout=20)
        except Exception as e:
            print("не удалось остановить старый процесс:", e)
        wait_port(False, 60)
    time.sleep(2)
    start_server(start_config, wait)


def _get(path, params):
    url = TTS_URL + path + "?" + urllib.parse.urlencode(params)
    try:
        with _NO_PROXY.open(url, timeout=300) as r:
            return r.status == 200
    except urllib.error.HTTPError:
        return False
    except Exception:
        return False


def set_weights(v):
    ok_gpt = _get("/set_gpt_weights", {"weights_path": v["gpt"]})
    ok_sov = _get("/set_sovits_weights", {"weights_path": v["sovits"]})
    return ok_gpt and ok_sov


def ensure_voice(v, force=False):
    """Сервер запущен + веса голоса загружены. При сбое — перезапуск и повтор."""
    require_engine()
    cfg = load_voices()
    start_config = os.path.join(ENGINE, cfg.get("start_config") or DEFAULT_START_CONFIG)
    if not tts_ready():
        start_server(start_config)
    if not force and active_voice() == v["name"]:
        return
    print("Переключаю веса на '%s'..." % v["name"])
    if set_weights(v):
        set_active_voice(v["name"])
        return
    print("Не получилось переключить (обычно нехватка памяти). Перезапуск...")
    restart_server(start_config)
    if set_weights(v):
        set_active_voice(v["name"])
        return
    raise SystemExit("Веса '%s' не загрузились. Проверь пути в voices.json:\n  GPT:    %s\n  SoVITS: %s"
                     % (v["name"], v["gpt"], v["sovits"]))


# ------------------------------------------------- хирагана / чтение текста
# иероглифы: BMP (вкл. Ext A и совместимые) + дополнительные плоскости
# (Ext B..I — редкие фамилии, исторические знаки, имена персонажей)
KANJI_RE = re.compile(
    r"[\u3005\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\U00020000-\U0003FFFF]")
LATIN = {"A": "エー", "B": "ビー", "C": "シー", "D": "ディー", "E": "イー",
         "F": "エフ", "G": "ジー", "H": "エイチ", "I": "アイ", "J": "ジェー",
         "K": "ケー", "L": "エル", "M": "エム", "N": "エヌ", "O": "オー",
         "P": "ピー", "Q": "キュー", "R": "アール", "S": "エス", "T": "ティー",
         "U": "ユー", "V": "ブイ", "W": "ダブリュー", "X": "エックス",
         "Y": "ワイ", "Z": "ゼット"}

_g2p_warned = False


def latin2kana(s):
    return re.sub(r"[A-Za-z]", lambda m: LATIN.get(m.group(0).upper(), m.group(0)), s)


def normalize_text(s):
    """NFKC для букв/цифр, но знаки препинания не трогаем.

    NFKC превращает японские ?!… в латинские (?!...), из-за чего GPT-SoVITS
    читает их иначе. Поэтому ASCII оставляем как есть, а полноразмерные
    буквы/цифры нормализуем — но ЦЕЛЫМИ КУСКАМИ: полукатакана ｶﾞ состоит
    из двух код-пунктов (ｶ + ‍ﾞ) и посимвольная нормализация даёт
    «か + парящий знак» вместо «が». Склеенный кусок NFKC превращает
    ｶﾞｷｮｳ сразу в правильное ガキョウ. Знаки препинания (？！…・～)
    к буквенным кускам не примыкают и остаются как есть.
    """
    out = []
    i, n = 0, len(s)
    while i < n:
        ch = s[i]
        if ord(ch) < 0x80:                          # ASCII: не трогаем
            out.append(ch)
            i += 1
            continue
        # собираем подряд идущие буквы/цифры/диакритику (кат. L, N, M)
        j = i
        while j < n and ord(s[j]) >= 0x80:
            nf = unicodedata.normalize("NFKC", s[j])
            # NFKC одного символа иногда даёт несколько (ﬃ -> "ffi"):
            # категорию берём по первому символу результата
            cat = unicodedata.category(nf[0]) if nf else "C"
            if cat[0] in ("L", "N", "M"):
                j += 1
            else:
                break
        if j > i:
            # кусок целиком: ｶﾞ -> ガ (один код-пункт), Ａ -> A и т.п.
            out.append(unicodedata.normalize("NFKC", s[i:j]))
            i = j
        else:
            out.append(ch)
            i += 1
    return "".join(out)


# katakana вне стандартного диапазона U+30A1..U+30F6:
# ヷヸヹヺ - уточнённые «ва/ви/ву/ве» (через combining dakuten).
# Знаки повторения ゝゞヽヾ обрабатываются контекстно в kata2hira().
_KATA_EXTRA = {"ヷ": "わ゛", "ヸ": "い゛", "ヹ": "う゛", "ヺ": "う゛"}

# озвончение для знаков повторения ゾ/ヾ (повтор предыдущего слога с dakuten)
_VOICED = {"か": "が", "き": "ぎ", "く": "ぐ", "け": "げ", "こ": "ご",
           "さ": "ざ", "し": "じ", "す": "ず", "せ": "ぜ", "そ": "ぞ",
           "た": "だ", "ち": "ぢ", "つ": "づ", "て": "で", "と": "ど",
           "は": "ば", "ひ": "び", "ふ": "ぶ", "へ": "べ", "ほ": "ぼ"}


def kata2hira(s, keep_kata=()):
    """Катакана -> хирагана. Слова из keep_kata остаются катаканой.

    Знаки повторения раскрываются контекстно: ヽ/ゝ повторяют предыдущий
    слог, ヾ/ゞ — предыдущий слог с озвончением (サヾ -> さざ). Раньше
    ヽ/ヾ были заменены фиксированной парой «け/げ» — это была ошибка:
    знак повторения не самостоятельный слог.
    """
    out = []
    prev = ""                     # предыдущий слог (уже хирагана)
    for c in s:
        if "ァ" <= c <= "ヶ":
            prev = chr(ord(c) - 0x60)
            out.append(prev)
        elif c in ("ゝ", "ヽ", "ゞ", "ヾ"):
            if not prev:
                out.append(c)     # не к чему повторять — оставляем как есть
            elif c in ("ゞ", "ヾ") and prev in _VOICED:
                out.append(_VOICED[prev])
            else:
                out.append(prev)  # prev не меняется: ヽゝ подряд = тот же слог
        else:
            out.append(_KATA_EXTRA.get(c, c))
            if "ぁ" <= c <= "ゖ":
                prev = c
    t = "".join(out)
    for keep in keep_kata:                      # вернуть защищённые слова
        t = t.replace(kata2hira(keep), keep)
    return t


# Границы сегментов: иероглифы (с хираганой) / катакана / всё прочее.
# Разрезаем текст так, чтобы g2p достались ТОЛЬКО куски с иероглифами.
# иероглифы и хирагана (включая Ext A и дополнительные плоскости Unicode);
# знаки препинания сознательно НЕ входят — они идут «прочим» сегментом.
_SEG_RE = re.compile(
    r"([\u3040-\u30ff\u4e00-\u9fff\u3400-\u4dbf\u3004\u3005\u30f5\u30f6\U00020000-\U0003FFFF]+)"
    r"|([\u30a1-\u30ff\uff66-\uff9f]+)"          # катакана (вкл. полукатакану)
    r"|([^\u3004\u3005\u3040-\u30ff\u4e00-\u9fff\u3400-\u4dbf\U00020000-\U0003FFFF]+)"       # всё прочее (латиница, цифры, знаки)
)
KANJI_SEG, KATA_SEG, ETC_SEG = 1, 2, 3


def _segments(text):
    """Разбить текст на сегменты [(вид, текст)]."""
    segs = []
    for m in _SEG_RE.finditer(text):
        if m.group(KANJI_SEG) is not None:
            segs.append((KANJI_SEG, m.group(KANJI_SEG)))
        elif m.group(KATA_SEG) is not None:
            segs.append((KATA_SEG, m.group(KATA_SEG)))
        else:
            segs.append((ETC_SEG, m.group(ETC_SEG)))
    return segs


# «Защищённые» слова: остаются КАТАКАНОЙ в итоговом тексте.
# Причина: MeCab читает хираграфу как частицу (こんにちは -> コンニчива,
# こんにちは -> コнбанва), а катакану читает верно. Финальный kata2hira
# их не трогает — в отличие от прочей катаканы, которую мы сами сгладили
# в хирагану, чтобы MeCab не портил наши сборки вроде
# IEC -> アイイーシー -> アイイースィー.
_KEEP_KATA = ("コンニチハ", "コンバンハ")


# SudachiPy — основной «читатель» иероглифов (движок sudachi.rs): свежий
# словарь UniDic даёт готовое чтение каждой морфемы целиком, с окуриганой
# и редкими терминами (高輪ゲートウェイ駅 -> タカナワゲートウェイエキ).
#
# SudachiPy 0.7 требует Python >= 3.10, а движку GPT-SoVITS хватает 3.9,
# поэтому разбор идёт в СВОЁМ встроенном Python (папка pyruntime рядом со
# скриптом): долгоживущий помощник sudachi_g2p.py отвечает на JSON-строки.
# Пользователю ставить ничего не нужно — всё лежит в репозитории.
PYRUNTIME_DIR = os.path.join(CODE, "pyruntime")
PYRUNTIME_PY = os.path.join(PYRUNTIME_DIR, "python.exe")
SUDACHI_HELPER = os.path.join(CODE, "sudachi_g2p.py")
PYRUNTIME_ZIP = os.path.join(CODE, "pyruntime.zip")

_SUDACHI_PROC = None      # None — ещё не пробовали, False — недоступно
_sudachi_warned = False


def _ensure_pyruntime():
    """Развернуть встроенный Python из pyruntime.zip, если его ещё нет."""
    if os.path.isfile(PYRUNTIME_PY):
        return True
    if not os.path.isfile(PYRUNTIME_ZIP):
        return False
    print("-- Собираю встроенный разбор текста (pyruntime, один раз)...")
    with zipfile.ZipFile(PYRUNTIME_ZIP) as zf:
        zf.extractall(CODE)
    return os.path.isfile(PYRUNTIME_PY)


class _SudachiProc(object):
    """Долгоживущий помощник SudachiPy на встроенном Python.

    Один процесс на весь запуск: словарь загружается один раз, каждый
    запрос/ответ — одна строка JSON. При сбое процесс перезапускается
    один раз, дальше — None (тогда читает pyopenjtalk).
    """

    def __init__(self):
        self.proc = None
        self.version = None
        self.dictver = None

    def start(self):
        if not (os.path.isfile(SUDACHI_HELPER) and _ensure_pyruntime()):
            return False
        env = dict(os.environ)
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        try:
            self.proc = subprocess.Popen(
                [PYRUNTIME_PY, SUDACHI_HELPER], cwd=CODE,
                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL, env=env,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            hello = self.proc.stdout.readline()   # приветствие = словарь загружен
            msg = json.loads(hello.decode("utf-8")) if hello else {}
            if not msg.get("ok"):
                self.proc = None
                return False
            self.version = msg.get("version") or "?"
            self.dictver = msg.get("dict") or "?"
            return True
        except Exception:
            self.proc = None
            return False

    def tokenize(self, text):
        """[(поверхность, нормализация, чтение)] или None при сбое."""
        for _ in range(2):                    # при сбое — перезапуск и ещё раз
            if self.proc is None and not self.start():
                return None
            try:
                req = (json.dumps({"id": 1, "text": text},
                                  ensure_ascii=False) + "\n").encode("utf-8")
                self.proc.stdin.write(req)
                self.proc.stdin.flush()
                line = self.proc.stdout.readline()
                if not line:                  # помощник умер — перезапуск
                    self.proc = None
                    continue
                msg = json.loads(line.decode("utf-8"))
                if "error" in msg:
                    return None
                return [tuple(t) for t in msg["tokens"]]
            except Exception:
                self.proc = None
        return None


def sudachi_client():
    """Помощник Sudachi (встроенный Python) или None, если недоступен."""
    global _SUDACHI_PROC, _sudachi_warned
    if _SUDACHI_PROC is None:
        proc = _SudachiProc()
        _SUDACHI_PROC = proc if proc.start() else False
    if _SUDACHI_PROC is False:
        if not _sudachi_warned:
            print("-- Встроенный Sudachi недоступен — иероглифы читает "
                  "pyopenjtalk (словарь постарее).")
            print("   Проверь, что рядом со скриптом лежат pyruntime.zip "
                  "и sudachidict.zip.")
            _sudachi_warned = True
        return None
    return _SUDACHI_PROC


_SUDACHI = None            # запасной ход: Sudachi прямо в интерпретаторе движка


def sudachi_local():
    """Токенизатор SudachiPy ИМЕННО в интерпретаторе движка или None.

    Используется, если пользователь сам поставил туда SudachiPy (любой
    версии) — тогда встроенный Python не нужен.
    """
    global _SUDACHI
    if _SUDACHI is None:
        try:
            from sudachipy import dictionary
            d = dictionary.Dictionary(dict="core")
            _SUDACHI = d.tokenizer() if hasattr(d, "tokenizer") else d.create()
        except Exception:
            _SUDACHI = False
    return _SUDACHI if _SUDACHI else None


# --- ядро чтения: Haqumei (основной ход), в своём встроенном Python -------
# Читает слово В КОНТЕКСТЕ ПРЕДЛОЖЕНИЯ и возвращает готовые чтения с
# позициями. Запасной ход при недоступности — старая цепочка Sudachi.
CORE_HELPER = os.path.join(CODE, "g2p_core.py")

_CORE_PROC = None         # None — ещё не пробовали, False — недоступно
_core_warned = False


class _CoreProc(object):
    """Долгоживущий помощник-ядро (Haqumei) на встроенном Python.

    Протокол как у _SudachiProc: JSON-строки, при сбое перезапуск один раз.
    """

    def __init__(self):
        self.proc = None
        self.version = None

    def start(self):
        if not (os.path.isfile(CORE_HELPER) and _ensure_pyruntime()):
            return False
        env = dict(os.environ)
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        try:
            self.proc = subprocess.Popen(
                [PYRUNTIME_PY, CORE_HELPER], cwd=CODE,
                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL, env=env,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            hello = self.proc.stdout.readline()
            msg = json.loads(hello.decode("utf-8")) if hello else {}
            if not msg.get("ok"):
                self.proc = None
                return False
            self.version = msg.get("version") or "?"
            return True
        except Exception:
            self.proc = None
            return False

    def reads(self, text):
        """[[поверхность, чтение, начало, конец, неизвестно], ...] или None."""
        for _ in range(2):                    # при сбое — перезапуск и ещё раз
            if self.proc is None and not self.start():
                return None
            try:
                req = (json.dumps({"id": 1, "text": text},
                                  ensure_ascii=False) + "\n").encode("utf-8")
                self.proc.stdin.write(req)
                self.proc.stdin.flush()
                line = self.proc.stdout.readline()
                if not line:                  # помощник умер — перезапуск
                    self.proc = None
                    continue
                msg = json.loads(line.decode("utf-8"))
                if "error" in msg:
                    return None
                return [list(w) for w in msg["words"]]
            except Exception:
                self.proc = None
        return None


def core_client():
    """Помощник-ядро (Haqumei) или None, если недоступен."""
    global _CORE_PROC, _core_warned
    if _CORE_PROC is None:
        proc = _CoreProc()
        _CORE_PROC = proc if proc.start() else False
    if _CORE_PROC is False:
        if not _core_warned:
            print("-- Ядро Haqumei недоступно — читает запасная цепочка "
                  "Sudachi + pyopenjtalk.")
            _core_warned = True
        return None
    return _CORE_PROC


def _pyopenjtalk_g2p(text):
    """Запасной ход: Open JTalk (проверенный словарь движка)."""
    global _g2p_warned
    try:
        import pyopenjtalk
        return pyopenjtalk.g2p(text, kana=True)
    except Exception as e:
        if not _g2p_warned:
            print("!! pyopenjtalk недоступен (%s) — иероглифы останутся как есть." % e)
            print("   Установи в интерпретатор движка: %s -m pip install pyopenjtalk"
                  % (PYTHON or r"runtime\python.exe"))
            _g2p_warned = True
        return text


_KATA_ONLY = re.compile(r"^[\u30a0-\u30ff]+$")


def _g2p_core(text):
    """Чтение через ядро Haqumei. None — ядро недоступно/не справилось.

    Haqumei отдаёт слова с позициями в тексте. Важно: поле word — это
    НОРМАЛИЗОВАННАЯ форма (3 -> 三, ﾊﾟﾋﾟｰ -> パピー), а позиция указывает
    в ИСХОДНЫЙ текст. Поэтому исходником истины считается кусок текста
    text[s:e], а по полю word только проверяется, что разметка легла
    честно. Правила:
      * кусок с иероглифами -> чтение (только если word совпал с куском —
        иначе позиция съехала и чтение привяжется не к тому слову,
        возвращаем None и уходим в запасную цепочку Sudachi);
      * цифры -> чтение ядра (оно читает числа как числа: 2024 ->
        二千二十四, а не как дату 二月二日);
      * чистая катакана -> нормализованная форма ядра, если она есть
        (та же защита от ляпсусов словаря, что была в цепочке Sudachi:
        シュミレーション -> シミュレーション);
      * всё прочее (хирагана, знаки, латиница) -> как есть, движок не трогает.
    """
    core = core_client()
    if core is None:
        return None
    words = core.reads(text)
    if not words:
        return None
    out = []
    pos = 0
    for w in words:
        word, read, s, e = w[0], w[1], int(w[2]), int(w[3])
        if not (0 <= pos <= s <= e <= len(text)):
            return None                     # позиции вышли за текст
        if s > pos:                         # пропуск между словами
            gap = text[pos:s]
            if KANJI_RE.search(gap):
                return None                 # пропущен кусок с иероглифами
            out.append(gap)
        surface = text[s:e]                 # исходный текст (не нормализация)
        if KANJI_RE.search(surface):
            if unicodedata.normalize("NFKC", word) != \
                    unicodedata.normalize("NFKC", surface):
                return None                 # разметка съехала — не доверяем
            if not read:
                return None                 # чтения нет — вся цепочка Sudachi
            out.append(read)
        elif any(c.isdigit() for c in surface):
            out.append(read or _pyopenjtalk_g2p(surface))
        elif _KATA_ONLY.match(surface) and word != surface and \
                _KATA_ONLY.match(word or ""):
            out.append(word)                # ляпсус словаря катаканой
        else:
            out.append(surface)             # кана/знаки/латиница — как есть
        pos = e
    if pos < len(text):
        tail = text[pos:]
        if KANJI_RE.search(tail):
            return None                     # хвост с иероглифами не покрыт
        out.append(tail)
    res = "".join(out)
    if any(c.isdigit() for c in res):
        res = _pyopenjtalk_g2p(res)         # цифры внутри чтения (第3条) -> кана
    return res


def g2p_kana(text, furigana_map=None):
    """Иероглифы -> катану: ядро Haqumei + резолвер с доменным словарём.

    Первый ход — ядро (g2p_core.py, Haqumei): слово читается В КОНТЕКСТЕ
    ПРЕДЛОЖЕНИЯ. Затем накладываются переопределения:
      1. furigana_map — чтение из ExpressionFurigana (Опция 1, источник истины,
         если прошло валидацию);
      2. доменный словарь из колод (Опция 2, записанные пользователем чтения);
      3. Haqumei pron (контекстная произносительная форма);
      4. резерв Sudachi / pyopenjtalk.

    Параметр furigana_map: dict {поверхность_слова: чтение_из_фуриганы}.
    Используется при импорте карточек (Опция 1). При отсутствии — работает
    чистый автомат (Опция 2).

    Хирагана/катакана и знаки проходят как есть — их g2p не трогает.
    """
    mods = _ensure_reading_modules()
    if mods is not None and "_error" not in mods:
        domain_dict = mods["domain_dict"]
        core = core_client()
        if core is not None:
            words = core.reads(text)
            if words:
                out = []
                pos = 0
                completed = True
                for w in words:
                    word, read, s, e = w[0], w[1], int(w[2]), int(w[3])
                    if not (0 <= pos <= s <= e <= len(text)):
                        completed = False
                        break                     # позиции вышли за текст
                    if s > pos:                   # пропуск между словами
                        gap = text[pos:s]
                        if KANJI_RE.search(gap):
                            completed = False
                            break                 # пропущен кусок с иероглифами
                        out.append(gap)
                    surface = text[s:e]           # исходный текст
                    if KANJI_RE.search(surface):
                        # 1. Фуригана (Опция 1) — источник истины, если валидна
                        furi = furigana_map.get(surface) if furigana_map else None
                        if furi:
                            out.append(_normalize_furigana(furi))
                        # 2. Доменный словарь (Опция 2) — записанные чтения
                        elif domain_dict is not None:
                            entry = domain_dict.lookup(surface)
                            if entry:
                                out.append(entry.reading)
                            else:
                                # 3. Чтение из ядра (уже содержит pron/сандхи
                                #    из контекста целого предложения)
                                out.append(read if read else surface)
                        else:
                            out.append(read if read else surface)
                    elif any(c.isdigit() for c in surface):
                        out.append(read or _pyopenjtalk_g2p(surface))
                    elif _KATA_ONLY.match(surface) and word != surface and \
                            _KATA_ONLY.match(word or ""):
                        out.append(word)            # ляпсус словаря катаканой
                    else:
                        out.append(surface)         # кана/знаки/латиница — как есть
                    pos = e
                if completed:
                    tail = text[pos:]
                    if not KANJI_RE.search(tail):
                        out.append(tail)
                    res = "".join(out)
                    if any(c.isdigit() for c in res):
                        res = _pyopenjtalk_g2p(res)  # цифры внутри чтения
                    return res
    # Fallback: исходный _g2p_core без резолвера
    res = _g2p_core(text)
    if res is not None:
        return res
    toks = None
    client = sudachi_client()
    if client is not None:
        toks = client.tokenize(text)
    if toks is None:                       # запасной ход: Sudachi в движке
        loc = sudachi_local()
        if loc is not None:
            toks = [(m.surface(), m.normalized_form(), m.reading_form())
                    for m in loc.tokenize(text)]
    if toks is None:
        return _pyopenjtalk_g2p(text)
    out = []
    for s, nf, r in toks:
        if KANJI_RE.search(s):
            if r and r != "?" and not KANJI_RE.search(r):
                out.append(r)
            else:
                out.append(_pyopenjtalk_g2p(s) or s)
        elif any(c.isdigit() for c in s):
            out.append(_pyopenjtalk_g2p(s))
        else:
            if nf != s and _KATA_ONLY.match(s or "") and _KATA_ONLY.match(nf):
                s = nf
            out.append(s)
    res = "".join(out)
    if any(c.isdigit() for c in res):
        res = _pyopenjtalk_g2p(res)      # цифры внутри чтения (第3条) -> кана
    return res


def kanaize(text, furigana_map=None):
    """Текст -> хирагана: NFKC -> словарь -> латиница катаканой -> сегменты
    -> g2p только иероглифы -> хирагана.

    Главный принцип: MeCab надёжно читает иероглифы и катакану, но портит
    уже готовую хирагану (применяет правила частиц: こんにちは -> コンничива).
    Поэтому ядру Haqumei подаётся текст с катеканой как есть — она даёт
    контекст для чтения иероглифов (ビェниャク殿 -> ドノ, а не ТОНО),
    а хирагана/цифры/знаки проходят мимо g2p без изменений.

    Шаги подробно (важно для сложных слов):
      1. NFKC-нормализация: полноразмерная латиница/цифры (ＡＢＣ１２３ -> ABC123),
         полукатакана с дакутеном (ｶﾞ -> ガ) и съёмные знаки (か+゙ -> ガ)
         сводятся к обычным формам — без этого MeCab видит «неразбиваемые»
         мусорные символы и ломает разбор всего предложения.
      2. Латиница -> катакана по буквам (IEC -> アイイーシー).
      3. Текст с иероглифами гоняется через g2p ТОЛЬКО там, где есть
         иероглифы. Готовая хирагана, цифры и знаки идут мимо g2p — их
         MeCab не портит.
      4. Всё приводится к хирагане, кроме «защищённых» слов _KEEP_KATA
         (их хирагану MeCab читает как частицу, поэтому оставляем катаканой).

    Результат кэшируется: одни и те же слова повторяются между карточками,
    а g2p (MeCab) — самая дорогая часть конвейера.
    """
    if furigana_map is not None:
        # Не кэшируем, когда есть внешние переопределения фуриганы
        t = normalize_text(text)
        t = latin2kana(t)
        if KANJI_RE.search(t):
            t = g2p_kana(t, furigana_map=furigana_map)
        result = kata2hira(t, keep_kata=_KEEP_KATA).strip()
        return result

    hit = _KANA_CACHE.get(text)
    if hit is not None:
        return hit
    t = normalize_text(text)
    t = latin2kana(t)

    if KANJI_RE.search(t):
        t = g2p_kana(t)

    result = kata2hira(t, keep_kata=_KEEP_KATA).strip()
    if len(_KANA_CACHE) >= 8192:
        _KANA_CACHE.clear()          # раздуваться бесконечно не даём
    _KANA_CACHE[text] = result
    return result


def _normalize_furigana(furigana: str) -> str:
    """Привести фуригану из хирагены в катану для сравнения с чтениями движков."""
    out = []
    for c in furigana:
        o = ord(c)
        if 0x3041 <= o <= 0x3096:  # хирагана -> катакана (+0x60)
            out.append(chr(o + 0x60))
        else:
            out.append(c)
    return "".join(out)


def _parse_furigana(furigana: str, expression: str = "") -> str:
    """
    Извлечь чистое чтение из поля фуриганы.

    Поддерживаемые форматы:
      * いけばな — чистое чтение без разметки
      * 生花[いけばな,せいか] — разметка на всё слово (берём первое чтение)
      * 遠隔[えんかく]監督[かんとく]・検査[けんさ] — разметка по частям слова:
        чтения склеиваются, сами основы-иероглифы отбрасываются
      * 食[た]べる — разметка только на иероглифах, окуригана своя

    expression (если передан) помогает отличить разметку на всё слово
    (生花[いけばな] -> «いけばな») от частичной (食[た]べる -> «たべる»).

    Возвращает чтение целиком: «いけばな», «えんかくかんとく・けんさ».
    """
    furigana = furigana.strip()
    if not furigana or "[" not in furigana:
        return furigana

    segs = re.split(r"(\[[^\[\]]*\])", furigana)

    def _is_br(s):
        return len(s) > 1 and s.startswith("[") and s.endswith("]")

    def _content(s):
        return s[1:-1].split(",", 1)[0].strip()

    def _concat():
        out = []
        for i, s in enumerate(segs):
            if not s:
                continue
            if _is_br(s):
                out.append(_content(s))
            elif i + 1 < len(segs) and _is_br(segs[i + 1]):
                # основа перед скобкой: её иероглифы уже покрыты чтением,
                # кана/знаки перед ними (окуригана, «・», латиница) остаются
                m = re.search(r"[\u3005\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff"
                              r"\U00020000-\U0003FFFF]+$", s)
                keep = s[:m.start()] if m else s
                if keep:
                    out.append(keep)
            else:
                out.append(s)
        return "".join(out)

    idxs = [i for i, s in enumerate(segs) if _is_br(s)]
    if len(idxs) == 1:
        base = segs[idxs[0] - 1] if idxs[0] > 0 else ""
        expr = (expression or "").strip()
        if not expr or base == expr or not re.search(
                r"[\u3005\u3400-\u4dbf\u4e00-\u9fff]", base):
            # разметка на всё слово (либо выражение не известно) -> одно чтение
            return _content(segs[idxs[0]])
    return _concat()


def kanaize_card(text, expression=None, furigana=None):
    """
    Текст карточки -> хирагана с приоритетом фуриганы для основного слова.

    Параметры:
      text      — текст предложения (Sentence)
      expression — основное слово карточки (Expression)
      furigana  — фуригана к основному слову (ExpressionFurigana)

    Логика:
      * Основное слово (expression) читается строго по furigana — это
        проверенное эталонное чтение, его не угадываем через Haqumei/Sudachi.
        Чтение подставляется ПОДСТРОЧНО: нашли написание слова в тексте и
        заменили на готовое чтение. Поэтому работает и для иероглифов, и для
        латиницы/цифр (PLATEAU[ぷらとー], 3D都市モデル[すりーでぃー…]).
      * Все остальные слова читаются автоматически (как kanaize).
      * Если expression или furigana пустые либо слова нет в тексте —
        работает как обычный kanaize.

    Не кэшируется (разные карточки — разные фуриганы).
    """
    if not expression or not furigana:
        return kanaize(text)

    reading = _parse_furigana(furigana, expression=expression)
    if not reading:
        return kanaize(text)

    norm_expr = normalize_text(expression)
    t = normalize_text(text)

    if norm_expr and norm_expr in t:
        # проверенное чтение вместо написания основного слова
        return kanaize(t.replace(norm_expr, reading))

    # латиница в предложении может отличаться регистром (PLATEAU vs plateau)
    if norm_expr and re.search(r"[A-Za-z]", norm_expr):
        pat = re.compile(re.escape(norm_expr), re.IGNORECASE)
        if pat.search(t):
            return kanaize(pat.sub(lambda _m: reading, t))

    # основного слова в тексте нет — читаем всё автоматически
    return kanaize(text)


def kanaize_from_fields(text, fields=None, field_names=None):
    """
    Текст карточки -> хирагана с приоритетом фуриганы для основного слова,
    где expression и furigana берутся из полей карточки.

    Параметры:
      text       — текст предложения (Sentence)
      fields     — dict с полями карточки (expression, furigana и т.д.)
      field_names — набор имён полей. Если не задан, берутся из DEFAULT_FIELDS:
                    word_src -> поле с основным словом
                    furigana_src -> поле с фуриганой

    Логика:
      * Основное слово читается строго по furigana из указанного поля.
      * Все остальные слова читаются автоматически.
      * Если поля не найдены или пустые — работает как обычный kanaize.
    """
    if field_names is None:
        field_names = DEFAULT_FIELDS

    if fields is None:
        return kanaize(text)

    expression = fields.get(field_names.get("word_src", "Expression"), "")
    furigana = fields.get(field_names.get("furigana_src", "ExpressionFurigana"), "")

    if not expression or not furigana:
        return kanaize(text)

    return kanaize_card(text, expression=expression, furigana=furigana)


_KANA_CACHE = {}


def _base_reading(base, reading):
    """Чтение для пары «основа[чтение]» в колоде.

    В колоде два вида разметки:
      * чтение покрывает ТОЛЬКО иероглифы, кана в основе — своя окуригана
        (き継[つ] -> «き» + «つ»);
      * чтение покрывает иероглифы И латиницу
        (IEC規格[アイイーシーきかく] -> «アイイーシーきかく» целиком).
    Поэтому кана-окуригану в основе оставляем, а латиницу НЕ оставляем —
    её звучание уже есть в начале чтения, иначе задвоится
    (IEC прочиталось бы дважды).
    """
    if not KANJI_RE.search(base):
        return reading                       # иероглифов нет — чтение целиком
    rest = KANJI_RE.sub("", base)            # окуригана и латиница
    if re.search(r"[A-Za-z]", rest):
        return reading                       # латиницу покрывает чтение
    return rest + reading                    # кана-окуригана своя + чтение


def furiga_pair(text):
    """(поверхность, чтение) для разметки «основа[чтение]…хвост».

    «相欠[あいが]き継[つ]ぎ» -> («相欠き継ぎ», «あいがきつぎ»).
    Хвост после последней скобки без чтения остаётся как есть.
    (None, None) — если разметки нет.
    """
    if "[" not in text:
        return None, None
    parts = re.split(r"\[([^\[\]]*)\]", text)
    last = len(parts) - 1
    surf, read = [], []
    i = 0
    while i < len(parts):
        if i % 2 == 1:
            i += 1                           # чтение обрабатывается с основой
            continue
        if i == last:
            surf.append(parts[i])
            read.append(parts[i])
        else:
            surf.append(parts[i])
            read.append(_base_reading(parts[i], parts[i + 1]))
            i += 1
        i += 1
    return "".join(surf), "".join(read)


def expression_inject_pair(note, reading_field):
    """(написание_слова, полное_чтение) — для подстановки в предложение.

    Написание — как слово стоит в предложении («相欠き継ぎ»), чтение —
    собранное целиком («あいがきつぎ»). Источник чтения — ТОЛЬКО указанное
    поле (режима «авто» больше нет):
      * простое чтение («あいが») — берётся как есть;
      * фуриганная разметка («相欠[あいが]き») — разбирается, берётся
        кана целиком (удобно указывать готовое поле ExpressionFurigana).
    (None, None) — подстановка невозможна: в Expression нет иероглифов,
    поле пустое, разметка не совпала со словом или в «чтении» остались
    иероглифы.
    """
    f = note["fields"]

    def fld(name):
        return plain(f.get(name, {}).get("value", ""))

    surface = re.sub(r"\[[^\[\]]*\]", "", fld("Expression")).strip()
    if not surface or not KANJI_RE.search(surface):
        return None, None                    # иероглифов нет — нечего подставлять
    reading = fld(reading_field).strip()
    if not reading:
        return None, None                    # поле пустое — подстановки нет
    if "[" in reading:
        fur_surf, fur_read = furiga_pair(reading)
        if fur_surf is None or fur_surf.strip() != surface:
            return None, None                # разметка не совпала со словом — риск
        reading = (fur_read or "").strip()
    if not reading or reading == surface:
        return None, None
    if KANJI_RE.search(reading):
        return None, None                    # иероглифы в «чтении» — это не чтение
    return surface, reading


def inject_reading(sentence, note, reading=""):
    """Вставить проверенное чтение в предложение вместо иероглифов.

    Идея: карточка уже содержит ПРАВИЛЬНОЕ чтение сложного слова, а API
    GPT-SoVITS принимает только текст (канала «готовое чтение» у него нет).
    Значит, подставляем чтение прямо в текст: движок увидит хирагану и не
    сможет ошибиться в редком термине (合折釘, 相欠き継ぎ и т.п.).

    Источник чтения (параметр reading) — только два режима:
      * "off" или "" — подстановки нет, движок читает предложение само;
      * имя поля — чтение слова строго из этого поля (пользователь заранее
        знает правильное чтение необычного слова). Поле содержит простое
        чтение либо фуриганную разметку.
    """
    if not reading or reading == "off":
        return sentence
    kanji, rd = expression_inject_pair(note, reading_field=reading)
    if not kanji or not rd:
        return sentence
    if kanji not in sentence:
        return sentence
    return sentence.replace(kanji, kata2hira(rd))


# --------------------------------------------------------------- синтез
def _tts_start_config():
    cfg = load_voices()
    return os.path.join(ENGINE, cfg.get("start_config") or DEFAULT_START_CONFIG)


_RESURRECT = {"left": 3}      # сколько раз за прогон можно поднять упавший сервер


def _resurrect(v):
    """Сервер упал (упал при старте, убит, обрыв) — поднять заново.

    Возвращает True, если сервер снова готов с нужными весами. Ограниченное
    число попыток: если сервер падает стабильно, батчу лучше встать сразу
    с понятной ошибкой, чем ждать по 600 с на каждой карточке."""
    if _RESURRECT["left"] <= 0:
        return False
    _RESURRECT["left"] -= 1
    print("Сервер не отвечает — поднимаю заново (осталось попыток: %d)..."
          % (_RESURRECT["left"] + 1))
    start_server(_tts_start_config(), wait=240)
    ensure_voice(v, force=True)
    return True


def _ffmpeg_exe():
    """ffmpeg из папки движка (или из PATH) — для проверки качества звука."""
    p = os.path.join(ENGINE, "runtime", "ffmpeg.exe")
    if os.path.exists(p):
        return p
    try:
        import shutil
        return shutil.which("ffmpeg") or ""
    except Exception:
        return ""


def audio_stats(blob, ext="ogg"):
    """Разбирает синтезированный файл: (длительность с, звучащая длительность с).

    Декодирует через ffmpeg в сырой PCM (16 кГц, моно) и считает, сколько
    времени сигнал реально звучит. Нужно, чтобы ловить главный сбой
    GPT-SoVITS: файл с 25–40 с тишины и крошечным куском речи в конце —
    байтов он при этом нормальный, поэтому «пустой ответ» его не отловит.
    Возвращает (0.0, 0.0), если разобрать не удалось (тогда проверка молчит).
    """
    ff = _ffmpeg_exe()
    if not ff:
        if os.environ.get("AV_DEBUG_QC"):
            print("  [qc] ffmpeg не найден; ENGINE=%r" % (ENGINE,))
        return 0.0, 0.0
    import subprocess
    cmd = [ff, "-v", "error", "-i", "pipe:0", "-f", "s16le",
           "-ac", "1", "-ar", "16000", "pipe:1"]
    try:
        r = subprocess.run(cmd, input=blob, capture_output=True, timeout=120)
        raw = r.stdout
    except Exception as e:
        if os.environ.get("AV_DEBUG_QC"):
            print("  [qc] ffmpeg не запустился: %r" % (e,))
        return 0.0, 0.0
    if len(raw) < 4:
        if os.environ.get("AV_DEBUG_QC"):
            print("  [qc] ffmpeg дал %d Б (rc=%s, stderr=%r)"
                  % (len(raw), r.returncode,
                     r.stderr.decode("utf-8", "replace")[:200]))
        return 0.0, 0.0
    try:
        import numpy as np
        x = np.frombuffer(raw, dtype="<i2").astype("float32") / 32768.0
    except Exception as e:
        if os.environ.get("AV_DEBUG_QC"):
            print("  [qc] numpy не справился: %r" % (e,))
        return 0.0, 0.0
    sr = 16000
    dur = len(x) / sr
    win = max(1, int(sr * 0.02))                 # окно 20 мс
    n = len(x) // win
    if n == 0:
        return dur, 0.0
    rms = np.array([np.sqrt((x[i*win:(i+1)*win] ** 2).mean()) for i in range(n)])
    thr = max(float(rms.max()) * 0.05, 1e-4)
    sounding = float((rms > thr).sum() * win / sr)
    return dur, sounding


def _synth_is_sane(text, dur, sounding):
    """True, если звук похож на речь, а не на пустоту.

    Норма для японского — примерно 0.15 с речи на знак. Мусорный ответ
    сервера отличается надёжно: общая длительность в разы больше ожидаемой
    (лишнее — тишина) либо звучащей речи почти нет.

    Короткие слова (つゆ, どの) проверяем мягче: для них крохотная длительность
    — норма, важнее доля звука в файле и отсутствие «пустого хвоста».
    """
    if dur == 0.0 and sounding == 0.0:
        return True                      # разобрать не удалось — не мешаем
    if sounding < 0.15:
        return False                     # речи практически нет
    expect = 0.15 * len(text)            # ожидаемая длительность речи
    if dur > max(8.0, expect * 3):
        return False                     # файл в разы длиннее ожидаемого
    if dur > 6.0 and sounding < expect * 0.5:
        return False                     # длинный файл, а речи почти нет
    return True


# ------------------------------------------------- многосигнальная проверка
_QC_V2 = {"state": "unset"}              # "unset" -> "ok"/"none"


def _qc_v2_module():
    """lab/quality_v2 — независимый анализатор (долгое молчание, разрывы
    внутри речи, дубль речи, обрезка, уровень, скорость мор/с).

    Лениво и с откатом: если lab/ недоступен (например, собранный .exe без
    исходников) или модуль не импортируется, остаётся старый простой
    критерий _synth_is_sane.
    """
    if _QC_V2["state"] != "unset":
        return _QC_V2.get("mod")
    try:
        lab = os.path.join(CODE, "lab")
        if lab not in sys.path:
            sys.path.append(lab)
        import quality_v2 as q2
        _QC_V2["mod"] = q2
        _QC_V2["state"] = "ok"
    except Exception as e:
        if os.environ.get("AV_DEBUG_QC"):
            print("  [qc] quality_v2 недоступен: %r" % (e,))
        _QC_V2["mod"] = None
        _QC_V2["state"] = "none"
    return _QC_V2["mod"]


def _check_audio(blob, ext, text):
    """(список сигналов, годен ли файл). Сигналы — для лога.

    Возвращает ([], True), если разобрать не удалось: не мешаем работе,
    но однократно предупреждаем — качество тогда не контролируется.
    """
    q2 = _qc_v2_module()
    if q2 is None:
        dur, snd = audio_stats(blob, ext)
        return ([], True) if _synth_is_sane(text, dur, snd) else (["тишина"], False)
    ff = q2.ffmpeg_exe(ENGINE)
    if not ff:
        return ([], True)                   # некому проверить — не мешаем
    m = q2.analyze(blob, ff)
    if not m.get("ok"):
        # ffmpeg есть, а файл не декодируется — битый ответ сервера
        return (["не декодируется"], False)
    sigs, is_bad = q2.verdict(m, text)
    return sigs, not is_bad


# Куда складывать отбракованный звук (чтобы можно было послушать и
# проверить: правильно ли детектор отклонил). Отключается AV_QC_KEEP=0.
QC_REJECT_DIR = os.path.join(CODE, "lab", "rejected")


def keep_rejected(blob, ext, text, sigs, attempt, meta=None):
    """Сохранить отбракованный файл + запись в index.jsonl.

    Возвращает (имя_файла, причины) либо (None, причины), если сохранить
    не удалось. Ошибка сохранения никогда не должна ломать озвучку.
    """
    if os.environ.get("AV_QC_KEEP", "1") == "0":
        return None, sigs
    try:
        os.makedirs(QC_REJECT_DIR, exist_ok=True)
        h = hashlib.sha1(("v2|%s|%d" % (text, attempt)).encode("utf-8")
                         ).hexdigest()[:10]
        name = "rej_%s_%s.%s" % (time.strftime("%Y%m%d_%H%M%S"), h, ext)
        path = os.path.join(QC_REJECT_DIR, name)
        with open(path, "wb") as f:
            f.write(blob)
        rec = {"file": name, "text": text, "reasons": list(sigs),
               "attempt": attempt, "at": time.strftime("%Y-%m-%d %H:%M:%S")}
        if meta:
            rec.update(meta)
        with open(os.path.join(QC_REJECT_DIR, "index.jsonl"), "a",
                  encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return name, sigs
    except Exception as e:
        if os.environ.get("AV_DEBUG_QC"):
            print("  [qc] не смог сохранить брак: %r" % (e,))
        return None, sigs


def _synth_once(v, text, seed=42, speed=1.0, _oom_retry=True, **overrides):
    # Sampling defaults follow the official GPT-SoVITS webui (calmer than the raw
    # API defaults of temperature=1.0 / top_p=1.0, which sound over-expressive).
    # Any of these can be overridden per voice in voices.json.
    payload = {
        "text": text,
        "text_lang": "ja",
        "ref_audio_path": v["ref"],
        "aux_ref_audio_paths": v.get("aux") or [],
        "prompt_text": v.get("prompt_text", ""),
        "prompt_lang": v.get("prompt_lang", "ja"),
        "text_split_method": "cut5",
        "batch_size": 1,
        "speed_factor": speed,
        "media_type": "ogg",
        "streaming_mode": False,
        "seed": seed,
        "temperature": float(v.get("temperature", 0.6)),
        "top_p": float(v.get("top_p", 0.6)),
        "top_k": int(v.get("top_k", 20)),
    }
    payload.update(overrides)           # переопределения из стратегий спасения

    def post(media_type):
        payload["media_type"] = media_type
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(TTS_URL + "/tts", data=data,
                                     headers={"Content-Type": "application/json"})
        try:
            with _NO_PROXY.open(req, timeout=600) as resp:
                return resp.read(), None
        except urllib.error.HTTPError as e:
            try:
                return None, e.read().decode("utf-8", "replace")
            except Exception:
                return None, "HTTP %s" % e.code
        except Exception as e:
            return None, str(e)

    blob, err = post("ogg")
    if blob is None and _oom_retry and err and \
            ("out of memory" in err or "CUDA" in err):
        # видеопамять переполнена (GPU занят чужими процессами или накопились
        # неудачные запросы) — полный перезапуск сервера даёт свежую память;
        # повторяем один раз, чтобы пачка озвучки не вставала целиком
        print("Не хватает видеопамяти — перезапускаю сервер и повторяю...")
        restart_server(_tts_start_config())
        ensure_voice(v, force=True)
        return synth(v, text, seed=seed, speed=speed, _oom_retry=False)
    if blob is None and _oom_retry and err and \
            any(s in err for s in ("10061", "refused", "urlopen error", "timed out")):
        # сервер упал/перезагружается — поднимаем заново и повторяем разок
        if _resurrect(v):
            return synth(v, text, seed=seed, speed=speed, _oom_retry=False)
    if blob is None:
        blob, err = post("wav")             # ogg может не поддерживаться
    if blob is None:
        raise SystemExit("сервер отказал: %s" % (err or "нет ответа")[:300])
    if len(blob) < 1024:
        # сервер ответил почти пустым телом (обрыв/уступка памяти на GPU) —
        # такое нельзя сохранять как «озвучено»: перезапуск сервера даёт
        # свежую память и обычно чинит ситуацию (как при CUDA OOM выше)
        if _oom_retry:
            print("Сервер вернул пустой звук — перезапускаю сервер и повторяю...")
            restart_server(_tts_start_config())
            ensure_voice(v, force=True)
            return synth(v, text, seed=seed, speed=speed, _oom_retry=False)
        raise SystemExit("сервер вернул пустой звук (%d байт) — попробуй ещё раз"
                         % len(blob))
    return blob, "ogg" if payload["media_type"] == "ogg" else "wav"


# схема спасения брака: (зарезервировано, подпись, что печатать в логе).
# В synth() стратегия выбирается по подписи: сид -> температура ->
# без промпта -> без промпта+сид -> другая разбивка -> без промпта+разбивка.
_QC_ATTEMPTS = (
    (None,    "сид",               "повторяю с другим сидом..."),
    (None,    "сид+температура",   "пробую с температурой 0.8..."),
    ("noref", "без промпта",       "пробую без текста референса..."),
    ("noref2", "без промпта+сид",  "пробую без промпта и с другим сидом..."),
    ("split0", "другая разбивка",  "пробую без разбиения текста на куски..."),
    ("nrefs0", "без промпта+разбивка",
     "пробую без промпта и без разбиения..."),
)


_QC_BLIND = [False]      # уже предупреждали, что проверить звук не удалось


def synth(v, text, seed=42, speed=1.0, _oom_retry=True):
    """Синтез с проверкой качества на входе в колоду.

    GPT-SoVITS иногда возвращает файл, где 25–40 с тишины и крошечный
    кусочек речи в самом конце: байтов нормально, длины хватает, но
    слушать нечего. Такой файл раньше уходил в карточку как «озвучено».
    Теперь проверяем звук (audio_stats) и при мусоре пробуем спасение:
    другой сид -> другая температура -> без текста референса -> ещё раз.
    Не помогло — ошибка, карточка остаётся неозвученной и видна в отчёте.
    """
    v_prompt = v.get("prompt_text", "")
    # Текста для чтения нет (только пунктуация, пробелы, ссылки на медиа) —
    # сервер всё равно откажет «有効なテキст...», а 6 попыток и FAIL в отчёте
    # будут лишь шумом. Это не ошибка озвучки, а пустая карточка.
    q2 = _qc_v2_module()
    if q2 is not None and q2.sound_chars(text) == 0:
        print("  [%s] нечего озвучивать — пропускаю" % text[:24])
        raise SystemExit("пустой текст: озвучивать нечего")
    tried = 0
    for _, what, msg in ((None, None, None),) + _QC_ATTEMPTS:
        if tried:
            print("  [%s] %s: %s" % (text[:24], what, msg))
        s, tv, nv, extra = seed, v, v_prompt, {}
        if what == "сид":
            s = seed + tried * 7 + 1
        elif what == "сид+температура":
            tv = dict(v); tv["temperature"] = 0.8
        elif what == "без промпта":
            nv = ""
        elif what == "без промпта+сид":
            nv = ""
            s = seed + tried * 13 + 3
        elif what == "другая разбивка":
            extra = {"text_split_method": "cut0"}
        elif what == "без промпта+разбивка":
            nv = ""
            extra = {"text_split_method": "cut0"}
        tv = dict(tv)
        if nv == "":
            tv["prompt_text"] = ""
        blob, ext = _synth_once(tv, text, seed=s, speed=speed,
                                _oom_retry=_oom_retry, **extra)
        sigs, ok = _check_audio(blob, ext, text)
        if ok:
            return blob, ext
        if not _QC_BLIND[0] and not sigs:
            _QC_BLIND[0] = True
            print("  ! проверить звук не удалось — качество не контролируется")
        tried += 1
        kept, _ = keep_rejected(blob, ext, text, sigs, tried,
                                meta={"strategy": what or "сид(по умолчанию)"})
        print("  [%s] брак: %s%s%s"
              % (text[:24], ", ".join(sigs) or "пустой ответ",
                 "" if msg is None else " — " + msg,
                 "" if kept is None else "  [сохранён: %s]" % kept))
    raise SystemExit("после %d попыток синтез даёт брак — карточка пропущена"
                     % tried)


def media_name(nid, field, text, ext, voice):
    h = hashlib.sha1(("v1|%d|%s|%s|%s" % (nid, field, text, voice))
                     .encode("utf-8")).hexdigest()[:10]
    return "tts_%s_%d_%s_%s.%s" % (voice, nid, field.lower(), h, ext)


# ----------------------------------------------------- операции с колодами
def word_text(note, word_src, reading=""):
    """Текст слова из поля word_src.

    word_src == 'Expression' учитывает режим источника reading:
      * "off"/"" — написание без разметки, движок читает его само;
      * имя поля — готовое чтение строго из этого поля (простое чтение
        либо фуриганная разметка); поле пустое — как при off.
    Для произвольного поля word_src — просто текст поля."""
    if word_src == "Expression":
        if reading and reading != "off":
            v = plain(note["fields"].get(reading, {}).get("value", ""))
            if "[" in v:                      # поле с фуриганой -> кана целиком
                _, v = furiga_pair(v)
                v = (v or "").strip()
            if v:
                return v
        return re.sub(r"\[[^\[\]]*\]", "",
                      plain(note["fields"].get("Expression", {})
                            .get("value", ""))).strip()
    return plain(note["fields"].get(word_src, {}).get("value", ""), strip_media=True)


def _speakable(text):
    """Есть ли в тексте хотя бы один звуковой знак.

    «！？…» или поле, состоящее из ссылок на медиа, — синтезировать нечего:
    сервер откажет, а 6 попыток и FAIL в отчёте будут лишь шумом. Если
    quality_v2 недоступен (собранный .exe), возвращаем True — не мешаем.
    """
    q2 = _qc_v2_module()
    if q2 is None:
        return True
    return q2.sound_chars(text) > 0


def build_jobs(notes, mode, force, fields=None):
    fields = fields or DEFAULT_FIELDS
    jobs = []
    for n in notes:
        f = n["fields"]

        def tgt(name):
            return plain(f.get(name, {}).get("value", ""))

        def tgt_text(name):
            # текст на синтез: [sound:...] внутри поля вырезаем
            return plain(f.get(name, {}).get("value", ""), strip_media=True)

        if mode in ("sentence", "both"):
            text = tgt_text(fields["sentence_src"])
            if text and (force or not tgt(fields["sentence_audio"])):
                # вставляем чтение сложного слова в предложение (источник:
                # отключено либо конкретное поле карточки)
                text = inject_reading(text, n, reading=fields.get("reading", ""))
                # kanaize_from_fields: основное слово читается по
                # ExpressionFurigana, остальное — автоматически
                # (поля раскладываем в простые строки: внутри f лежит
                #  формат AnkiConnect {"value": ...})
                flat = {k: plain(v.get("value", ""))
                        for k, v in f.items() if isinstance(v, dict)}
                text = kanaize_from_fields(text, fields=flat, field_names=fields)
                if not _speakable(text):        # только пунктуация и медиа
                    continue
                jobs.append((n["noteId"], fields["sentence_audio"], text))
        if mode in ("expression", "both"):
            text = word_text(n, fields["word_src"], reading=fields.get("reading", ""))
            if text and (force or not tgt(fields["word_audio"])):
                # Фуригана для основного слова — из настраиваемого поля
                furigana = plain(f.get(fields.get("furigana_src", "ExpressionFurigana"),
                                       {}).get("value", ""))
                expression = plain(f.get(fields.get("word_src", "Expression"),
                                         {}).get("value", ""))
                text = kanaize_card(text, expression=expression, furigana=furigana)
                if not _speakable(text):        # только пунктуация и медиа
                    continue
                jobs.append((n["noteId"], fields["word_audio"], text))
    return jobs


def voice_notes(ids, voice_name, mode="both", force=False, seed=42, speed=1.0,
                fields=None):
    v = get_voice(voice_name)
    notes = notes_info(ids)
    jobs = build_jobs(notes, mode, force, fields=fields)
    if not jobs:
        print("Всё уже озвучено (или пустой текст). --force — переделать.")
        return 0, 0
    print("К озвучке: %d операций в %d карточках (голос '%s', mode=%s)"
          % (len(jobs), len({j[0] for j in jobs}), v["name"], mode))
    ensure_voice(v)
    done, failed = 0, 0
    cache = {}
    for nid, field, text in jobs:
        try:
            key = (text, seed, speed)
            if key not in cache:
                cache[key] = synth(v, text, seed=seed, speed=speed)
                time.sleep(0.2)
            blob, ext = cache[key]
            fname = media_name(nid, field, text, ext, v["name"])
            stored = ac("storeMediaFile", filename=fname, overwrite=True,
                        data=base64.b64encode(blob).decode("ascii"))
            if stored != fname:
                fname = stored
            ac("updateNoteFields", note={"id": nid, "fields": {field: "[sound:%s]" % fname}})
            done += 1
            print("OK   [%d] %-16s %s (%s, %.0f КБ)"
                  % (nid, field, text[:40], ext, len(blob) / 1024))
        except SystemExit as e:
            failed += 1
            print("FAIL [%d] %s: %s" % (nid, field, e))
        except Exception as e:
            failed += 1
            msg = str(e)
            if "editor" in msg.lower():
                msg += "  <- закой карточку в редакторе Anki"
            print("FAIL [%d] %s: %s" % (nid, field, msg))
    print("\nГотово: %d, ошибок: %d" % (done, failed))
    return done, failed


def clone_cards(query, to_deck, limit=None, tag=None, force=False, fields=None):
    cfg = fields or DEFAULT_FIELDS
    afs = set(audio_fields(cfg))
    existing = ac("findNotes", query='deck:"%s"' % to_deck)
    if existing and not force:
        raise SystemExit("Колода '%s' уже содержит %d карточек — дозови командой voice "
                         "или добавь --force, чтобы клонировать ещё набор."
                         % (to_deck, len(existing)))
    ids = ac("findNotes", query=query)
    if limit:
        ids = ids[:limit]
    if not ids:
        raise SystemExit("По запросу '%s' ничего не найдено." % query)
    ac("createDeck", deck=to_deck)
    created = []
    for n in notes_info(ids):
        nfields = {}
        for k, val in n["fields"].items():
            nfields[k] = "" if k in afs else val["value"]
        tags = list(n.get("tags") or [])
        if tag and tag not in tags:
            tags.append(tag)
        nid = ac("addNote", note={
            "deckName": to_deck, "modelName": n["modelName"], "fields": nfields,
            "options": {"allowDuplicate": True, "duplicateScope": "deck"},
            "tags": tags,
        })
        created.append(nid)
    print("Склонировано в '%s': %d карточек." % (to_deck, len(created)))
    return created


def check_deck(deck, fields=None, verify_files=True):
    """verify_files=False — быстрая проверка (только поля, без скачивания
    аудиофайлов из Anki; на больших колодах это десятки МБ и минуты)."""
    cfg = fields or DEFAULT_FIELDS
    afs = audio_fields(cfg)
    ids = ac("findNotes", query='deck:"%s"' % deck)
    if not ids:
        print("Колода '%s' не найдена или пуста (опечатка в имени?)." % deck)
        return False
    ok, problems = 0, []
    for n in notes_info(ids):
        expr = plain(n["fields"].get(cfg["word_src"], {}).get("value", ""))
        bad = []
        for fld in afs:
            tag = plain(n["fields"].get(fld, {}).get("value", ""))
            m = re.search(r"\[sound:([^\]]+)\]", tag)
            if not m:
                bad.append("%s пусто" % fld)
            elif verify_files and not ac("retrieveMediaFile", filename=m.group(1)):
                bad.append("%s: файл %s пропал" % (fld, m.group(1)))
        if bad:
            problems.append((n["noteId"], expr, "; ".join(bad)))
        else:
            ok += 1
    print("Колода '%s': %d карточек, из них полностью готово: %d"
          % (deck, len(ids), ok))
    for nid, expr, msg in problems:
        print("  ПРОБЛЕМА [%d] %s: %s" % (nid, expr, msg))
    return len(problems) == 0


# --------------------------------------------------------- один экземпляр
_LOCK_HANDLE = None


def acquire_lock():
    """Один экземпляр пайплайна.

    Два параллельных запуска дерутся за веса и перезапуск сервера — второй
    получает понятную ошибку вместо тихой порчи звука. Блокировка снимается
    сама при выходе процесса (закрытие файла)."""
    global _LOCK_HANDLE
    require_engine()
    lockp = os.path.join(ENGINE, "logs", "pipeline.lock")
    os.makedirs(os.path.dirname(lockp), exist_ok=True)
    f = open(lockp, "a+")
    try:
        import msvcrt
        msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        f.close()
        raise SystemExit(
            "Пайплайн уже запущен другим процессом (%s).\n"
            "Дождись его завершения (или убой зависший процесс)." % lockp)
    _LOCK_HANDLE = f


# --------------------------------------------------------------- команды
def ask(prompt, default=None):
    suffix = " [%s]" % default if default else ""
    v = input(prompt + suffix + ": ").strip()
    return v or (default or "")


def cmd_list(args=None):
    cfg = load_voices()
    if not cfg["voices"]:
        print("Голосов пока нет. Добавь: voice_pipeline.py add ...")
        return
    print("Голоса (по умолчанию: %s):" % (cfg.get("default_voice") or "—"))
    for name, v in sorted(cfg["voices"].items()):
        gpt_ok = os.path.exists(v["gpt"]) if os.path.isabs(v.get("gpt", "")) else \
            os.path.exists(os.path.join(ENGINE, v.get("gpt", "")))
        sov_ok = os.path.exists(v["sovits"]) if os.path.isabs(v.get("sovits", "")) else \
            os.path.exists(os.path.join(ENGINE, v.get("sovits", "")))
        ref = v["ref"] if os.path.isabs(v.get("ref", "")) else os.path.join(ENGINE, v.get("ref", ""))
        dur = ref_duration(ref)
        dur_s = ("%.1f с" % dur) if dur else ("НЕ НАЙДЕН" if not os.path.exists(ref) else "? с")
        flags = []
        if not gpt_ok:
            flags.append("нет GPT-весов")
        if not sov_ok:
            flags.append("нет SoVITS-весов")
        if dur and not (3.0 <= dur <= 10.0):
            flags.append("референс вне 3–10 с!")
        print("  %-12s %-14s референс: %-8s %s"
              % (name, v.get("display", ""), dur_s, ("  !! " + ", ".join(flags)) if flags else "ok"))


def cmd_add(args):
    cfg = load_voices()
    if args.name in cfg["voices"] and not args.force:
        raise SystemExit("Голос '%s' уже есть. --force — перезаписать." % args.name)
    for path, what in ((args.gpt, "GPT-веса"), (args.sovits, "SoVITS-веса"), (args.ref, "референс")):
        if not os.path.exists(path):
            raise SystemExit("Не найден файл %s: %s" % (what, path))
    dur = ref_duration(args.ref)
    if dur is not None and not (3.0 <= dur <= 10.0):
        raise SystemExit("Референс %.1f с — API требует 3–10 с. Вырежи другой кусок." % dur)
    cfg["voices"][args.name] = {
        "display": args.display or args.name,
        "gpt": os.path.relpath(args.gpt, ENGINE) if os.path.abspath(args.gpt).startswith(ENGINE) else args.gpt,
        "sovits": os.path.relpath(args.sovits, ENGINE) if os.path.abspath(args.sovits).startswith(ENGINE) else args.sovits,
        "ref": os.path.relpath(args.ref, ENGINE) if os.path.abspath(args.ref).startswith(ENGINE) else args.ref,
        "aux": args.aux or [],
        "prompt_text": args.prompt_text,
        "prompt_lang": args.prompt_lang,
    }
    if not cfg.get("default_voice"):
        cfg["default_voice"] = args.name
    save_voices(cfg)
    print("Голос '%s' добавлен в voices.json." % args.name)


def cmd_serve(args):
    ensure_voice(get_voice(args.voice), force=args.force)
    print("Сервер работает с голосом '%s'." % args.voice)


def cmd_test(args):
    v = get_voice(args.voice)
    ensure_voice(v)
    text = kanaize(args.text)
    print("Текст: %s\nКиана: %s" % (args.text, text))
    blob, ext = synth(v, text, seed=args.seed, speed=args.speed)
    out = os.path.join(CODE, "test_%s.%s" % (v["name"], ext))
    with open(out, "wb") as f:
        f.write(blob)
    print("Сохранено: %s (%.0f КБ) — проиграй файл." % (out, len(blob) / 1024))


def cmd_clone(args):
    to_deck = args.to_deck or args.voice
    clone_cards(args.query, to_deck, limit=args.limit,
                tag=args.tag or args.voice, force=args.force)


def _fields_from_args(args):
    """Собрать конфиг полей из CLI/GUI-аргументов (пустые = дефолт)."""
    return resolve_fields(
        sentence_src=getattr(args, "sentence_src", None),
        sentence_audio=getattr(args, "sentence_audio", None),
        word_src=getattr(args, "word_src", None),
        word_audio=getattr(args, "word_audio", None),
        furigana_src=getattr(args, "furigana_src", None),
        reading=getattr(args, "reading", None),
    )


def cmd_voice(args):
    fields = _fields_from_args(args)
    if args.deck:
        ids = ac("findNotes", query='deck:"%s"' % args.deck)
        if args.limit:
            ids = ids[:args.limit]
        if not ids:
            raise SystemExit("Колода '%s' пуста." % args.deck)
    elif args.ids:
        ids = [int(x) for x in args.ids]
    else:
        raise SystemExit("Укажи --deck или --ids.")
    voice_notes(ids, args.voice, mode=args.mode, force=args.force,
                seed=args.seed, speed=args.speed, fields=fields)


def cmd_make_deck(args):
    fields = _fields_from_args(args)
    to_deck = args.to_deck or get_voice(args.voice).get("display") or args.voice
    ids = clone_cards(args.query, to_deck, limit=args.limit, tag=args.tag or args.voice,
                      force=args.force, fields=fields)
    voice_notes(ids, args.voice, mode=args.mode, force=args.force,
                seed=args.seed, speed=args.speed, fields=fields)
    print("\n=== Проверка ===")
    check_deck(to_deck, fields=fields)


def cmd_qc_deck(args):
    """Собрать отбракованный синтез в отдельную колоду Anki.

    Зачем: детектор отклоняет файл и выбрасывает его — а чтобы судить,
    правильно ли он отклонил, нужно ПОСЛУШАТЬ. Здесь каждая отбракованная
    попытка становится карточкой: сверху текст, под ним причины и стратегия,
    внизу само аудио.

    Карточки помечены тегом av_qc_reject и снабжены полем «Вердикт», куда
    вы пишете своё решение («верно» / «ложное срабатывание») — это и есть
    разметка для подстройки порогов.
    """
    d = QC_REJECT_DIR
    idx = os.path.join(d, "index.jsonl")
    if not os.path.exists(idx):
        raise SystemExit("Отбракованного звука нет: %s\n"
                         "Сначала прогони озвучку — брак складывается туда "
                         "автоматически." % idx)
    recs = []
    with open(idx, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    recs.append(json.loads(line))
                except Exception:
                    pass
    if not recs:
        raise SystemExit("index.jsonl пуст.")

    deck = args.deck or "AnkiVoice_Брак"
    ac("createDeck", deck=deck)

    # Имя модели зависит от локали установки Anki: в русской сборке
    # «Basic» называется «Простая». Ищем не по имени, а по строению —
    # модель ровно с двумя полями Front/Back. Kiku (22 поля) брать нельзя:
    # карточка брака сломается на обязательных полях.
    models = ac("modelNames") or []
    model = None
    for m in models:
        try:
            flds_m = ac("modelFieldNames", modelName=m) or []
        except Exception:
            continue
        if [x.lower() for x in flds_m] == ["front", "back"]:
            model = m
            break
    if not model:
        raise SystemExit("Нет модели с полями Front/Back (обычно «Простая»). "
                         "Доступны: %s" % ", ".join(models[:12]))
    flds = ac("modelFieldNames", modelName=model) or ["Front", "Back"]
    front, back = flds[0], flds[-1]
    print("модель: %s (%s)" % (model, ", ".join(flds)))
    verdict_field = next((x for x in flds if x.lower() in
                          ("вердикт", "verdict", "comment", "комментарий")), None)

    made = skipped = 0
    for r in recs:
        fp = os.path.join(d, r["file"])
        if not os.path.exists(fp):
            skipped += 1
            continue
        with open(fp, "rb") as f:
            blob = f.read()
        stored = ac("storeMediaFile", filename=r["file"], overwrite=True,
                    data=base64.b64encode(blob).decode("ascii"))
        fname = stored or r["file"]
        head = "【%d】%s" % (r["attempt"], r["text"] or "(пусто)")
        body = ("Причина: %s\nСтратегия: %s\nФайл: %s (%.1f КБ)"
                % ("; ".join(r["reasons"]) or "не указана",
                   r.get("strategy", "?"), fname, len(blob) / 1024))
        fields = {front: head,
                  back: "%s\n\n[sound:%s]" % (body, fname)}
        if verdict_field:
            fields[verdict_field] = ""
        ac("addNote", note={
            "deckName": deck, "modelName": model, "fields": fields,
            "options": {"allowDuplicate": False, "duplicateScope": "deck"},
            "tags": ["av_qc_reject"],
        })
        made += 1
    print("Колода '%s': добавлено %d карточек, пропущено (нет файла): %d"
          % (deck, made, skipped))
    print("Послушай каждую и впиши в поле «Вердикт»: «верно» либо "
          "\"ложное срабатывание\" — по этим записям подстроятся пороги.")
    return made


def cmd_check(args):
    return check_deck(args.deck, fields=_fields_from_args(args),
                      verify_files=not getattr(args, "fast", False))


def cmd_selftest(args):
    """Проверка всей цепочки без записи в Anki и без синтеза."""
    bad = 0

    def ok(msg):
        print("  OK   %s" % msg)

    def fail(msg):
        nonlocal bad
        bad += 1
        print("  FAIL %s" % msg)

    print("== Самопроверка пайплайна ==")
    print("  --   код (инструмент): %s" % CODE)
    if ENGINE:
        ok("папка GPT-SoVITS найдена: %s" % ENGINE)
    else:
        fail("папка GPT-SoVITS не найдена (env GPT_SOVITS_ROOT / gptsovits_path.txt / конфиг AnkiVoice.exe)")
    if PYTHON and os.path.exists(PYTHON):
        ok("runtime\\python.exe на месте")
    else:
        fail("нет runtime\\python.exe: %s" % PYTHON)

    cfg = load_voices()
    voices = cfg.get("voices", {})
    ok("voices.json: голосов %d" % len(voices)) if voices else fail("voices.json пуст")
    for name, v in sorted(voices.items()):
        for key in ("gpt", "sovits", "ref"):
            p = v.get(key, "")
            if key == "ref" and not p:
                # голос найден сканером, референс ещё не подобран — не ошибка
                print("  --   %s: референс не выбран (выбери вкладкой «Голос»)" % name)
                continue
            p = p if os.path.isabs(p) else os.path.join(ENGINE or CODE, p)
            if os.path.exists(p):
                d = ref_duration(p) if key == "ref" else None
                if key == "ref" and d is not None and not (3.0 <= d <= 10.0):
                    fail("%s: %s = %.1f с (API требует 3–10 с)" % (name, key, d))
                else:
                    ok("%s: %s %s" % (name, key, ("%.1f с" % d) if d else ""))
            else:
                fail("%s: %s не найден: %s" % (name, key, p))
    try:
        import pyopenjtalk
        r = pyopenjtalk.g2p("合釘を打ち込む", kana=True)
        ok("pyopenjtalk (запасной ход): %s" % r)
    except Exception as e:
        fail("pyopenjtalk: %s" % e)
    client = sudachi_client()
    if client is not None:
        ok("Sudachi (встроенный, %s, словарь %s): %s"
           % (client.version, client.dictver, kanaize(u"高輪ゲートウェイ駅")))
    else:
        print("  --   Встроенный Sudachi недоступен — иероглифы читает "
              "pyopenjtalk;")
        print("       нужны pyruntime.zip и sudachidict.zip рядом со скриптом.")

    # текст -> хирагана: проверяем сложные случаи (полукатакана, полноразмерная
    # латиница, ヴ-серия, словарные замены, длинная глагольная форма)
    print("  --   текст -> хирагана (сложные случаи):")
    for src, want in ((u"ｶﾞｷｮｳ", u"がきょう"),
                      (u"ＩＥＣ規格", u"あいいーしーきかく"),
                      (u"食べさせられたくなかった", u"たべさせられたくなかった"),
                      (u"キョウト", u"きょうと")):
        got = kanaize(src)
        if got == want:
            ok("%s -> %s" % (src, got))
        else:
            fail("%s -> %s (ожидалось %s)" % (src, got, want))
    # 合折釘 — доменный термин: движку без поля не знать «あいおれくぎ»,
    # он читает по-своему. Проверяем обе ветки раздельно: авто-чтение
    # (просто обязано выдать хирагану) и чтение из фуриганы (строго эталон).
    src = u"合折釘"
    got = kanaize(src)
    if got and not KANJI_RE.search(got):
        ok("%s (авто, без поля): %s — движок читает сам" % (src, got))
    else:
        fail("%s (авто): %r — остались иероглифы" % (src, got))
    got = kanaize_card(src, expression=src, furigana=u"合折釘[あいおれくぎ]")
    if got == u"あいおれくぎ":
        ok("%s (из фуриганы): %s" % (src, got))
    else:
        fail("%s (из фуриганы): %s (ожидалось %s)" % (src, got, u"あいおれくぎ"))
    try:
        ac("version")
        ok("AnkiConnect отвечает")
    except SystemExit:
        fail("AnkiConnect недоступен — открой Anki")
    proxied = [k for k in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
                           "http_proxy", "https_proxy", "all_proxy")
               if os.environ.get(k)]
    if proxied:
        print("  --   в окружении задан прокси (%s) — локальные запросы идут "
              "мимо него, не мешает" % ", ".join(proxied))

    # подстановка чтения из фуриганного поля в предложение (см. inject_reading)
    print("  --   подстановка чтения из поля (фуригана слова):")
    for expr, efur, sent, want in (
            (u"相欠き", u"相欠[あいが]き",
             u"大工は交差部を相欠きにして高さを揃えた。",
             u"大工は交差部をあいがきにして高さを揃えた。"),
            (u"相欠き継ぎ", u"相欠[あいが]き継[つ]ぎ",
             u"大工は材の延長に相欠き継ぎを用いて固めた。",
             u"大工は材の延長にあいがきつぎを用いて固めた。"),
            (u"I形グルーブ", u"I形[アイがた]グルーブ",
             u"薄板の突合せ継手はI形グルーブで溶接した。",
             u"薄板の突合せ継手はあいがたぐるーぶで溶接した。"),
            (u"IEC規格", u"IEC規格[アイイーシーきかく]",
             u"特注の配電盤仕様にIEC規格を引用した。",
             u"特注の配電盤仕様にあいいーしーきかくを引用した。"),
            # слово в предложении НЕТ — предложение не трогаем
            (u"合折釘", u"合折釘[あいおれくぎ]",
             u"別の文には слова нет。", u"別の文には слова нет。")):
        note = {"fields": {
            "Expression": {"value": expr},
            "ExpressionFurigana": {"value": efur},
            "ExpressionReading": {"value": ""},
            "Sentence": {"value": sent},
            "SentenceFurigana": {"value": ""}}}
        got = inject_reading(sent, note, reading="ExpressionFurigana")
        if got == want:
            ok("подстановка: %s" % expr)
        else:
            fail("подстановка: %s -> %s (ожидалось %s)" % (expr, got, want))
        # чтение слова (для озвучки самого Expression) тоже должно быть верным
        w = word_text(note, "Expression", reading="ExpressionFurigana")
        if w and not KANJI_RE.search(w):
            ok("чтение слова %s: %s" % (expr, w))
        else:
            fail("чтение слова %s: %s (в чтении остались иероглифы)"
                 % (expr, w))
    # режимы источника чтения (параметр reading): только off и конкретное поле
    print("  --   режимы источника чтения:")
    if DEFAULT_FIELDS.get("reading") == "off":
        ok("по умолчанию: подстановки нет (off) — движок читает сам")
    else:
        fail("по умолчанию: reading=%r (ожидалось 'off')"
             % DEFAULT_FIELDS.get("reading"))
    note_r = {"fields": {
        "Expression": {"value": u"相欠き"},
        "ExpressionFurigana": {"value": u"相欠[あいが]き"},
        "ExpressionReading": {"value": ""},
        u"Кана": {"value": u"あいが"},
        u"КанаИероглифы": {"value": u"相欠き"},
        u"Пусто": {"value": ""},
        "Sentence": {"value": u"大工は相欠きにして高さを揃えた。"},
        "SentenceFurigana": {"value": ""}}}
    sent_r = note_r["fields"]["Sentence"]["value"]
    got = inject_reading(sent_r, note_r, reading="off")
    if got == sent_r:
        ok("reading=off: подстановки нет")
    else:
        fail("reading=off: ожидалась чистая строка, получено %r" % got)
    w = word_text(note_r, "Expression", reading="off")
    if w == u"相欠き":
        ok("reading=off: слово без фуриганы (движок читает само)")
    else:
        fail("reading=off: слово %r (ожидалось написание без разметки)" % w)
    got = inject_reading(sent_r, note_r, reading=u"Кана")
    if got == u"大工はあいがにして高さを揃えた。":
        ok("reading=поле: чтение подставилось из поля «Кана»")
    else:
        fail("reading=поле: %r" % got)
    w = word_text(note_r, "Expression", reading=u"Кана")
    if w == u"あいが":
        ok("reading=поле: слово озвучивается чтением из поля")
    else:
        fail("reading=поле: слово %r" % w)
    # поле может содержать фуриганную разметку — указывай готовое
    # ExpressionFurigana, карточку переписывать не нужно
    got = inject_reading(sent_r, note_r, reading="ExpressionFurigana")
    if got == u"大工はあいがきにして高さを揃えた。":
        ok("reading=фуриганное поле: разметка разобрана, чтение подставлено")
    else:
        fail("reading=фуриганное поле: %r" % got)
    w = word_text(note_r, "Expression", reading="ExpressionFurigana")
    if w == u"あいがき":
        ok("reading=фуриганное поле: слово озвучивается полным чтением")
    else:
        fail("reading=фуриганное поле: слово %r" % w)
    # пустое поле — подстановки нет, авто НЕ подхватывается
    got = inject_reading(sent_r, note_r, reading=u"Пусто")
    if got == sent_r:
        ok("reading=пустое поле: подстановки нет (авто не подхватывается)")
    else:
        fail("reading=пустое поле: %r" % got)
    w = word_text(note_r, "Expression", reading=u"Пусто")
    if w == u"相欠き":
        ok("reading=пустое поле: слово — написание без разметки (как off)")
    else:
        fail("reading=пустое поле: слово %r" % w)
    got = inject_reading(sent_r, note_r, reading=u"НетТакогоПоля")
    if got == sent_r:
        ok("reading=нет такого поля: подстановки нет")
    else:
        fail("reading=нет такого поля: %r" % got)
    # в «чтении» иероглифы — отказываемся: это не чтение
    got = inject_reading(sent_r, note_r, reading=u"КанаИероглифы")
    if got == sent_r:
        ok("reading=иероглифы в поле: подстановки нет (безопасность)")
    else:
        fail("reading=иероглифы в поле: %r" % got)

    ok("GPT-SoVITS запущен") if tts_ready() else \
        print("  --   GPT-SoVITS не запущен (поднимется сам при озвучке)")
    print("\n%s" % ("Всё в порядке." if not bad else "Проблем: %d — см. FAIL выше." % bad))
    sys.exit(1 if bad else 0)


def menu():
    cfg = load_voices()
    while True:
        print("\n======== Пайплайн озвучки Anki (GPT-SoVITS) ========")
        print("  1. Список голосов")
        print("  2. Добавить голос")
        print("  3. Создать колоду и озвучить её")
        print("  4. Озвучить существующую колоду")
        print("  5. Проверить колоду")
        print("  6. Тест синтеза (файл test_<голос>.ogg)")
        print("  7. Поднять сервер с голосом")
        print("  0. Выход")
        c = input("Выбор: ").strip()
        try:
            if c == "1":
                cmd_list()
            elif c == "2":
                cmd_add(argparse.Namespace(
                    name=ask("имя голоса латиницей (напр. sakura)"),
                    display=ask("как показывать (напр. Сакура)", ""),
                    gpt=ask("путь к GPT .ckpt"),
                    sovits=ask("путь к SoVITS .pth"),
                    ref=ask("путь к референсу 3–10 с"),
                    aux=[], prompt_text=ask("текст, говорится в референсе"),
                    prompt_lang="ja", force=True))
            elif c == "3":
                voice = ask("голос", cfg.get("default_voice") or "")
                cmd_make_deck(argparse.Namespace(
                    voice=voice, to_deck=None,
                    query=ask("откуда клонировать (запрос Anki)", "deck:Архитектура"),
                    limit=int(ask("сколько карточек", "20") or 20),
                    mode=ask("mode (both/sentence/expression)", "both"),
                    tag=None, force=False, seed=42, speed=1.0))
            elif c == "4":
                voice = ask("голос", cfg.get("default_voice") or "")
                cmd_voice(argparse.Namespace(
                    voice=voice, deck=ask("имя колоды"),
                    ids=None, limit=None,
                    mode=ask("mode (both/sentence/expression)", "both"),
                    force=False, seed=42, speed=1.0))
            elif c == "5":
                cmd_check(argparse.Namespace(deck=ask("имя колоды")))
            elif c == "6":
                cmd_test(argparse.Namespace(
                    voice=ask("голос", cfg.get("default_voice") or ""),
                    text=ask("текст для проверки", "こんにちは"),
                    seed=42, speed=1.0))
            elif c == "7":
                cmd_serve(argparse.Namespace(voice=ask("голос"), force=False))
            elif c == "0":
                return
        except SystemExit as e:
            if e.code not in (0, None):
                print("—", e)
        except Exception as e:
            print("Ошибка:", repr(e))


def main():
    ap = argparse.ArgumentParser(description="Пайплайн озвучки колод Anki голосами GPT-SoVITS")
    sub = ap.add_subparsers(dest="cmd")

    sub.add_parser("list", help="показать голоса")

    p = sub.add_parser("add", help="добавить голос в voices.json")
    p.add_argument("--name", required=True)
    p.add_argument("--display", default=None)
    p.add_argument("--gpt", required=True)
    p.add_argument("--sovits", required=True)
    p.add_argument("--ref", required=True)
    p.add_argument("--aux", nargs="*", default=[])
    p.add_argument("--prompt-text", required=True)
    p.add_argument("--prompt-lang", default="ja")
    p.add_argument("--force", action="store_true")

    p = sub.add_parser("serve", help="поднять сервер/переключить голос")
    p.add_argument("--voice")
    p.add_argument("--force", action="store_true")

    p = sub.add_parser("test", help="синтез одного текста в файл")
    p.add_argument("--voice")
    p.add_argument("--text", required=True)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--speed", type=float, default=1.0)

    p = sub.add_parser("clone", help="клонировать карточки в новую колоду")
    p.add_argument("--voice", required=True)
    p.add_argument("--query", default="deck:Архитектура")
    p.add_argument("--to-deck", default=None)
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--tag", default=None)
    p.add_argument("--force", action="store_true")

    p = sub.add_parser("voice", help="озвучить колоду/карточки")
    p.add_argument("--voice")
    p.add_argument("--deck", default=None)
    p.add_argument("--ids", nargs="*", default=None)
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--mode", choices=["sentence", "expression", "both"], default="both")
    p.add_argument("--sentence-src", default=None, help="поле с текстом предложения")
    p.add_argument("--sentence-audio", default=None, help="поле для звука предложения")
    p.add_argument("--word-src", default=None, help="поле со словом")
    p.add_argument("--word-audio", default=None, help="поле для звука слова")
    p.add_argument("--furigana-src", default=None,
                   help="поле с фуриганой основного слова (по умолчанию "
                        "ExpressionFurigana); основное слово читается строго "
                        "по нему, всё остальное — автоматически")
    p.add_argument("--reading", default="off",
                   help="источник чтения: off — не подставлять (движок читает "
                        "сам), либо имя поля с готовым чтением слова "
                        "(простое чтение или фуриганная разметка поля)")
    p.add_argument("--force", action="store_true")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--speed", type=float, default=1.0)

    p = sub.add_parser("make-deck", help="клонировать + озвучить + проверить")
    p.add_argument("--voice", required=True)
    p.add_argument("--query", default="deck:Архитектура")
    p.add_argument("--to-deck", default=None)
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--mode", choices=["sentence", "expression", "both"], default="both")
    p.add_argument("--sentence-src", default=None, help="поле с текстом предложения")
    p.add_argument("--sentence-audio", default=None, help="поле для звука предложения")
    p.add_argument("--word-src", default=None, help="поле со словом")
    p.add_argument("--word-audio", default=None, help="поле для звука слова")
    p.add_argument("--furigana-src", default=None,
                   help="поле с фуриганой основного слова (по умолчанию "
                        "ExpressionFurigana)")
    p.add_argument("--reading", default="off",
                   help="источник чтения: off — не подставлять (движок читает "
                        "сам), либо имя поля с готовым чтением слова "
                        "(простое чтение или фуриганная разметка поля)")
    p.add_argument("--tag", default=None)
    p.add_argument("--force", action="store_true")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--speed", type=float, default=1.0)

    p = sub.add_parser("check", help="проверить колоду")
    p.add_argument("--deck", required=True)
    p.add_argument("--sentence-audio", default=None, help="поле для звука предложения")
    p.add_argument("--word-audio", default=None, help="поле для звука слова")
    p.add_argument("--fast", action="store_true",
                   help="не качать аудиофайлы из Anki — только проверить поля")

    p = sub.add_parser("scan", help="найти голоса в папке движка и добавить в voices.json")
    p.add_argument("--apply", action="store_true",
                   help="записать новые голоса в voices.json (без флага — только показать)")
    p.add_argument("--json", action="store_true", help="машинночитаемый вывод (для GUI)")

    sub.add_parser("selftest", help="проверить файлы/референсы/Anki/сервер")

    p = sub.add_parser("qc-deck", help="собрать отбракованный синтез в колоду Anki "
                                       "(чтобы послушать и оценить детектор)")
    p.add_argument("--deck", default="AnkiVoice_Брак",
                   help="имя колоды (по умолчанию AnkiVoice_Брак)")

    args = ap.parse_args()
    if not args.cmd:
        menu()
        return
    # команды, которым нужен один работающий экземпляр (гонка за веса/сервер)
    if args.cmd in ("serve", "test", "clone", "voice", "make-deck"):
        acquire_lock()
    result = {"list": cmd_list, "add": cmd_add, "serve": cmd_serve, "test": cmd_test,
              "clone": cmd_clone, "voice": cmd_voice, "make-deck": cmd_make_deck,
              "check": cmd_check, "scan": cmd_scan, "qc-deck": cmd_qc_deck,
              "selftest": cmd_selftest}[args.cmd](args)
    if args.cmd == "check" and result is False:
        sys.exit(1)


if __name__ == "__main__":
    main()
