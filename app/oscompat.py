# -*- coding: utf-8 -*-
"""Всё, что зависит от ОС, — в одном месте (Windows и Linux).

Остальной код не проверяет os.name сам: спрашивает здесь, где конфиг,
какой Python у движка, где ffmpeg, кто слушает порт и как открыть файл.

Раскладка на Linux (её создаёт install.sh):
  ~/.config/AnkiVoice/            — config.json, last_run.json, отчёты
  ~/.local/share/AnkiVoice/gsv-venv/  — Python движка GPT-SoVITS
  <приложение>/pyruntime/         — свой Python для чтения (Haqumei/Sudachi)
Модуль только из stdlib: его импортирует и лёгкий веб-интерфейс, и пайплайн.
"""
import json
import os
import shutil
import signal
import subprocess
import sys

IS_WIN = os.name == "nt"
APP_NAME = "AnkiVoice"

# флаг «без окна консоли» для дочерних процессов (на Linux его нет)
NO_WINDOW = 0x08000000 if IS_WIN else 0


# ---------------------------------------------------------------- папки
def appdata_base():
    """Корень пользовательских настроек: %APPDATA% или ~/.config."""
    if IS_WIN:
        return os.environ.get("APPDATA") or os.path.expanduser("~")
    return os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")


def app_dir(name=APP_NAME, create=False):
    """Папка настроек приложения (%APPDATA%\\AnkiVoice, ~/.config/AnkiVoice)."""
    d = os.path.join(appdata_base(), name)
    if create:
        os.makedirs(d, exist_ok=True)
    return d


def data_dir(create=False):
    """Папка данных: на Linux ~/.local/share/AnkiVoice (окружение движка)."""
    if IS_WIN:
        d = app_dir()
    else:
        d = os.path.join(os.environ.get("XDG_DATA_HOME")
                         or os.path.expanduser("~/.local/share"), APP_NAME)
    if create:
        os.makedirs(d, exist_ok=True)
    return d


def read_app_config():
    """config.json приложения (старое имя AnkiTTS тоже читается) или {}."""
    for name in (APP_NAME, "AnkiTTS"):
        try:
            with open(os.path.join(app_dir(name), "config.json"),
                      encoding="utf-8") as f:
                cfg = json.load(f) or {}
            if cfg:
                return cfg
        except Exception:
            continue
    return {}


# ---------------------------------------------------- Python движка GPT-SoVITS
def _venv_python(d):
    for rel in (("Scripts", "python.exe"), ("bin", "python")):
        p = os.path.join(d, *rel)
        if os.path.isfile(p):
            return p
    return None


def engine_python_candidates(root):
    """Где может лежать интерпретатор движка (по порядку проверки)."""
    cands = []
    env = os.environ.get("GPT_SOVITS_PYTHON")
    if env:
        cands.append(env)
    if root:
        # окружение внутри папки движка — его собственное, оно главнее
        # общего из конфига: иначе при переключении на другой движок
        # подхватывался Python прежнего (с чужими версиями библиотек)
        cands.append(os.path.join(root, "runtime", "python.exe"))
        if not IS_WIN:
            for sub in ("runtime", ".venv", "venv", "env"):
                cands.append(os.path.join(root, sub, "bin", "python"))
    cfg_py = str(read_app_config().get("gptsovits_python") or "").strip()
    if cfg_py:
        cands.append(cfg_py)
    if not IS_WIN:
        cands.append(os.path.join(data_dir(), "gsv-venv", "bin", "python"))
    return cands


def engine_python(root):
    """Интерпретатор, которым запускать api_v2.py и пайплайн, или None.

    На Windows это runtime\\python.exe из пакета движка. На Linux Windows-
    рантайм не запустится, поэтому ищем отдельное окружение: переменная
    GPT_SOVITS_PYTHON, venv внутри самого движка, ключ gptsovits_python в
    config.json или окружение, которое собрал install.sh.
    """
    for p in engine_python_candidates(root):
        p = os.path.expanduser(p)
        if not os.path.isfile(p):
            continue
        if not IS_WIN and p.lower().endswith(".exe"):
            continue
        return p
    return None


def engine_python_label():
    """Как назвать интерпретатор движка в сообщениях."""
    return "runtime\\python.exe" if IS_WIN else "Python движка (gsv-venv)"


