# -*- coding: utf-8 -*-
"""voice_pipeline.py — единый пайплайн озвучки колод Anki голосами GPT-SoVITS.

Автономный пайплайн: скрипт лежит в любой папке (например, в репозитории на
GitHub), а движок GPT-SoVITS может стоять где угодно. Папка движка ищется
в таком приоритете (первый найденный берётся):
  1. переменная окружения GPT_SOVITS_ROOT=C:\\...\\GPT-SoVITS
  2. файл gptsovits_path.txt рядом с этим скриптом (одна строка — путь)
  3. %APPDATA%\\AnkiTTS\\config.json  ->  "gptsovits_path"  (его пишет AnkiTTS.exe)
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
  * переводит текст карточек в хирагану (pyopenjtalk), латиницу IEC/ISO/I形 -> катакана,
    редкие слова — через kana_overrides.txt;
  * синтезирует слово и предложение, кладёт ogg в медиа Anki, пишет [sound:...] в поля;
  * проверяет результат (поля заполнены, файлы на месте).

Голоса хранятся в voices.json (рядом со скриптом). Референс обязан быть 3–10 секунд.
Относительные пути в voices.json (к весам и референсам) считаются от папки ДВИЖКА.
"""

import argparse
import base64
import hashlib
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

try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# ------------------------------------------------------------------ константы
# CODE  — папка самого инструмента (этот скрипт, voices.json, kana_overrides.txt).
# ENGINE — папка установленного GPT-SoVITS (runtime\python.exe, api_v2.py, веса).
CODE = os.path.dirname(os.path.abspath(__file__))
VOICES_FILE = os.path.join(CODE, "voices.json")
OVERRIDES_FILE = os.path.join(CODE, "kana_overrides.txt")
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
# на вкладке «Anki» / через CLI — разные колоды называют поля по-разному.
DEFAULT_FIELDS = {
    "sentence_src": "Sentence",        # поле с текстом предложения
    "sentence_audio": "SentenceAudio",  # поле, куда писать звук предложения
    "word_src": "Expression",          # поле со словом (понимает фуригану)
    "word_audio": "ExpressionAudio",   # поле, куда писать звук слова
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
    cfgp = os.path.join(os.environ.get("APPDATA") or "", "AnkiTTS", "config.json")
    try:
        with open(cfgp, encoding="utf-8") as f:
            return (json.load(f) or {}).get("gptsovits_path") or None
    except Exception:
        return None


def _norm(p):
    return os.path.abspath(os.path.expandvars(os.path.expanduser(p)))


def resolve_engine():
    """Папка движка: env -> gptsovits_path.txt -> конфиг AnkiTTS.exe -> своя папка."""
    for cand in (os.environ.get("GPT_SOVITS_ROOT"),
                 _read_engine_local_file(),
                 _read_engine_gui_config(),
                 CODE):                      # обратная совместимость: лежит внутри GPT-SoVITS
        if cand:
            cand = _norm(cand)
            if _is_engine(cand):
                return cand
    return None


def require_engine():
    if not ENGINE:
        raise SystemExit(
            "Не найдена папка GPT-SoVITS. Укажи её одним из способов:\n"
            "  * переменная окружения  GPT_SOVITS_ROOT=C:\\...\\GPT-SoVITS\n"
            "  * файл gptsovits_path.txt рядом с voice_pipeline.py (одна строка — путь)\n"
            "  * запусти AnkiTTS.exe и выбери папку в окне (сохранится в конфиг)\n"
            "В папке должны быть runtime\\python.exe и файл api_v2.py.")
    return ENGINE


# сразу резолвим (не бросает исключений: при отсутствии ENGINE останется None,
# а require_engine() даст понятную ошибку при попытке использовать движок)
ENGINE = resolve_engine()
if ENGINE:
    PYTHON = os.path.join(ENGINE, "runtime", "python.exe")
    ACTIVE_VOICE_FILE = os.path.join(ENGINE, "logs", "active_voice.txt")
    SERVER_LOG = os.path.join(ENGINE, "logs", "api_v2_pipeline.log")


# ------------------------------------------------------------ AnkiConnect
def ac(action, **params):
    payload = {"action": action, "version": 6, "params": params}
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        ANKI_CONNECT, data=data,
        headers={"Content-Type": "application/json", "Origin": "http://localhost"},
    )
    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
            out = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as e:
        raise SystemExit("AnkiConnect недоступен (%s). Открой Anki и повтори." % e)
    if out.get("error"):
        raise SystemExit("AnkiConnect: %s" % out["error"])
    return out["result"]


