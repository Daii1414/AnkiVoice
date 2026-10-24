# -*- coding: utf-8 -*-
"""Движки: выбор GPT-SoVITS/IndexTTS, поиск папки, сервер и веса.

Состояние движка живёт в av_state (ENGINE/PYTHON/...), заполняется
resolve_engine()+apply_engine() при импорте пайплайна. ensure_voice()
и _read_engine_local_file() лениво импортируют voices: voices нужны
engine_kind/require_engine, а движку — реестр голосов; цикл разрываем
ленивым импортом.
"""
import json
import os
import re
import shutil
import socket
import subprocess
import time
import urllib.error
import urllib.request

import av_state
from anki_api import _NO_PROXY
from paths import CODE, lab_dir

TTS_HOST, TTS_PORT = "127.0.0.1", 9880
TTS_URL = "http://%s:%d" % (TTS_HOST, TTS_PORT)
DEFAULT_START_CONFIG = os.path.join("GPT_SoVITS", "configs", "tts_infer.yaml")

ENGINE_GPT = "gpt-sovits"
ENGINE_INDEX = "indextts"
INDEXTTS_DEFAULT_URL = "http://127.0.0.1:9881"

# ------------------------------------------------------------- выбор движка
# Движков два: GPT-SoVITS (как раньше) и IndexTTS 2.5. Выбор хранится в
# конфиге приложения (engine), чтобы переключатель в интерфейсе был один
# на всё приложение.


def engine_kind(cfg=None):
    """Какой движок выбран: 'gpt-sovits' (по умолчанию) или 'indextts'."""
    c = cfg if cfg is not None else _read_app_config()
    kind = str((c or {}).get("engine") or "").strip().lower()
    if kind in (ENGINE_INDEX, "indextts2", "indextts2.5", "index-tts", "index_tts"):
        return ENGINE_INDEX
    return ENGINE_GPT


def indextts_url(cfg=None):
    """Адрес сервиса IndexTTS (он поднимается нашим же скриптом)."""
    c = cfg if cfg is not None else _read_app_config()
    url = str((c or {}).get("indextts_url") or "").strip() or INDEXTTS_DEFAULT_URL
    return url.rstrip("/")


def indextts_dir(cfg=None):
    """Папка с установленным IndexTTS (репозиторий с checkpoints и .venv)."""
    c = cfg if cfg is not None else _read_app_config()
    return str((c or {}).get("indextts_path") or "").strip()


# Какие поля карточки читать (текст) и куда писать (звук). Можно переопределить
# на вкладке «Поля колоды» / через CLI — разные колоды называют поля по-разному.

# --------------------------------------------------- поиск папки GPT-SoVITS
def _is_engine(p):
    """Папка похожа на установку GPT-SoVITS: есть интерпретатор и api_v2.py."""
    return bool(p) and os.path.isfile(os.path.join(p, "runtime", "python.exe")) \
        and os.path.isfile(os.path.join(p, "api_v2.py"))


def _read_engine_local_file():
    try:
        from voices import ENGINE_LOCAL_FILE  # лениво: voices -> engines
        with open(ENGINE_LOCAL_FILE, encoding="utf-8") as f:
            s = f.read().strip().strip('"').strip("'")
        return s or None
    except OSError:
        return None


def _read_app_config():
    """Конфиг приложения (%APPDATA%\\AnkiVoice\\config.json) целиком."""
    for name in ("AnkiVoice", "AnkiTTS"):
        cfgp = os.path.join(os.environ.get("APPDATA") or "", name, "config.json")
        try:
            with open(cfgp, encoding="utf-8") as f:
                cfg = json.load(f) or {}
            if cfg:
                return cfg
        except Exception:
            continue
    return {}