# --------------------------------------------- встроенный Python для чтения
def pyruntime_python(root):
    """Python помощников чтения: pyruntime\\python.exe или pyruntime/bin/python."""
    d = os.path.join(root, "pyruntime")
    if IS_WIN:
        return os.path.join(d, "python.exe")
    return os.path.join(d, "bin", "python")


# ------------------------------------------------------------------ ffmpeg
def ffmpeg_path(engine=None):
    """ffmpeg движка (Windows-пакет везёт свой) или системный из PATH."""
    if engine:
        for rel in (("runtime", "ffmpeg.exe"), ("ffmpeg.exe",),
                    ("runtime", "bin", "ffmpeg")):
            p = os.path.join(engine, *rel)
            if os.path.isfile(p) and (IS_WIN or not p.endswith(".exe")):
                return p
    return shutil.which("ffmpeg") or ""


# ---------------------------------------------------------- открыть файл
def open_path(path):
    """Открыть файл/папку программой по умолчанию (как двойной щелчок)."""
    if IS_WIN:
        os.startfile(path)
        return
    opener = "open" if sys.platform == "darwin" else "xdg-open"
    if not shutil.which(opener):
        raise OSError("нет %s — открой вручную: %s" % (opener, path))
    subprocess.Popen([opener, path], stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, start_new_session=True)


def show_error(title, text):
    """Окно с ошибкой, которое видно даже без консоли."""
    if IS_WIN:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, text.replace("\n", "\r\n"),
                                         title, 0x10)      # MB_ICONERROR
        return
    print("%s\n\n%s" % (title, text), file=sys.stderr)
    for cmd in (["zenity", "--error", "--title", title, "--text", text],
                ["kdialog", "--title", title, "--error", text],
                ["notify-send", title, text]):
        if shutil.which(cmd[0]):
            try:
                subprocess.run(cmd, timeout=600)
            except Exception:
                pass
            return


# ------------------------------------------------- где искать движки и Anki
def search_roots():
    """Корни для автопоиска папок движков: диски Windows или типичные места Linux."""
    if IS_WIN:
        import string
        drives = [d + ":\\" for d in string.ascii_uppercase
                  if os.path.exists(d + ":\\")]
        drives.sort(key=lambda p: p[0] != "D")     # D: обычно с движком
        out = []
        for root in drives:
            dl = os.path.join(root, "DOWNLOAD")
            if os.path.isdir(dl):
                out.append(dl)
            out.append(root)
        return out
    home = os.path.expanduser("~")
    out = [os.path.join(home, d) for d in
           ("", "Downloads", "Загрузки", "Projects", "apps", "opt")]
    out.append(data_dir())
    user = os.environ.get("USER") or ""
    for media in ("/run/media/" + user, "/media/" + user, "/mnt", "/media"):
        try:
            for name in sorted(os.listdir(media)):
                disk = os.path.join(media, name)
                out.append(disk)
                for sub in ("LLM", "DOWNLOAD", "Downloads"):
                    out.append(os.path.join(disk, sub))
        except OSError:
            continue
    out.append("/opt")
    seen, res = set(), []
    for p in out:
        p = os.path.normpath(p)
        if p not in seen and os.path.isdir(p):
            seen.add(p)
            res.append(p)
    return res


def fs_roots():
    """Корни для выбора файлов в веб-модалке: буквы дисков или / и ~."""
    if IS_WIN:
        return ["%s:\\" % c for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
                if os.path.exists("%s:\\" % c)]
    roots = [os.path.expanduser("~"), "/"]
    user = os.environ.get("USER") or ""
    for media in ("/run/media/" + user, "/media/" + user, "/mnt"):
        try:
            roots += [os.path.join(media, n) for n in sorted(os.listdir(media))]
        except OSError:
            continue
    return [r for r in roots if os.path.isdir(r)]