TAG_RE = re.compile(r"<[^>]+>")


def plain(v):
    return TAG_RE.sub("", v or "").strip()


# ----------------------------------------------------------- работа с голосами
def load_voices():
    if not os.path.exists(VOICES_FILE):
        return {"start_config": DEFAULT_START_CONFIG, "default_voice": None, "voices": {}}
    with open(VOICES_FILE, encoding="utf-8") as f:
        cfg = json.load(f)
    cfg.setdefault("voices", {})
    cfg.setdefault("start_config", DEFAULT_START_CONFIG)
    return cfg


def save_voices(cfg):
    with open(VOICES_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


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


def cmd_scan(args):
    engine = require_engine()
    found = scan_engine_voices(engine)
    cfg = load_voices()
    existing = cfg.setdefault("voices", {})
    known_gpt = {str(v.get("gpt", "")).lower().replace("\\", "/")
                 for v in existing.values()}
    added = []
    for item in found:
        if item["gpt"].lower() in known_gpt:
            continue                      # голос уже зарегистрирован (иначе ключей)
        existing[item["name"]] = {
            "display": item["display"],
            "gpt": item["gpt"],
            "sovits": item["sovits"],
            "ref": item["ref"],
            "aux": [],
            "prompt_text": "",
            "prompt_lang": "ja",
        }
        known_gpt.add(item["gpt"].lower())
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


def start_server(start_config, wait=600):
    require_engine()
    if tts_ready():
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
        urllib.request.urlopen(TTS_URL + "/control?command=restart", timeout=10).read()
    except Exception:
        pass                       # сокет обрывается — это ожидаемо
    wait_port(False, 60)
    if tts_ready():                # не упал — убиваем по порту
        try:
            out = subprocess.run(["netstat", "-ano"], capture_output=True,
                                 text=True, timeout=20)
            for line in out.stdout.splitlines():
                if (":%d" % TTS_PORT) in line and "LISTENING" in line:
                    pid = line.split()[-1]
                    subprocess.run(["taskkill", "/PID", pid, "/F"],
                                   capture_output=True, timeout=20)
                    break
        except Exception as e:
            print("не удалось остановить старый процесс:", e)
        wait_port(False, 60)
    time.sleep(2)
    start_server(start_config, wait)


def _get(path, params):
    url = TTS_URL + path + "?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=300) as r:
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
KANJI_RE = re.compile(r"[\u3005\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
LATIN = {"A": "エー", "B": "ビー", "C": "シー", "D": "ディー", "E": "エー",
         "F": "エフ", "G": "ジー", "H": "エイチ", "I": "アイ", "J": "ジェー",
         "K": "ケー", "L": "エル", "M": "エム", "N": "エヌ", "O": "オー",
         "P": "ピー", "Q": "キュー", "R": "アール", "S": "エス", "T": "ティー",
         "U": "ユー", "V": "ブイ", "W": "ダブリュー", "X": "イックス",
         "Y": "ワイ", "Z": "ゼット"}

_overrides = None
_g2p_warned = False


def load_overrides():
    global _overrides
    if _overrides is not None:
        return _overrides
    _overrides = {}
    if os.path.exists(OVERRIDES_FILE):
        with open(OVERRIDES_FILE, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, val = line.split("=", 1)
                if k.strip():
                    _overrides[k.strip()] = val.strip()
    return _overrides


def apply_overrides(text):
    ov = load_overrides()
    for k in sorted(ov, key=len, reverse=True):
        if k in text:
            text = text.replace(k, ov[k])
    return text


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
# ヷヸヹヺ - уточнённые «ва/ви/ву/ве»; ヽヾ - повторяющиеся знаки.
# Иначе они остаются катаканой и попадают в MeCab «как есть».
_KATA_EXTRA = {"ヷ": "わ゛", "ヸ": "い゛", "ヹ": "う゛", "ヺ": "う゛",
               "ヽ": "け", "ヾ": "げ"}


def kata2hira(s, keep_kata=()):
    """Катакана -> хирагана. Слова из keep_kata остаются катаканой."""
    out = []
    for c in s:
        if "ァ" <= c <= "ヶ":
            out.append(chr(ord(c) - 0x60))
        else:
            out.append(_KATA_EXTRA.get(c, c))
    t = "".join(out)
    for keep in keep_kata:                      # вернуть защищённые слова
        t = t.replace(kata2hira(keep), keep)
    return t


# Границы сегментов: иероглифы (с хираганой) / катакана / всё прочее.
# Разрезаем текст так, чтобы g2p достались ТОЛЬКО куски с иероглифами.
_SEG_RE = re.compile(
    r"([぀-ヿ一-鿿々〆ヶ]+)"      # иероглифы и хирагана
    r"|([ァ-ヿｦ-ﾟ]+)"                            # катакана (вкл. полукатакану)
    r"|([^぀-ヿ一-鿿]+)"                        # всё прочее (латиница, цифры, знаки)
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
# IEC -> アイエーシー -> アイエースィー.
_KEEP_KATA = ("コンニチハ", "コンバンハ")


def g2p_kana(text):
    global _g2p_warned
    try:
        import pyopenjtalk
        return pyopenjtalk.g2p(text, kana=True)
    except Exception as e:
        if not _g2p_warned:
            print("!! pyopenjtalk недоступен (%s) — иероглифы останутся как есть" % e)
            _g2p_warned = True
        return text


def kanaize(text):
    """Текст -> хирагана: NFKC -> словарь -> латиница катаканой -> сегменты
    -> g2p только иероглифы -> хирагана.

    Главный принцип: MeCab надёжно читает иероглифы и катакану, но портит
    уже готовую хирагану (применяет правила частиц: こんにちは -> コнничива).
    Поэтому режем текст на сегменты и гоняем через g2p ТОЛЬКО куски с
    иероглифами.

    Шаги подробно (важно для сложных слов):
      1. NFKC-нормализация: полноразмерная латиница/цифры (ＡＢＣ１２３ -> ABC123),
         полукатакана с дакутеном (ｶﾞ -> ガ) и съёмные знаки (か+゙ -> ガ)
         сводятся к обычным формам — без этого MeCab видит «неразбиваемые»
         мусорные символы и ломает разбор всего предложения.
      2. kana_overrides.txt: точечные замены слов, которые MeCab читает
         неверно (длинные ключи раньше коротких). Замены пишем катаканой,
         чтобы g2p разобрал их как обычное слово, а не как частицу.
      3. Латиница -> катакана по буквам (IEC -> アイエーシー).
      4. Текст режется на сегменты (иероглифы / катакана / прочее) и
         гоняется через g2p ТОЛЬКО там, где есть иероглифы. Готовая
         хирагана, цифры и знаки идут мимо g2p — их MeCab не портит.
      5. Всё приводится к хирагане, кроме «защищённых» слов _KEEP_KATA
         (их хирагану MeCab читает как частицу, поэтому оставляем катаканой).
    """
    t = normalize_text(text)
    t = apply_overrides(t)
    t = latin2kana(t)
    t = kata2hira(t, keep_kata=_KEEP_KATA)

    if KANJI_RE.search(t):
        t = g2p_kana(t)

    return kata2hira(t, keep_kata=_KEEP_KATA).strip()


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


def expression_reading(note):
    """Чтение слова: ExpressionReading -> фуригана (все скобки) -> сам Expression.

    Фуригана разбирается через furiga_pair (см. _base_reading о двух видах
    разметки в колоде). Если чтения нет — берём сам Expression.
    """
    f = note["fields"]

    def fld(name):
        return plain(f.get(name, {}).get("value", ""))

    r = fld("ExpressionReading")
    if r:
        return r
    _, reading = furiga_pair(fld("ExpressionFurigana"))
    if reading and reading.strip():
        return reading.strip()
    return fld("Expression")


def expression_inject_pair(note):
    """(написание_слова, полное_чтение) — для подстановки в предложение.

    Написание — как слово стоит в предложении («相欠き継ぎ»), чтение —
    собранное целиком («あいがきつぎ»). Если разметки фуриганы нет —
    используется ExpressionReading. (None, None) — подстановка невозможна.
    """
    f = note["fields"]

    def fld(name):
        return plain(f.get(name, {}).get("value", ""))

    surface = re.sub(r"\[[^\[\]]*\]", "", fld("Expression")).strip()
    if not surface or not KANJI_RE.search(surface):
        return None, None                    # иероглифов нет — нечего подставлять
    reading = ""
    efur = fld("ExpressionFurigana")
    if "[" in efur:
        fur_surf, fur_read = furiga_pair(efur)
        if fur_surf is None or fur_surf.strip() != surface:
            return None, None                # разметка не совпала со словом — риск
        reading = fur_read
    else:
        reading = fld("ExpressionReading")
    reading = reading.strip()
    if not reading or reading == surface:
        return None, None
    if KANJI_RE.search(reading):
        return None, None                    # иероглифы в «чтении» — это не чтение
    return surface, reading


def inject_reading(sentence, note):
    """Вставить проверенное чтение в предложение вместо иероглифов.

    Идея: карточка уже содержит ПРАВИЛЬНОЕ чтение сложного слова, а API
    GPT-SoVITS принимает только текст (канала «готовое чтение» у него нет).
    Значит, подставляем чтение прямо в текст: MeCab увидит хирагану и не
    сможет ошибиться в редком термине (合折釘, 相欠き継ぎ и т.п.).

    Два источника чтения:
      1. SentenceFurigana (чтение целого предложения) — если заполнено и
         совпадает с предложением, чинит ВСЕ слова разом;
      2. Expression/ExpressionFurigana — подстановка одного слова.
    """
    f = note["fields"]

    def fld(name):
        return plain(f.get(name, {}).get("value", ""))

    # 1) чтение целого предложения — если оно есть
    sfur = fld("SentenceFurigana")
    if "[" in sfur:
        surf, read = furiga_pair(sfur)
        if surf and read and surf.strip() == fld("Sentence").strip():
            r = read.strip()
            if r and not KANJI_RE.search(r):
                return r
        # разметка не совпала с предложением — идём дальше, к слову

    # 2) подстановка чтения слова Expression
    kanji, reading = expression_inject_pair(note)
    if not kanji or not reading:
        return sentence
    if kanji not in sentence:
        return sentence
    return sentence.replace(kanji, kata2hira(reading))


# --------------------------------------------------------------- синтез
def _tts_start_config():
    cfg = load_voices()
    return os.path.join(ENGINE, cfg.get("start_config") or DEFAULT_START_CONFIG)


def synth(v, text, seed=42, speed=1.0, _oom_retry=True):
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

    def post(media_type):
        payload["media_type"] = media_type
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(TTS_URL + "/tts", data=data,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=600) as resp:
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
    if blob is None:
        blob, err = post("wav")             # ogg может не поддерживаться
    if blob is None:
        raise SystemExit("сервер отказал: %s" % (err or "нет ответа")[:300])
    if len(blob) < 1024:
        # сервер ответил почти пустым телом (обрыв/уступка памяти) —
        # такое нельзя сохранять как «озвучено»
        raise SystemExit("сервер вернул пустой звук (%d байт) — попробуй ещё раз"
                         % len(blob))
    return blob, "ogg" if payload["media_type"] == "ogg" else "wav"


def media_name(nid, field, text, ext, voice):
    h = hashlib.sha1(("v1|%d|%s|%s|%s" % (nid, field, text, voice))
                     .encode("utf-8")).hexdigest()[:10]
    return "tts_%s_%d_%s_%s.%s" % (voice, nid, field.lower(), h, ext)


# ----------------------------------------------------- операции с колодами
def word_text(note, word_src):
    """Текст слова из поля word_src. Для 'Expression' — полный разбор фуриганы,
    для произвольного поля — просто текст."""
    if word_src == "Expression":
        return expression_reading(note)
    return plain(note["fields"].get(word_src, {}).get("value", ""))


def build_jobs(notes, mode, force, fields=None):
    fields = fields or DEFAULT_FIELDS
    jobs = []
    for n in notes:
        f = n["fields"]

        def tgt(name):
            return plain(f.get(name, {}).get("value", ""))

        if mode in ("sentence", "both"):
            text = tgt(fields["sentence_src"])
            if text and (force or not tgt(fields["sentence_audio"])):
                # вставляем чтение сложного слова в предложение (если оно там
                # есть и карточка даёт правильное чтение) — защита от ошибок
                # MeCab на редких терминах
                text = inject_reading(text, n)
                jobs.append((n["noteId"], fields["sentence_audio"], kanaize(text)))
        if mode in ("expression", "both"):
            text = word_text(n, fields["word_src"])
            if text and (force or not tgt(fields["word_audio"])):
                jobs.append((n["noteId"], fields["word_audio"], kanaize(text)))
    return jobs


def voice_notes(ids, voice_name, mode="both", force=False, seed=42, speed=1.0,
                fields=None):
    v = get_voice(voice_name)
    notes = ac("notesInfo", notes=ids)
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
    for n in ac("notesInfo", notes=ids):
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


def check_deck(deck, fields=None):
    cfg = fields or DEFAULT_FIELDS
    afs = audio_fields(cfg)
    ids = ac("findNotes", query='deck:"%s"' % deck)
    if not ids:
        print("Колода '%s' не найдена или пуста (опечатка в имени?)." % deck)
        return False
    ok, problems = 0, []
    for n in ac("notesInfo", notes=ids):
        expr = plain(n["fields"].get(cfg["word_src"], {}).get("value", ""))
        bad = []
        for fld in afs:
            tag = plain(n["fields"].get(fld, {}).get("value", ""))
            m = re.search(r"\[sound:([^\]]+)\]", tag)
            if not m:
                bad.append("%s пусто" % fld)
            elif not ac("retrieveMediaFile", filename=m.group(1)):
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


def cmd_check(args):
    return check_deck(args.deck, fields=_fields_from_args(args))


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
        fail("папка GPT-SoVITS не найдена (env GPT_SOVITS_ROOT / gptsovits_path.txt / конфиг AnkiTTS.exe)")
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
    ov = load_overrides()
    ok("kana_overrides.txt: %d замен" % len(ov)) if ov else \
        print("  --   kana_overrides.txt пуст (не страшно)")
    try:
        import pyopenjtalk
        r = pyopenjtalk.g2p("合釘を打ち込む", kana=True)
        ok("pyopenjtalk: %s" % r)
    except Exception as e:
        fail("pyopenjtalk: %s" % e)

    # текст -> хирагана: проверяем сложные случаи (полукатакана, полноразмерная
    # латиница, ヴ-серия, словарные замены, длинная глагольная форма)
    print("  --   текст -> хирагана (сложные случаи):")
    for src, want in ((u"ｶﾞｷｮｳ", u"がきょう"),
                      (u"ＩＥＣ規格", u"あいえーしーきかく"),
                      (u"合折釘", u"あいおれくぎ"),
                      (u"食べさせられたくなかった", u"たべさせられたくなかった"),
                      (u"キョウト", u"きょうと")):
        got = kanaize(src)
        if got == want:
            ok("%s -> %s" % (src, got))
        else:
            fail("%s -> %s (ожидалось %s)" % (src, got, want))
    try:
        ac("version")
        ok("AnkiConnect отвечает")
    except SystemExit:
        fail("AnkiConnect недоступен — открой Anki")

    # подстановка чтения из фуриганы в предложение (см. inject_reading)
    print("  --   подстановка чтения из карточки:")
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
        got = inject_reading(sent, note)
        if got == want:
            ok("подстановка: %s" % expr)
        else:
            fail("подстановка: %s -> %s (ожидалось %s)" % (expr, got, want))
        # чтение слова (для озвучки самого Expression) тоже должно быть верным
        w = expression_reading(note)
        if w and not KANJI_RE.search(w):
            ok("чтение слова %s: %s" % (expr, w))
        else:
            fail("чтение слова %s: %s (в чтении остались иероглифы)"
                 % (expr, w))
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
    p.add_argument("--tag", default=None)
    p.add_argument("--force", action="store_true")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--speed", type=float, default=1.0)

    p = sub.add_parser("check", help="проверить колоду")
    p.add_argument("--deck", required=True)
    p.add_argument("--sentence-audio", default=None, help="поле для звука предложения")
    p.add_argument("--word-audio", default=None, help="поле для звука слова")

    p = sub.add_parser("scan", help="найти голоса в папке движка и добавить в voices.json")
    p.add_argument("--apply", action="store_true",
                   help="записать новые голоса в voices.json (без флага — только показать)")
    p.add_argument("--json", action="store_true", help="машинночитаемый вывод (для GUI)")

    sub.add_parser("selftest", help="проверить файлы/референсы/Anki/сервер")

    args = ap.parse_args()
    if not args.cmd:
        menu()
        return
    result = {"list": cmd_list, "add": cmd_add, "serve": cmd_serve, "test": cmd_test,
              "clone": cmd_clone, "voice": cmd_voice, "make-deck": cmd_make_deck,
              "check": cmd_check, "scan": cmd_scan,
              "selftest": cmd_selftest}[args.cmd](args)
    if args.cmd == "check" and result is False:
        sys.exit(1)


if __name__ == "__main__":
    main()