def _read_engine_gui_config():
    cfg = _read_app_config()
    return cfg.get("gptsovits_path") or None


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
    if not av_state.ENGINE:
        msg = ("Не найдена папка GPT-SoVITS. Укажи её одним из способов:\n"
               "  * переменная окружения  GPT_SOVITS_ROOT=C:\\...\\GPT-SoVITS\n"
               "  * файл gptsovits_path.txt рядом с voice_pipeline.py (одна строка — путь)\n"
               "  * запусти AnkiVoice.exe и выбери папку в окне (сохранится в конфиг)\n"
               "В папке должны быть runtime\\python.exe и файл api_v2.py.")
        if _BAD_ENGINES:
            msg += ("\n\nУказанные пути НЕ подошли (нет runtime\\python.exe или api_v2.py):"
                    + "".join("\n  * %s" % p for p in _BAD_ENGINES))
        raise SystemExit(msg)
    return av_state.ENGINE

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
        with open(av_state.ACTIVE_VOICE_FILE, encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return None


def set_active_voice(name):
    os.makedirs(os.path.dirname(av_state.ACTIVE_VOICE_FILE), exist_ok=True)
    with open(av_state.ACTIVE_VOICE_FILE, "w", encoding="utf-8") as f:
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
    os.makedirs(os.path.dirname(av_state.SERVER_LOG), exist_ok=True)
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    log = open(av_state.SERVER_LOG, "a", encoding="utf-8")
    subprocess.Popen(
        [av_state.PYTHON, "-u", "api_v2.py", "-a", TTS_HOST, "-p", str(TTS_PORT),
         "-c", os.path.relpath(start_config, av_state.ENGINE)],
        cwd=av_state.ENGINE, env=env, stdout=log, stderr=subprocess.STDOUT,
    )
    print("Запускаю GPT-SoVITS, ждём до %d с..." % wait)
    if not wait_port(True, wait):
        raise SystemExit("Сервер не поднялся за %d с, см. %s" % (wait, av_state.SERVER_LOG))
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
    if engine_kind() == ENGINE_INDEX:
        # У IndexTTS веса голоса общие (модель одна), а голос — это референс.
        # Переключать нечего: нужен только наш сервис с загруженной моделью.
        _ensure_indextts_service()
        return
    require_engine()
    from voices import load_voices  # лениво: voices -> engines
    cfg = load_voices()
    start_config = os.path.join(av_state.ENGINE, cfg.get("start_config") or DEFAULT_START_CONFIG)
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

def _start_indextts_service(wait=240):
    """Поднять сервис IndexTTS (наш мост) и дождаться готовности."""
    root = indextts_dir()
    if not root:
        raise SystemExit("Не указана папка IndexTTS (вкладка «Приложение»).")
    if not os.path.isdir(root):
        raise SystemExit("Папки IndexTTS нет: %s" % root)
    model_dir = os.path.join(root, "checkpoints")
    cfg = os.path.join(model_dir, "config.yaml")
    if not os.path.isfile(cfg):
        raise SystemExit("Нет весов IndexTTS: %s" % cfg)
    script = os.path.join(lab_dir(), "indextts_service.py")
    if not os.path.isfile(script):
        raise SystemExit("Нет сервиса: %s" % script)
    url = indextts_url()
    port = 9881
    m = re.search(r":(\d+)(?:/|$)", url)
    if m:
        port = int(m.group(1))
    if _indextts_health(url):
        print("Сервис IndexTTS уже работает.")
        return
    # .venv — уже готовое окружение IndexTTS; uv оставляем запасным путём
    # (он может уйти в сеть и зависнуть на проверке зависимостей).
    venv_py = os.path.join(root, ".venv", "Scripts", "python.exe")
    if not os.path.isfile(venv_py):
        venv_py = os.path.join(root, ".venv", "bin", "python")
    uv = shutil.which("uv")
    if os.path.isfile(venv_py):
        cmd = [venv_py, "-u", script, "--model-dir", model_dir,
               "--port", str(port)]
    elif uv:
        cmd = [uv, "run", "--project", root, "python", script,
               "--model-dir", model_dir, "--port", str(port)]
    else:
        raise SystemExit("Не найден .venv и нет uv — поставь IndexTTS "
                         "(uv sync --extra webui).")
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    log_path = os.path.join(CODE, "indextts_service.log")
    log = open(log_path, "a", encoding="utf-8")
    subprocess.Popen(cmd, cwd=root, env=env, stdout=log,
                     stderr=subprocess.STDOUT)
    print("Запускаю IndexTTS, ждём до %d c (модель грузится долго)..." % wait)
    if not _wait_indextts(url, wait):
        raise SystemExit("Сервис IndexTTS не поднялся за %d c, см. %s"
                         % (wait, log_path))
    print("IndexTTS готов.")


def _ensure_indextts_service(wait=240):
    """Сервис IndexTTS должен быть живым; если нет — поднимаем."""
    url = indextts_url()
    if _indextts_health(url):
        return True
    _start_indextts_service(wait=wait)
    return True


def cmd_indextts_server(args):
    """Поднять сервис IndexTTS: модель грузится один раз и живёт в памяти.

    Синтез идёт по HTTP (POST /tts) — в отличие от GPT-SoVITS, у IndexTTS
    нет готового HTTP-API, поэтому рядом с приложением лежит наш мост
    lab/indextts_service.py. Запускаем его в окружении IndexTTS (uv).
    """
    _start_indextts_service(wait=getattr(args, "wait", 240) or 240)


def _indextts_health(url):
    try:
        with _NO_PROXY.open(url + "/health", timeout=3) as r:
            return bool(json.loads(r.read(512).decode("utf-8")).get("ok"))
    except Exception:
        return False


def _wait_indextts(url, timeout):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if _indextts_health(url):
            return True
        time.sleep(3)
    return False


def apply_engine(path):
    """Заполнить av_state по найденной папке движка."""
    av_state.ENGINE = path
    av_state.PYTHON = os.path.join(path, "runtime", "python.exe")
    av_state.ACTIVE_VOICE_FILE = os.path.join(path, "logs", "active_voice.txt")
    av_state.SERVER_LOG = os.path.join(path, "logs", "api_v2_pipeline.log")


_resolved = resolve_engine()
if _resolved:
    apply_engine(_resolved)