def _custom_anki2():
    """Папка Anki2, указанная при установке (если Anki стоит не там, где
    обычно): ключ anki2_dir в config.json или app/anki2_dir.txt (Windows)."""
    out = []
    v = (read_app_config() or {}).get("anki2_dir")
    if v:
        out.append(os.path.expanduser(v))
    try:
        here = os.path.dirname(os.path.abspath(__file__))
        if getattr(sys, "frozen", False):
            here = os.path.join(os.path.dirname(os.path.abspath(sys.executable)), "app")
        with open(os.path.join(here, "anki2_dir.txt"), encoding="utf-8-sig") as f:
            v = f.read().strip()
        if v:
            out.append(v)
    except OSError:
        pass
    return out


def anki2_dirs():
    """Папки данных Anki (Anki2), где лежат профили с collection.media."""
    if IS_WIN:
        return _custom_anki2() + [os.path.join(os.environ.get("APPDATA", ""), "Anki2")]
    home = os.path.expanduser("~")
    xdg = os.environ.get("XDG_DATA_HOME") or os.path.join(home, ".local", "share")
    return _custom_anki2() + [os.path.join(xdg, "Anki2"),
            os.path.join(home, ".var", "app", "net.ankiweb.Anki",
                         "data", "Anki2"),                # Flatpak
            os.path.join(home, "snap", "anki-woodrow", "common", "Anki2"),
            os.path.join(home, "Anki2")]


# ------------------------------------------------ процесс, слушающий порт
def port_pid(port):
    """PID процесса, слушающего TCP-порт (строкой), либо None."""
    if IS_WIN:
        try:
            out = subprocess.run(["netstat", "-ano"], capture_output=True,
                                 text=True, timeout=20)
            for line in out.stdout.splitlines():
                if "LISTENING" in line and (":%d " % port) in line:
                    return line.split()[-1]
        except Exception:
            pass
        return None
    return _linux_port_pid(port)


def _linux_port_pid(port):
    """Linux без внешних утилит: сокет в LISTEN из /proc/net/tcp* -> его PID."""
    inodes = set()
    for tab in ("/proc/net/tcp", "/proc/net/tcp6"):
        try:
            with open(tab) as f:
                next(f, None)
                for line in f:
                    parts = line.split()
                    if len(parts) < 10 or parts[3] != "0A":      # 0A = LISTEN
                        continue
                    if int(parts[1].rsplit(":", 1)[1], 16) == port:
                        inodes.add(parts[9])
        except OSError:
            continue
    inodes.discard("0")
    if not inodes:
        return None
    want = {"socket:[%s]" % i for i in inodes}
    try:
        pids = [p for p in os.listdir("/proc") if p.isdigit()]
    except OSError:
        return None
    for pid in pids:
        fd_dir = os.path.join("/proc", pid, "fd")
        try:
            for fd in os.listdir(fd_dir):
                try:
                    if os.readlink(os.path.join(fd_dir, fd)) in want:
                        return pid
                except OSError:
                    continue
        except OSError:
            continue                    # чужой процесс: прав на fd нет
    return None


def process_name(pid):
    """Имя исполняемого файла процесса ('python.exe', 'python3.10') или '?'."""
    if IS_WIN:
        try:
            out = subprocess.run(
                ["tasklist", "/FI", "PID eq %s" % pid, "/FO", "CSV", "/NH"],
                capture_output=True, text=True, timeout=20)
            line = out.stdout.strip().splitlines()[0]
            return line.split('","')[0].strip('"')
        except Exception:
            return "?"
    try:
        exe = os.readlink("/proc/%s/exe" % pid)
        return os.path.basename(exe)
    except OSError:
        pass
    try:
        with open("/proc/%s/comm" % pid, encoding="utf-8") as f:
            return f.read().strip() or "?"
    except OSError:
        return "?"


def process_cwd(pid):
    """Рабочая папка процесса (Linux, /proc) или None, если узнать нельзя."""
    if IS_WIN:
        return None
    try:
        return os.readlink("/proc/%s/cwd" % pid)
    except OSError:
        return None


def kill_pid(pid):
    """Принудительно завершить процесс."""
    if IS_WIN:
        subprocess.run(["taskkill", "/PID", str(pid), "/F"],
                       capture_output=True, timeout=20)
        return
    os.kill(int(pid), signal.SIGKILL)


# -------------------------------------------------------- блокировка файла
def try_lock(f):
    """Неблокирующая эксклюзивная блокировка открытого файла; OSError — занято."""
    if IS_WIN:
        import msvcrt
        msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
    else:
        import fcntl
        fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
