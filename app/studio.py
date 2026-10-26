# -*- coding: utf-8 -*-
"""Новый голос: базовые веса для голоса без обучения и студия обучения.

Голос GPT-SoVITS — пара весов (GPT .ckpt + SoVITS .pth) и запись-образец.
Свой голос получается двумя путями:

* без обучения — базовые (предобученные) веса движка + запись-образец 3-10 с:
  движок подхватывает тембр из записи «на лету». Сходство хуже, чем у
  обученного голоса, зато готово за минуту;
* с обучением — в студии GPT-SoVITS (webui.py движка): нарезка записей,
  распознавание текста, дообучение SoVITS и GPT. Готовые веса появляются в
  GPT_weights_* / SoVITS_weights_*, оттуда их подхватывает «Найти голоса».

Студию запускаем тем же Python, что и сервер синтеза, и прибиваем к
127.0.0.1 (сам webui.py слушает 0.0.0.0 — то есть всю локальную сеть).
"""
import os
import signal
import subprocess
import sys
import threading
import time
import urllib.request

import oscompat

STUDIO_PORT = 9874
STUDIO_URL = "http://127.0.0.1:%d/" % STUDIO_PORT
HF_REPO = "lj1995/GPT-SoVITS"
PM = "GPT_SoVITS/pretrained_models"

# (версия, GPT, SoVITS) — от новых к старым; берём первую пару, что есть
BASE_PAIRS = (
    ("v2ProPlus", PM + "/s1v3.ckpt", PM + "/v2Pro/s2Gv2ProPlus.pth"),
    ("v2Pro", PM + "/s1v3.ckpt", PM + "/v2Pro/s2Gv2Pro.pth"),
    ("v3", PM + "/s1v3.ckpt", PM + "/s2Gv3.pth"),
    ("v2", PM + "/gsv-v2final-pretrained/s1bert25hz-5kh-longer-epoch=12-step=369668.ckpt",
     PM + "/gsv-v2final-pretrained/s2G2333k.pth"),
    ("v1", PM + "/s1bert25hz-2kh-longer-epoch=68e-step=50232.ckpt", PM + "/s2G488k.pth"),
)

# дискриминаторы нужны только обучению v2Pro/v2ProPlus — установщик их не
# качает (синтезу они не нужны), докачиваем при первом запуске студии
TRAIN_FILES = (PM + "/v2Pro/s2Dv2Pro.pth", PM + "/v2Pro/s2Dv2ProPlus.pth")
TRAIN_MB = 250



def _shim_dir():
    """app/studio_shim: у exe модули вшиты, а подкладка лежит на диске в app\\."""
    base = (os.path.join(os.path.dirname(os.path.abspath(sys.executable)), "app")
            if getattr(sys, "frozen", False)
            else os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "studio_shim")


_S = {"phase": "idle", "msg": "", "error": "", "pid": None}
_LOCK = threading.Lock()


def base_weights(engine):
    """(версия, GPT, SoVITS) базовых весов движка — пути от папки движка."""
    for ver, gpt, sov in BASE_PAIRS:
        if (os.path.isfile(os.path.join(engine, gpt))
                and os.path.isfile(os.path.join(engine, sov))):
            return ver, gpt, sov
    return None


def missing_train_files(engine):
    """Чего не хватает для обучения v2Pro (пусто, если движок старше v2Pro)."""
    if not os.path.isdir(os.path.join(engine, PM, "v2Pro")):
        return []
    return [f for f in TRAIN_FILES if not os.path.isfile(os.path.join(engine, f))]


def _up():
    try:
        with urllib.request.urlopen(STUDIO_URL, timeout=2) as r:
            return r.status == 200
    except Exception:
        return False


def status(engine):
    up = _up()
    with _LOCK:
        if up:
            _S["phase"] = "running"
        elif _S["phase"] == "running":
            _S["phase"] = "idle"           # закрыли снаружи
        st = {k: _S[k] for k in ("phase", "msg", "error")}
    st.update(running=up, url=STUDIO_URL,
              missing=missing_train_files(engine) if engine else [],
              train_mb=TRAIN_MB)
    return st


def start(engine, python, lang="ru_RU"):
    with _LOCK:
        if _S["phase"] in ("download", "starting"):
            return
        _S.update(phase="starting", msg="", error="")
    if _up():
        with _LOCK:
            _S["phase"] = "running"
        return
    threading.Thread(target=_start_worker, args=(engine, python, lang),
                     daemon=True).start()


def _set(**kw):
    with _LOCK:
        _S.update(**kw)


def _start_worker(engine, python, lang):
    try:
        miss = missing_train_files(engine)
        if miss:
            _set(phase="download",
                 msg="Скачиваю файлы для обучения (~%d МБ, один раз)…" % TRAIN_MB)
            code = ("import sys\n"
                    "from huggingface_hub import hf_hub_download\n"
                    "for f in sys.argv[2:]:\n"
                    "    hf_hub_download(%r, f, local_dir=sys.argv[1])\n" % HF_REPO)
            r = subprocess.run(
                [python, "-c", code, os.path.join(engine, PM)] +
                [f[len(PM) + 1:] for f in miss],
                capture_output=True, text=True, timeout=3600,
                creationflags=oscompat.NO_WINDOW)
            if r.returncode != 0:
                tail = (r.stderr or r.stdout or "").strip().splitlines()[-1:]
                raise RuntimeError("не удалось скачать файлы для обучения: %s"
                                   % (tail[0][:200] if tail else "нет ответа"))
        _set(phase="starting", msg="Запускаю студию — первый раз до минуты…")
        os.makedirs(os.path.join(engine, "logs"), exist_ok=True)
        log_path = os.path.join(engine, "logs", "studio.log")
        log = open(log_path, "a", encoding="utf-8")
        env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8",
                   language=lang)
        env["PYTHONPATH"] = _shim_dir() + os.pathsep + env.get("PYTHONPATH", "")
        kw = ({"creationflags": oscompat.NO_WINDOW} if oscompat.IS_WIN
              else {"start_new_session": True})
        proc = subprocess.Popen([python, "-u", "webui.py", lang], cwd=engine,
                                env=env, stdout=log, stderr=subprocess.STDOUT,
                                stdin=subprocess.DEVNULL, **kw)
        _set(pid=proc.pid)
        t0 = time.time()
        while time.time() - t0 < 300:
            if _up():
                _set(phase="running", msg="")
                return
            if proc.poll() is not None:
                raise RuntimeError("студия закрылась при запуске — см. %s" % log_path)
            time.sleep(1.5)
        raise RuntimeError("студия не запустилась за 5 минут — см. %s" % log_path)
    except Exception as e:
        _set(phase="error", msg="", error=str(e))


def stop():
    """Закрыть студию вместе с её процессами (обучение, вкладка синтеза)."""
    with _LOCK:
        pid = _S.get("pid")
        _S.update(phase="idle", msg="", error="", pid=None)
    if not pid:
        pid = oscompat.port_pid(STUDIO_PORT)
    if not pid:
        return False
    try:
        if oscompat.IS_WIN:
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                           capture_output=True, timeout=20)
        else:
            os.killpg(os.getpgid(int(pid)), signal.SIGTERM)
    except (OSError, ValueError):
        try:
            oscompat.kill_pid(pid)
        except OSError:
            return False
    return True
