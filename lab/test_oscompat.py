# -*- coding: utf-8 -*-
"""test_oscompat.py — платформенный слой (app/oscompat.py) без Anki и GPU.

Запуск:  python lab/test_oscompat.py
Проверяет на текущей ОС: папку настроек, поиск Python движка, PID и имя
процесса на порту, блокировку второго экземпляра, генератор версий для
окружения движка на Linux.
"""
import os
import socket
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "app"))
sys.path.insert(0, os.path.join(ROOT, "linux"))

import oscompat  # noqa: E402

fails = []


def check(cond, msg):
    print(("OK   " if cond else "FAIL ") + msg)
    if not cond:
        fails.append(msg)


def test_app_dir():
    env = "APPDATA" if oscompat.IS_WIN else "XDG_CONFIG_HOME"
    old = os.environ.get(env)
    tmp = tempfile.mkdtemp(prefix="av_os_")
    os.environ[env] = tmp
    try:
        check(oscompat.app_dir() == os.path.join(tmp, "AnkiVoice"),
              "папка настроек считается от %s" % env)
        with open(os.path.join(oscompat.app_dir(create=True), "config.json"),
                  "w", encoding="utf-8") as f:
            f.write('{"gptsovits_path": "/x"}')
        check(oscompat.read_app_config().get("gptsovits_path") == "/x",
              "config.json читается")
    finally:
        if old is None:
            os.environ.pop(env, None)
        else:
            os.environ[env] = old


def test_engine_python():
    eng = tempfile.mkdtemp(prefix="av_eng_")
    old = os.environ.pop("GPT_SOVITS_PYTHON", None)
    try:
        os.environ["GPT_SOVITS_PYTHON"] = sys.executable
        check(oscompat.engine_python(eng) == sys.executable,
              "GPT_SOVITS_PYTHON имеет приоритет")
        if not oscompat.IS_WIN:
            # Windows-рантайм на Linux не годится, даже если лежит в папке
            os.environ.pop("GPT_SOVITS_PYTHON")
            os.makedirs(os.path.join(eng, "runtime"))
            open(os.path.join(eng, "runtime", "python.exe"), "w").close()
            got = oscompat.engine_python(eng) or ""
            check(not got.endswith(".exe"), "python.exe на Linux пропускается")
    finally:
        os.environ.pop("GPT_SOVITS_PYTHON", None)
        if old is not None:
            os.environ["GPT_SOVITS_PYTHON"] = old


def test_port_pid():
    srv = subprocess.Popen(
        [sys.executable, "-c",
         "import socket,sys,time;s=socket.socket();s.bind(('127.0.0.1',0));"
         "s.listen();print(s.getsockname()[1],flush=True);time.sleep(30)"],
        stdout=subprocess.PIPE, text=True)
    try:
        port = int(srv.stdout.readline())
        pid = oscompat.port_pid(port)
        check(str(pid) == str(srv.pid), "port_pid: слушающий процесс найден")
        check("python" in oscompat.process_name(pid).lower(),
              "process_name: %s" % oscompat.process_name(pid))
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        free = s.getsockname()[1]
        s.close()
        check(oscompat.port_pid(free) is None, "port_pid: закрытый порт -> None")
        oscompat.kill_pid(pid)
        srv.wait(timeout=10)
        check(srv.poll() is not None, "kill_pid завершает процесс")
    finally:
        if srv.poll() is None:
            srv.kill()


def test_lock():
    p = os.path.join(tempfile.mkdtemp(prefix="av_lock_"), "pipeline.lock")
    f = open(p, "a+")
    oscompat.try_lock(f)
    code = ("import sys;sys.path.insert(0,%r);import oscompat\n"
            "f=open(%r,'a+')\n"
            "try:\n oscompat.try_lock(f);print('free')\n"
            "except OSError:\n print('busy')\n"
            % (os.path.join(ROOT, "app"), p))
    out = subprocess.run([sys.executable, "-c", code], capture_output=True,
                         text=True).stdout.strip()
    check(out == "busy", "второй процесс не берёт блокировку (%s)" % out)
    f.close()


def test_engine_constraints():
    import engine_constraints as ec
    eng = tempfile.mkdtemp(prefix="av_gsv_")
    site = os.path.join(eng, "runtime", "Lib", "site-packages")
    os.makedirs(site)
    for d in ("transformers-4.43.0.dist-info", "torch-2.0.0+cu118.dist-info",
              "fast_langdetect-0.2.5.dist-info", "jieba_fast-0.53.dist-info"):
        os.makedirs(os.path.join(site, d))
    with open(os.path.join(eng, "requirements.txt"), "w") as f:
        f.write("torch\njieba_fast\nfast_langdetect>=0.2\n")
    lines = ec.build(eng)
    check("transformers==4.43.0" in lines, "версия transformers из рантайма")
    check("fast-langdetect==0.2.5" in lines, "версия fast_langdetect из рантайма")
    check("jieba-fast==0.53" in lines, "пакет из requirements.txt фиксируется")
    check(not any(x.startswith("torch") for x in lines), "torch не фиксируется")
    check("transformers<4.51" not in lines, "общая рамка заменена точной версией")
    check("setuptools<81" in lines, "setuptools<81 всегда")
    check(ec.build(tempfile.mkdtemp()) == ec.COMMON + ec.GIT_ENGINE,
          "без рантайма — общие рамки и рамки эпохи v2Pro")


def main():
    for t in (test_app_dir, test_engine_python, test_port_pid, test_lock,
              test_engine_constraints):
        t()
    print("\nошибок: %d" % len(fails))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
