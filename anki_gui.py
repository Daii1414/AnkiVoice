# -*- coding: utf-8 -*-
"""anki_gui.py — AnkiVoice: графическая оболочка пайплайна озвучки Anki.

Программа — тонкий интерфейс поверх voice_pipeline.py. Сам exe ничего не
считает: вся работа (синтез, хирагана, веса, AnkiConnect) выполняется
вызовом runtime\\python.exe из папки GPT-SoVITS, где уже лежит проверенный
пайплайн. Поэтому exe лёгкий и не тянет torch.

Основной интерфейс — локальная веб-страница (четыре вкладки: «Озвучка»,
«Поля колоды», «Голос», «Приложение»). Старое tkinter-окно с тремя вкладками
осталось под флагом `--classic`.

Первый запуск: мастер настройки сам ищет папку GPT-SoVITS, проверяет
AnkiConnect, поднимает сервер и предлагает тестовую фразу.
Дальше всё подхватывается само: голоса из voices.json, колоды из AnkiConnect.

Конфиг хранится в %APPDATA%\\AnkiVoice\\config.json
(старый %APPDATA%\\AnkiTTS\\config.json переносится автоматически).
Логи и аварийные дампы — в той же папке.

Headless-режимы (для отладки и сборки):
    anki_gui.py doctor          — диагностика, exit code 0/1
    anki_gui.py doctor --json   — то же в виде JSON
"""

import argparse
import json
import os
import queue
import re
import shutil
import socket
import subprocess
import sys
import threading
import traceback
import urllib.request

APP_NAME = "AnkiVoice"
APP_VERSION = "1.2"
LEGACY_APP_NAME = "AnkiTTS"   # старое имя (до переименования) — конфиг переносим
ANKI_CONNECT = "http://127.0.0.1:8765"
TTS_HOST, TTS_PORT = "127.0.0.1", 9880
CREATE_NO_WINDOW = 0x08000000

# дефолтные sampling-значения (как в официальном webui GPT-SoVITS — спокойнее,
# чем «горячие» дефолты чистого API); перезаписываются из voices.json
DEFAULT_SAMPLING = {"temperature": 0.6, "top_p": 0.6, "top_k": 20}

# маркер старта: пишем ДО всего остального, чтобы было видно даже ранние падения
try:
    _boot = os.path.join(os.environ.get("APPDATA") or ".", APP_NAME)
    os.makedirs(_boot, exist_ok=True)
    with open(os.path.join(_boot, "boot.log"), "a", encoding="utf-8") as _f:
        _f.write("boot ok, argv=%r\n" % (sys.argv,))
except Exception:
    pass


# ------------------------------------------------------------------ утилиты
def version_tuple(s):
    """'v1.2.1' -> (1, 2, 1); мусор -> (0,)."""
    parts = re.findall(r"\d+", str(s or ""))
    return tuple(int(x) for x in parts[:4]) or (0,)


def appdata_dir():
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    d = os.path.join(base, APP_NAME)
    os.makedirs(d, exist_ok=True)
    return d


def code_dir():
    """Папка самого инструмента (рядом лежат voice_pipeline.py, voices.json).

    У замороженного exe __file__ указывает во временную папку распаковки,
    поэтому для frozen-сборки берём папку реального exe.
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


CONFIG_FILE = os.path.join(appdata_dir(), "config.json")
GUI_LOG = os.path.join(appdata_dir(), "gui.log")
CRASH_LOG = os.path.join(appdata_dir(), "gui_crash.log")

# перенос конфига со старого имени (AnkiTTS -> AnkiVoice): путь к движку
# и тема сохраняются, пользователь ничего не настраивает заново
try:
    if not os.path.exists(CONFIG_FILE):
        _legacy = os.path.join(os.environ.get("APPDATA") or "",
                               LEGACY_APP_NAME, "config.json")
        if os.path.isfile(_legacy):
            shutil.copy2(_legacy, CONFIG_FILE)
except Exception:
    pass


def _excepthook(t, v, tb):
    """Любое необработанное исключение — в файл (в windowed-сборке иначе невидимо)."""
    import traceback as _tb
    try:
        text = "".join(_tb.format_exception(t, v, tb))
        with open(CRASH_LOG, "a", encoding="utf-8") as f:
            f.write(text + "\n")
    except Exception:
        pass


sys.excepthook = _excepthook


def out(msg):
    """Печать в консоль, если она есть (в windowed-сборке stdout = None)."""
    for h in (getattr(sys, "stdout", None), sys.__stdout__):
        try:
            if h:
                h.write(str(msg) + "\n")
                h.flush()
                return
        except Exception:
            pass
    try:
        with open(GUI_LOG, "a", encoding="utf-8") as f:
            f.write(str(msg) + "\n")
    except Exception:
        pass


def load_config():
    try:
        with open(CONFIG_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_config(cfg):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


# ------------------------------------------------------ проверка папки GPT-SoVITS
def validate_gptsovits(path):
    """Возвращает список проблем с папкой ДВИЖКА. Пустой список = папка подходит.

    Проверяются только признаки установки GPT-SoVITS. Сам пайплайн
    (voice_pipeline.py, voices.json) лежит рядом с этой программой, не здесь.
    """
    problems = []
    if not path:
        return ["Папка GPT-SoVITS не указана"]
    if not os.path.isdir(path):
        return ["Папка не существует: %s" % path]
    for rel, what in (
        ("runtime\\python.exe", "интерпретатор GPT-SoVITS"),
        ("api_v2.py", "сервер синтеза"),
    ):
        if not os.path.exists(os.path.join(path, rel)):
            problems.append("Нет %s: %s" % (what, os.path.join(path, rel)))
    return problems


def validate_local():
    """Проблемы с самим инструментом (файлы рядом с программой)."""
    problems = []
    here = code_dir()
    for rel, what in (
        ("voice_pipeline.py", "пайплайн озвучки"),
        ("voices.json", "реестр голосов"),
    ):
        if not os.path.exists(os.path.join(here, rel)):
            problems.append("Нет %s: %s" % (what, os.path.join(here, rel)))
    return problems


def find_gptsovits_automatic():
    """Автопоиск папки GPT-SoVITS на всех дисках (обычно D:\\DOWNLOAD)."""
    import string
    drives = [d + ":\\" for d in string.ascii_uppercase if os.path.exists(d + ":\\")]
    drives.sort(key=lambda p: p[0] != "D")     # D: обычно с движком
    hints = []
    for root in drives:
        dl = os.path.join(root, "DOWNLOAD")
        if os.path.isdir(dl):
            hints.append(dl)
        hints.append(root)
    for base in hints:
        try:
            for name in sorted(os.listdir(base)):
                if "GPT-SOVITS" not in name.upper():
                    continue
                cand = os.path.join(base, name)
                if not validate_gptsovits(cand):
                    return cand
        except Exception:
            continue
    return None


def load_voices(gpt_path=None):
    """Реестр голосов лежит рядом с программой (CODE), не в папке движка."""
    p = os.path.join(code_dir(), "voices.json")
    try:
        with open(p, encoding="utf-8") as f:
            cfg = json.load(f)
        return cfg.get("voices", {}), cfg.get("default_voice")
    except Exception:
        return {}, None


# --------------------------------------------------------------- Anki / сервер
# локальные запросы — мимо системного прокси (см. voice_pipeline)
_NO_PROXY = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def anki_call(action, timeout=15, **params):
    payload = json.dumps({"action": action, "version": 6, "params": params},
                         ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        ANKI_CONNECT, data=payload,
        headers={"Content-Type": "application/json", "Origin": "http://localhost"})
    with _NO_PROXY.open(req, timeout=timeout) as resp:
        out_json = json.loads(resp.read().decode("utf-8"))
    if out_json.get("error"):
        raise RuntimeError(out_json["error"])
    return out_json["result"]


def anki_status():
    """True, если AnkiConnect отвечает."""
    try:
        anki_call("version", timeout=4)
        return True
    except Exception:
        return False


def tts_status():
    """True, если сервер GPT-SoVITS слушает порт."""
    try:
        s = socket.create_connection((TTS_HOST, TTS_PORT), timeout=2)
        s.close()
        return True
    except OSError:
        return False


def list_decks():
    """[(имя, кол-во заметок)] — колоды Anki с количеством заметок."""
    names = anki_call("deckNames")
    result = []
    for name in names:
        try:
            n = len(anki_call("findNotes", query='deck:"%s"' % name, timeout=60))
        except Exception:
            n = -1
        result.append((name, n))
    return result


def list_note_fields(deck, timeout=60):
    """Имена полей заметок в колоде (берётся по первой заметке)."""
    try:
        ids = anki_call("findNotes", query='deck:"%s"' % deck, timeout=timeout)
        if not ids:
            return []
        info = anki_call("notesInfo", notes=ids[:1], timeout=timeout)
        if not info:
            return []
        return list(info[0]["fields"].keys())
    except Exception:
        return []


# ------------------------------------------------------- запуск пайплайна
class _PipelineRun:
    """Запущенный пайплайн: умеет реально остановить подпроцесс."""

    def __init__(self):
        self.proc = None
        self._lock = threading.Lock()

    def run(self, cmd, cwd, env, on_line, on_done):
        def runner():
            code = -1
            try:
                with self._lock:
                    self.proc = subprocess.Popen(
                        cmd, cwd=cwd, env=env,
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                        stdin=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW)
                for raw in self.proc.stdout:
                    line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
                    if on_line:
                        on_line(line)
                code = self.proc.wait()
            except Exception as e:
                if on_line:
                    on_line("!! Ошибка запуска: %r" % (e,))
            finally:
                if on_done:
                    on_done(code)

        threading.Thread(target=runner, daemon=True).start()

    def stop(self):
        with self._lock:
            proc = self.proc
        if proc and proc.poll() is None:
            try:
                proc.terminate()
                proc.wait(timeout=10)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
            return True
        return False


def pipeline_cmd(gpt_path, args, on_line=None, on_done=None):
    """Запуск voice_pipeline.py в фоне. Возвращает _PipelineRun.

    gpt_path — папка ДВИЖКА (куда ставить python и api). Сам скрипт
    пайплайна лежит рядом с программой (CODE). Движок передаём дочернему
    процессу через переменную GPT_SOVITS_ROOT, чтобы резолюция совпала.
    """
    python = os.path.join(gpt_path, "runtime", "python.exe")
    script = os.path.join(code_dir(), "voice_pipeline.py")
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8",
               GPT_SOVITS_ROOT=gpt_path)
    cmd = [python, "-u", script] + list(args)
    run = _PipelineRun()
    run.run(cmd, code_dir(), env, on_line, on_done)
    return run


# =========================================================== headless-режимы
def doctor(gpt_path=None, as_json=False):
    """Диагностика без интерфейса. Возвращает код выхода 0/1."""
    report = {"config": CONFIG_FILE}
    cfg = load_config()
    path = gpt_path or cfg.get("gptsovits_path") or ""
    if not path and not gpt_path:
        auto = find_gptsovits_automatic()
        if auto:
            path = auto
            report["auto_found"] = True
    report["gptsovits_path"] = path
    report["local_problems"] = validate_local()
    report["problems"] = validate_gptsovits(path)
    if path and not report["problems"]:
        voices, default = load_voices()
        report["voices"] = sorted(voices)
        report["default_voice"] = default
        python = os.path.join(path, "runtime", "python.exe")
        try:
            p = subprocess.run(
                [python, "-c", "import pyopenjtalk;print('ok')"],
                capture_output=True, text=True, timeout=120,
                creationflags=CREATE_NO_WINDOW,
                env=dict(os.environ, PYTHONUTF8="1"))
            report["pyopenjtalk"] = p.returncode == 0
        except Exception as e:
            report["pyopenjtalk"] = False
            report["pyopenjtalk_error"] = repr(e)
    report["anki"] = anki_status()
    report["tts_server"] = tts_status()
    report["ok"] = (not report["problems"] and not report["local_problems"]
                    and report["anki"])
    if as_json:
        out(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        out("Диагностика %s" % APP_NAME)
        out("  инструмент   : %s" % code_dir())
        out("  конфиг       : %s" % CONFIG_FILE)
        out("  GPT-SoVITS   : %s" % (path or "— не указан"))
        for pr in report["local_problems"]:
            out("  ПРОБЛЕМА(инструмент): %s" % pr)
        for pr in report["problems"]:
            out("  ПРОБЛЕМА(движок)    : %s" % pr)
        if "voices" in report:
            out("  голосов      : %d (%s)" % (len(report["voices"]),
                                              ", ".join(report["voices"])))
            out("  pyopenjtalk  : %s" % report.get("pyopenjtalk"))
        out("  AnkiConnect  : %s" % ("да" if report["anki"] else "НЕТ — открой Anki"))
        out("  TTS-сервер   : %s" % ("запущен" if report["tts_server"] else "не запущен (поднимется сам)"))
        out("  ИТОГ         : %s" % ("ok" if report["ok"] else "есть проблемы"))
    return 0 if report["ok"] else 1


# ================================================================ интерфейс
def _payload_problem():
    """Понятная подсказка, если exe запущен без своих файлов.

    Так бывает, когда пользователь скачал zip и запустил AnkiVoice.exe
    прямо из окна архиватора (или оставил файлы на месте не распакованными):
    Windows поднимает exe из временной папки, а рядом нет ни пайплайна,
    ни встроенного рантайма. Вместо каскада непонятных ошибок — одна
    инструкция «что сделать».
    """
    if not getattr(sys, "frozen", False):
        return None                      # запуск с диска — файлы на месте
    d = code_dir()
    missing = [f for f in ("voice_pipeline.py", "sudachi_g2p.py", "voices.json")
               if not os.path.isfile(os.path.join(d, f))]
    if not (os.path.isfile(os.path.join(d, "pyruntime", "python.exe"))
            or os.path.isfile(os.path.join(d, "pyruntime.zip"))):
        missing.append("pyruntime.zip")
    _dic = os.path.join(d, "pyruntime", "Lib", "site-packages",
                        "sudachidict_core", "resources", "system.dic")
    if not (os.path.isfile(_dic)
            or os.path.isfile(os.path.join(d, "sudachidict.zip"))):
        missing.append("sudachidict.zip")
    if not missing:
        return None
    return (
        "AnkiVoice запущен без файлов программы — похоже, exe поднялся "
        "прямо из архива или временной папки.\n\n"
        "Что сделать:\n"
        "  1. Скачай установщик со страницы релизов\n"
        "     (Releases -> AnkiVoice-Setup-x.y.exe)\n"
        "  2. Запусти его — файлы лягут на место, настройки сохранятся\n"
        "  3. Запускай AnkiVoice.exe из папки установки, не из архива\n\n"
        "Не хватает файлов:\n" +
        "".join("  * %s\n" % f for f in missing)
    )


def run_gui(open_tab=None):
    import tkinter as tk
    from tkinter import filedialog, messagebox, scrolledtext, ttk

    _prob = _payload_problem()
    if _prob:
        # WinAPI-диалог вместо tkinter: он гарантированно показывается в любой
        # ситуации (в том числе когда exe поднят из временной папки архиватора)
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, _prob.replace("\n", "\r\n"),
                                         "%s — сначала распакуй zip" % APP_NAME,
                                         0x10)      # MB_ICONERROR
        sys.exit(1)

    LANGS = ["ja", "zh", "en", "ko", "yue", "ru", "de", "fr", "es"]

    # ----------------------------------------------------------- дизайн-система
    # Плоский стиль: карточки на холодном фоне, акцент — индиго, шрифты
    # Segoe UI, статусы — цветные чипы, лог — тёмная консоль.
    # Тема по умолчанию — тёмная; хранится в config.json, переключается
    # кнопкой в шапке (применение — перезапуском окна).
    THEMES = {
        "dark": {
            "page": "#0F1319",       # фон страницы
            "card": "#171C25",       # фон карточек
            "border": "#262E3B",     # рамки карточек и полей
            "line": "#212936",       # тонкие разделители
            "text": "#E7ECF5",       # основной текст
            "sub": "#97A1B3",        # вторичный текст
            "accent": "#8B9BFF",     # акцент (индиго)
            "accent_h": "#A6B2FF",   # акцент при наведении
            "tint": "#26304E",       # подсветка акцента
            "ok": "#4CD797",
            "ok_tint": "#123024",
            "err": "#FF7B7C",
            "err_tint": "#331A1C",
            "chip": "#1E2531",
            "console": "#0C0F14",
            "console_fg": "#D8DEE9",
            "trough": "#2A3242",     # дорожка ползунка
            "input": "#212A37",      # фон полей ввода
            "knob": "#171C25",       # заливка бегунка ползунка
            "onaccent": "#10141C",   # текст на акцентных кнопках
            "hover": "#232C3A",      # наведение на вторичную кнопку
            "disabled": "#5C6675",   # текст выключенной кнопки
            "accent_dis": "#39436B", # фон выключенной акцентной
            "err_h": "#FF9C9C",      # наведение на красную кнопку
            "err_dis": "#5A3033",    # фон выключенной красной
        },
        "light": {
            "page": "#F1F3F8",
            "card": "#FFFFFF",
            "border": "#E3E7EF",
            "line": "#EDF0F5",
            "text": "#1B2233",
            "sub": "#6E7789",
            "accent": "#4F46E5",
            "accent_h": "#4338CA",
            "tint": "#EEF0FF",
            "ok": "#12A150",
            "ok_tint": "#E6F7EF",
            "err": "#E5484D",
            "err_tint": "#FDECEC",
            "chip": "#F2F4F8",
            "console": "#12161C",
            "console_fg": "#D8DEE9",
            "trough": "#DCE1EA",
            "input": "#FFFFFF",
            "knob": "#FFFFFF",
            "onaccent": "#FFFFFF",
            "hover": "#E9EDF4",
            "disabled": "#A9B1BF",
            "accent_dis": "#C3C7EC",
            "err_h": "#CE3C41",
            "err_dis": "#F0B9BA",
        },
    }
    THEME_NAME = "dark"
    try:
        with open(CONFIG_FILE, encoding="utf-8") as _f:
            THEME_NAME = json.load(_f).get("theme", "dark")
    except Exception:
        THEME_NAME = "dark"
    if THEME_NAME not in THEMES:
        THEME_NAME = "dark"
    C = THEMES[THEME_NAME]
    F_TITLE = ("Segoe UI", 16, "bold")
    F_SECT = ("Segoe UI", 10, "bold")
    F_BODY = ("Segoe UI", 10)
    F_SMALL = ("Segoe UI", 9)
    F_TINY = ("Segoe UI", 8)
    F_MONO = ("Consolas", 9)
    F_TAB = ("Segoe UI", 10)
    F_TAB_ON = ("Segoe UI", 10, "bold")

    def apply_theme(root):
        """Настройка ttk-стилей (тема clam даёт полный контроль над цветами)."""
        s = ttk.Style(root)
        try:
            s.theme_use("clam")
        except tk.TclError:
            pass
        root.configure(bg=C["page"])
        s.configure(".", background=C["page"], foreground=C["text"], font=F_BODY)
        s.configure("TFrame", background=C["page"])
        for name, bg, fg, font in (
            ("TLabel", C["page"], C["text"], F_BODY),
            ("Muted.TLabel", C["page"], C["sub"], F_SMALL),
            ("Card.TLabel", C["card"], C["text"], F_BODY),
            ("CardMuted.TLabel", C["card"], C["sub"], F_SMALL),
            ("Section.TLabel", C["card"], C["text"], F_SECT),
        ):
            s.configure(name, background=bg, foreground=fg, font=font)
        # поля ввода
        s.configure("TEntry", fieldbackground=C["input"], foreground=C["text"],
                    borderwidth=1, relief="flat", padding=6, insertcolor=C["text"],
                    bordercolor=C["border"], lightcolor=C["border"], darkcolor=C["border"])
        s.map("TEntry", bordercolor=[("focus", C["accent"])],
              lightcolor=[("focus", C["accent"])], darkcolor=[("focus", C["accent"])])
        s.configure("TCombobox", fieldbackground=C["input"], background=C["input"],
                    foreground=C["text"], borderwidth=1, relief="flat", padding=6,
                    arrowcolor=C["sub"], bordercolor=C["border"],
                    lightcolor=C["border"], darkcolor=C["border"])
        s.map("TCombobox",
              fieldbackground=[("readonly", C["input"])], foreground=[("readonly", C["text"])],
              bordercolor=[("focus", C["accent"])], lightcolor=[("focus", C["accent"])],
              darkcolor=[("focus", C["accent"])], arrowcolor=[("active", C["text"])])
        s.configure("TCombobox.Listbox", background=C["input"], foreground=C["text"],
                    fieldbackground=C["input"], selectbackground=C["accent"],
                    selectforeground=C["onaccent"])
        # кнопки: вторичные (рамка), акцентные (индиго), опасная (красная)
        s.configure("TButton", background=C["card"], foreground=C["text"],
                    borderwidth=1, relief="flat", focusthickness=0, padding=(14, 7),
                    font=F_BODY, bordercolor=C["border"],
                    lightcolor=C["border"], darkcolor=C["border"])
        s.map("TButton", background=[("active", C["hover"]), ("disabled", C["card"])],
              foreground=[("disabled", C["disabled"])])
        s.configure("Accent.TButton", background=C["accent"], foreground=C["onaccent"],
                    borderwidth=0, focusthickness=0, padding=(16, 8),
                    font=("Segoe UI", 10, "bold"), bordercolor=C["accent"],
                    lightcolor=C["accent"], darkcolor=C["accent"])
        s.map("Accent.TButton",
              background=[("active", C["accent_h"]), ("disabled", C["accent_dis"])],
              foreground=[("disabled", C["onaccent"])])
        s.configure("Danger.TButton", background=C["err"], foreground=C["onaccent"],
                    borderwidth=0, focusthickness=0, padding=(14, 8), font=F_BODY,
                    bordercolor=C["err"], lightcolor=C["err"], darkcolor=C["err"])
        s.map("Danger.TButton",
              background=[("active", C["err_h"]), ("disabled", C["err_dis"])])
        # списки, ползунки, флажки
        s.configure("Treeview", background=C["input"], fieldbackground=C["input"],
                    foreground=C["text"], rowheight=28, borderwidth=0, font=F_BODY)
        s.configure("Treeview.Heading", background=C["chip"], foreground=C["sub"],
                    font=F_SECT, relief="flat", padding=(8, 7))
        s.map("Treeview", background=[("selected", C["accent"])],
              foreground=[("selected", C["onaccent"])])
        s.configure("TScrollbar", background=C["chip"], troughcolor=C["page"],
                    bordercolor=C["page"], arrowcolor=C["sub"], borderwidth=0,
                    relief="flat")
        s.map("TScrollbar", background=[("active", C["border"])])
        s.configure("TScale", background=C["card"])
        s.configure("Horizontal.TScale.trough", background=C["trough"], borderwidth=0)
        s.configure("Horizontal.TScale.slider", background=C["accent"], borderwidth=0,
                    bordercolor=C["accent"], lightcolor=C["accent"], darkcolor=C["accent"])
        s.configure("TCheckbutton", background=C["card"], foreground=C["text"],
                    font=F_BODY, focuscolor=C["card"])
        s.configure("TRadiobutton", background=C["card"], foreground=C["text"],
                    font=F_BODY, focuscolor=C["card"])
        s.map("TCheckbutton", background=[("active", C["card"])])
        s.map("TRadiobutton", background=[("active", C["card"])])

    def card(parent, title=None):
        """Белая карточка с тонкой рамкой; содержимое — атрибут .body."""
        outer = tk.Frame(parent, bg=C["card"], highlightthickness=1,
                         highlightbackground=C["border"])
        body = tk.Frame(outer, bg=C["card"])
        if title:
            tk.Label(outer, text=title, font=F_SECT, bg=C["card"], fg=C["text"]
                     ).pack(anchor="w", padx=14, pady=(12, 3))
            tk.Frame(outer, bg=C["line"], height=1).pack(fill="x", padx=14)
            body.pack(fill="both", expand=True, padx=14, pady=(10, 13))
        else:
            body.pack(fill="both", expand=True, padx=14, pady=12)
        outer.body = body
        return outer

    class Chip:
        """Статусный чип в шапке: цветная точка + текст."""

        def __init__(self, parent, text=None, textvariable=None, good=None):
            self.frame = tk.Frame(parent, bg=C["chip"])
            self.dot = tk.Label(self.frame, text="●", font=("Segoe UI", 7),
                                bg=C["chip"], fg=C["accent"])
            kw = {"textvariable": textvariable} if textvariable is not None \
                else {"text": text or ""}
            self.text_lbl = tk.Label(self.frame, font=F_SMALL, fg=C["text"],
                                     bg=C["chip"], **kw)
            self.dot.pack(side="left", padx=(10, 4), pady=5)
            self.text_lbl.pack(side="left", padx=(0, 10))
            self.set_ok(good)

        def set_ok(self, good):
            if good is None:                       # нейтральный чип
                bg, dot = C["chip"], C["accent"]
            elif good:                             # всё хорошо — зелёный
                bg, dot = C["ok_tint"], C["ok"]
            else:                                  # проблема — красный
                bg, dot = C["err_tint"], C["err"]
            self.frame.configure(bg=bg)
            self.dot.configure(bg=bg, fg=dot)
            self.text_lbl.configure(bg=bg)

    class FlatSlider(tk.Canvas):
        """Плоский ползунок: тонкая дорожка + круглый бегунок акцентного цвета."""

        def __init__(self, parent, var, from_, to, **kw):
            super().__init__(parent, bg=C["card"], highlightthickness=0, height=22,
                             **kw)
            self.var, self.from_, self.to = var, float(from_), float(to)
            self.bind("<Configure>", lambda e: self.redraw())
            var.trace_add("write", lambda *a: self.redraw())
            self.bind("<Button-1>", self._press)
            self.bind("<B1-Motion>", self._press)
            self.bind("<Enter>", lambda e: self.configure(cursor="hand2"))
            self.bind("<Leave>", lambda e: self.configure(cursor=""))

        def _track(self):
            w = max(self.winfo_width(), 40)
            x0, x1 = 9.0, w - 9.0
            span = max(self.to - self.from_, 1e-9)
            frac = (float(self.var.get()) - self.from_) / span
            return x0, x1, x0 + max(0.0, min(1.0, frac)) * (x1 - x0)

        def redraw(self):
            self.delete("all")
            x0, x1, cx = self._track()
            cy = 11
            self.create_rectangle(x0, cy - 3, x1, cy + 3, fill=C["trough"],
                                  outline="", tags=("track",))
            if cx > x0:
                self.create_rectangle(x0, cy - 3, cx, cy + 3, fill=C["accent"],
                                      outline="", tags=("fill",))
            self.create_oval(cx - 8, cy - 8, cx + 8, cy + 8, fill=C["knob"],
                             outline=C["accent"], width=2, tags=("knob",))

        def _press(self, event):
            x0, x1, _ = self._track()
            frac = (event.x - x0) / max(x1 - x0, 1.0)
            val = self.from_ + max(0.0, min(1.0, frac)) * (self.to - self.from_)
            self.var.set(int(round(val)) if isinstance(self.var, tk.IntVar)
                         else round(val, 3))
            self.redraw()

    class SegTabs:
        """Плоская навигация с акцентным подчёркиванием вместо вкладок Windows."""

        def __init__(self, bar, container):
            self.bar = bar
            self.container = container
            self.entries = []          # [frame, tab, label, underline]
            self.current = None

        def add(self, frame, text):
            tab = tk.Frame(self.bar, bg=C["page"], cursor="hand2")
            lab = tk.Label(tab, text=text, bg=C["page"], fg=C["sub"], font=F_TAB,
                           padx=18, pady=9)
            lab.grid(row=0, column=0, sticky="nsew")
            ul = tk.Frame(tab, bg=C["page"], height=3)
            ul.grid(row=1, column=0, sticky="ew")
            self.entries.append([frame, tab, lab, ul])
            for w in (tab, lab):
                w.bind("<Button-1>", lambda e, f=frame: self.select(f))
                w.bind("<Enter>", lambda e, l=lab, f=frame: self._hover(l, f, True))
                w.bind("<Leave>", lambda e, l=lab, f=frame: self._hover(l, f, False))
            tab.pack(side="left", fill="y")
            frame.pack_forget()
            if self.current is None:
                self.select(frame)

        def _hover(self, lab, frame, on):
            if frame is not self.current:
                lab.configure(fg=C["text"] if on else C["sub"])

        def select(self, frame):
            self.current = frame
            for fr, tab, lab, ul in self.entries:
                active = fr is frame
                lab.configure(fg=C["text"] if active else C["sub"],
                              font=F_TAB_ON if active else F_TAB)
                ul.configure(bg=C["accent"] if active else C["page"])
                if active:
                    fr.pack(in_=self.container, fill="both", expand=True)
                    fr.tkraise()
                else:
                    fr.pack_forget()

    class App(tk.Tk):
        def __init__(self, open_tab=None):
            super().__init__()
            self.title("%s — озвучка колод Anki" % APP_NAME)
            self.geometry("1040x815")
            self.minsize(940, 700)
            apply_theme(self)
            self.run = None
            self.decks = []
            self.voices = {}
            self.default_voice = None
            self.current_voice = None
            self.fields = {"sentence_src": "Sentence", "sentence_audio": "SentenceAudio",
                           "word_src": "Expression", "word_audio": "ExpressionAudio",
                           "furigana_src": "ExpressionFurigana"}
            self._aux_list = []
            self._build()
            self._load_initial_path()
            self._refresh_decks_async()
            self._poll_status()
            # тихий автоскан весов движка: подтягиваем новые голоса в voices.json
            self.after(1500, lambda: self._scan_voices_async(True))
            if open_tab:
                self.after_idle(lambda: self.after(300, lambda: self._open_tab(open_tab)))
            self.protocol("WM_DELETE_WINDOW", self.on_close)

        def _open_tab(self, name):
            tab = {"voice": self.tab_voice, "anki": self.tab_anki,
                   "final": self.tab_final}.get(name)
            if tab is not None:
                self.nb.select(tab)

        def _toggle_theme(self):
            """Переключить тему и перезапустить окно (так надёжнее, чем
            перекрашивать живые виджеты: все цвета заданы при сборке UI)."""
            cfg = load_config()
            cfg["theme"] = "light" if THEME_NAME == "dark" else "dark"
            save_config(cfg)
            cmd = [sys.executable]
            if not getattr(sys, "frozen", False):
                cmd.append(sys.argv[0])
            cmd += sys.argv[1:]
            try:
                subprocess.Popen(cmd, cwd=code_dir())
            except OSError:
                pass
            self.destroy()

        # ------------------------------------------------------- построение UI
        def _build(self):
            # --- шапка: заголовок слева, статусы-чипы справа
            hdr = tk.Frame(self, bg=C["card"], highlightthickness=1,
                           highlightbackground=C["border"])
            hdr.pack(fill="x")
            titles = tk.Frame(hdr, bg=C["card"])
            titles.pack(side="left", padx=20, pady=11)
            tk.Label(titles, text="AnkiVoice", font=F_TITLE, bg=C["card"],
                     fg=C["accent"]).pack(anchor="w")
            tk.Label(titles, text="озвучка колод Anki голосами GPT-SoVITS",
                     font=F_SMALL, bg=C["card"], fg=C["sub"]).pack(anchor="w")
            self.var_anki = tk.StringVar(value="Anki: …")
            self.var_tts = tk.StringVar(value="Сервер: …")
            self.var_info = tk.StringVar(value="")
            self.chip_info = Chip(hdr, textvariable=self.var_info)
            self.chip_tts = Chip(hdr, textvariable=self.var_tts)
            self.chip_anki = Chip(hdr, textvariable=self.var_anki)
            # кнопка переключения темы (правее чипов; применение — перезапуском)
            self.btn_theme = tk.Label(
                hdr, text="Светлая тема" if THEME_NAME == "dark" else "Тёмная тема",
                font=F_SMALL, bg=C["chip"], fg=C["sub"], padx=10, pady=5,
                cursor="hand2")
            self.btn_theme.pack(side="right", padx=(0, 20), pady=14)
            self.btn_theme.bind("<Button-1>", lambda e: self._toggle_theme())
            self.btn_theme.bind("<Enter>",
                                lambda e: self.btn_theme.configure(fg=C["text"]))
            self.btn_theme.bind("<Leave>",
                                lambda e: self.btn_theme.configure(fg=C["sub"]))
            self.chip_info.frame.pack(side="right", padx=6, pady=14)
            self.chip_tts.frame.pack(side="right", padx=6, pady=14)
            self.chip_anki.frame.pack(side="right", padx=6, pady=14)

            # --- строка пути к движку
            frm_path = tk.Frame(self, bg=C["page"])
            frm_path.pack(fill="x", padx=20, pady=(14, 4))
            tk.Label(frm_path, text="GPT-SoVITS", font=F_SECT, bg=C["page"],
                     fg=C["text"]).pack(side="left", padx=(0, 12))
            self.var_path = tk.StringVar()
            ent_path = ttk.Entry(frm_path, textvariable=self.var_path)
            ent_path.pack(side="left", fill="x", expand=True)
            self._add_edit_menu(ent_path)
            ttk.Button(frm_path, text="Обзор…", command=self.browse_path
                       ).pack(side="left", padx=(8, 0))
            ttk.Button(frm_path, text="Проверить", command=self.check_path
                       ).pack(side="left", padx=(6, 0))

            # --- нижняя строка состояния (упакована до контейнера: всегда снизу)
            foot = tk.Frame(self, bg=C["card"], highlightthickness=1,
                            highlightbackground=C["border"])
            foot.pack(fill="x", side="bottom")
            self.var_status = tk.StringVar(value="Готово")
            tk.Label(foot, textvariable=self.var_status, font=F_SMALL, bg=C["card"],
                     fg=C["sub"], anchor="w").pack(fill="x", padx=20, pady=7)

            # --- навигация + содержимое вкладок
            container = tk.Frame(self, bg=C["page"])
            container.pack(fill="both", expand=True, padx=20, pady=(12, 8))
            bar = tk.Frame(container, bg=C["page"])
            bar.pack(fill="x")
            tk.Frame(container, bg=C["border"], height=1).pack(fill="x")
            holder = tk.Frame(container, bg=C["page"])
            holder.pack(fill="both", expand=True, pady=(10, 0))
            self.nb = SegTabs(bar, holder)
            self.tab_voice = tk.Frame(holder, bg=C["page"])
            self.tab_anki = tk.Frame(holder, bg=C["page"])
            self.tab_final = tk.Frame(holder, bg=C["page"])
            self.nb.add(self.tab_voice, "Голос")
            self.nb.add(self.tab_anki, "Anki")
            self.nb.add(self.tab_final, "Финализация")
            self._build_tab_voice()
            self._build_tab_anki()
            self._build_tab_final()

        # ------------------------------------------------------ вкладка «Голос»
        def _build_tab_voice(self):
            tab = self.tab_voice
            tab.columnconfigure(1, weight=1)
            tab.rowconfigure(0, weight=1)

            # --- слева: список голосов
            left = card(tab, "Голоса")
            left.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
            self.tree_voices = ttk.Treeview(left.body, columns=("disp", "ok"),
                                            show="headings", height=15,
                                            selectmode="browse")
            self.tree_voices.heading("disp", text="Голос", anchor="w")
            self.tree_voices.heading("ok", text="Файлы", anchor="center")
            self.tree_voices.column("disp", width=140, anchor="w")
            self.tree_voices.column("ok", width=46, anchor="center")
            vsb = ttk.Scrollbar(left.body, orient="vertical",
                                command=self.tree_voices.yview)
            self.tree_voices.configure(yscrollcommand=vsb.set)
            vsb.pack(side="right", fill="y")
            self.tree_voices.pack(fill="both", expand=True)
            self.tree_voices.tag_configure("ok", foreground=C["ok"])
            self.tree_voices.tag_configure("err", foreground=C["err"])
            self.tree_voices.bind("<<TreeviewSelect>>", lambda e: self._select_voice())

            # --- справа: референс + характер речи + действия
            right = tk.Frame(tab, bg=C["page"])
            right.grid(row=0, column=1, sticky="nsew")

            frm_ref = card(right, "Референс (3–10 с)")
            frm_ref.pack(fill="x")
            body = frm_ref.body
            body.columnconfigure(1, weight=1)
            tk.Label(body, text="Файл", font=F_BODY, bg=C["card"], fg=C["text"]
                     ).grid(row=0, column=0, sticky="w", padx=(0, 10))
            self.var_ref = tk.StringVar()
            ent_ref = ttk.Entry(body, textvariable=self.var_ref)
            ent_ref.grid(row=0, column=1, sticky="we")
            self._add_edit_menu(ent_ref)
            ttk.Button(body, text="Обзор…", command=self.browse_ref
                       ).grid(row=0, column=2, padx=(8, 0))
            ttk.Button(body, text="⎘", width=3, command=self.paste_ref_path,
                       ).grid(row=0, column=3, padx=(4, 0))
            ttk.Button(body, text="▶", width=3, command=self.play_ref,
                       style="Accent.TButton").grid(row=0, column=4, padx=(4, 0))

            tk.Label(body, text="Текст\nреференса", font=F_SMALL, bg=C["card"],
                     fg=C["sub"]).grid(row=1, column=0, sticky="nw",
                                       padx=(0, 10), pady=(12, 0))
            self.txt_prompt = scrolledtext.ScrolledText(
                body, height=3, width=48, font=F_BODY, wrap="word",
                bg=C["input"], fg=C["text"], insertbackground=C["text"],
                relief="flat", highlightthickness=1, highlightbackground=C["border"],
                highlightcolor=C["accent"], padx=8, pady=6, spacing1=2, spacing3=2)
            self.txt_prompt.grid(row=1, column=1, columnspan=3, sticky="we",
                                 pady=(12, 0))
            # правая кнопка мыши -> «Вставить» (в tkinter меню по умолчанию нет)
            self._add_edit_menu(self.txt_prompt)

            tk.Label(body, text="Язык", font=F_BODY, bg=C["card"], fg=C["text"]
                     ).grid(row=2, column=0, sticky="w", padx=(0, 10), pady=(12, 0))
            self.var_prompt_lang = tk.StringVar(value="ja")
            ttk.Combobox(body, textvariable=self.var_prompt_lang, values=LANGS,
                         width=8, state="readonly").grid(row=2, column=1,
                                                         sticky="w", pady=(12, 0))
            self.var_noref = tk.BooleanVar(value=False)
            ttk.Checkbutton(body, text="Без текста референса",
                            variable=self.var_noref,
                            command=self._toggle_noref).grid(
                row=2, column=2, columnspan=2, sticky="e", pady=(12, 0))

            tk.Label(body, text="Вспомогательные\n(aux)", font=F_SMALL, bg=C["card"],
                     fg=C["sub"]).grid(row=3, column=0, sticky="nw",
                                       padx=(0, 10), pady=(12, 0))
            aux_wrap = tk.Frame(body, bg=C["card"])
            aux_wrap.grid(row=3, column=1, columnspan=3, sticky="we", pady=(12, 0))
            aux_wrap.columnconfigure(0, weight=1)
            self.lst_aux = tk.Listbox(aux_wrap, height=3, font=F_TINY, bg=C["input"],
                                      fg=C["text"], selectbackground=C["accent"],
                                      selectforeground=C["onaccent"], relief="flat",
                                      highlightthickness=1,
                                      highlightbackground=C["border"],
                                      highlightcolor=C["accent"],
                                      activestyle="none", exportselection=False)
            self.lst_aux.grid(row=0, column=0, sticky="we")
            ttk.Button(aux_wrap, text="+", width=3, command=self.aux_add
                       ).grid(row=0, column=1, padx=(8, 0))
            ttk.Button(aux_wrap, text="−", width=3, command=self.aux_remove
                       ).grid(row=0, column=2, padx=(4, 0))

            # --- характер речи (sampling)
            frm_smp = card(right, "Характер речи — спокойнее ← → живее")
            frm_smp.pack(fill="x", pady=(10, 0))
            smp = frm_smp.body
            smp.columnconfigure(2, weight=1)  # колонка ползунка растягивается
            self.var_temp = tk.DoubleVar(value=DEFAULT_SAMPLING["temperature"])
            self.var_topp = tk.DoubleVar(value=DEFAULT_SAMPLING["top_p"])
            self.var_topk = tk.IntVar(value=DEFAULT_SAMPLING["top_k"])
            self.var_speed = tk.DoubleVar(value=1.0)
            self.var_seed = tk.StringVar(value="42")
            self._slider(smp, 0, "temperature", self.var_temp, 0.0, 1.5,
                         lambda x: "%.2f" % x,
                         "эмоции речи: меньше — ровнее и спокойнее")
            self._slider(smp, 1, "top_p", self.var_topp, 0.0, 1.0,
                         lambda x: "%.2f" % x,
                         "свобода выбора слов: меньше — проще и стабильнее")
            self._slider(smp, 2, "top_k", self.var_topk, 1, 50,
                         lambda x: "%d" % round(x),
                         "варианты чтения: меньше — консервативнее")
            self._slider(smp, 3, "speed", self.var_speed, 0.5, 2.0,
                         lambda x: "%.2f" % x,
                         "скорость речи: 1.00 — обычная")
            tk.Label(smp, text="seed", font=F_BODY, bg=C["card"], fg=C["text"]
                     ).grid(row=4, column=0, sticky="w", padx=(0, 4), pady=2)
            self._hint_label(smp, 4, "seed")
            ttk.Entry(smp, textvariable=self.var_seed, width=8).grid(
                row=4, column=2, sticky="w", padx=6)

            # --- действия и статус
            frm_btn = tk.Frame(right, bg=C["page"])
            frm_btn.pack(fill="x", pady=(10, 0))
            ttk.Button(frm_btn, text="▶  Прослушать тест", style="Accent.TButton",
                       command=self.test_voice).pack(side="left")
            ttk.Button(frm_btn, text="Сохранить", command=self.save_voice
                       ).pack(side="left", padx=8)
            ttk.Button(frm_btn, text="➕ Добавить голос",
                       command=self.add_voice_dialog).pack(side="left")
            ttk.Button(frm_btn, text="Голоса в движке",
                       command=self._scan_voices_async).pack(side="left", padx=8)
            ttk.Button(frm_btn, text="voices.json",
                       command=self.edit_voices).pack(side="right")

            self.var_voice_status = tk.StringVar(value="Выбери голос слева")
            tk.Label(right, textvariable=self.var_voice_status, font=F_SMALL,
                     bg=C["page"], fg=C["sub"], anchor="w").pack(fill="x", pady=(6, 0))

        # серая приписка: что за параметр и в какую сторону его крутить
        HINTS = {
            "seed": "зерно генерации: то же число — тот же результат",
        }

        def _hint_label(self, parent, row, name):
            tk.Label(parent, text=self.HINTS.get(name, ""), foreground=C["sub"],
                     background=C["card"], font=F_TINY, anchor="w").grid(
                row=row, column=1, sticky="w", padx=4)

        def _slider(self, parent, row, text, var, from_, to, show, hint=""):
            tk.Label(parent, text=text, font=F_BODY, bg=C["card"], fg=C["text"]
                     ).grid(row=row, column=0, sticky="w", padx=(0, 4), pady=2)
            if hint:
                tk.Label(parent, text=hint, foreground=C["sub"], background=C["card"],
                         font=F_TINY, anchor="w").grid(
                    row=row, column=1, sticky="w", padx=4)
            lbl = tk.Label(parent, text=show(var.get()), width=6, anchor="e",
                           font=F_BODY, bg=C["card"], fg=C["accent"])
            lbl.grid(row=row, column=3, sticky="e", padx=(2, 0))
            var.trace_add("write", lambda *a, l=lbl, s=show, v=var:
                          l.configure(text=s(float(v.get()))))
            sc = FlatSlider(parent, var, from_, to)
            sc.grid(row=row, column=2, sticky="we", padx=8, pady=2)

        # ------------------------------------------------------- вкладка «Anki»
        def _build_tab_anki(self):
            tab = self.tab_anki

            frm_deck = card(tab, "Колода")
            frm_deck.pack(fill="x")
            body = frm_deck.body
            body.columnconfigure(1, weight=1)
            tk.Label(body, text="Колода", font=F_BODY, bg=C["card"], fg=C["text"]
                     ).grid(row=0, column=0, sticky="w", padx=(0, 10))
            self.var_deck = tk.StringVar()
            self.cmb_deck = ttk.Combobox(body, textvariable=self.var_deck,
                                         state="readonly")
            self.cmb_deck.grid(row=0, column=1, sticky="we")
            self.cmb_deck.bind("<<ComboboxSelected>>", lambda e: self._on_deck_chosen())
            ttk.Button(body, text="↻", width=3,
                       command=self._refresh_decks_async).grid(row=0, column=2,
                                                               padx=(8, 0))
            self.var_note_count = tk.StringVar(value="")
            tk.Label(body, textvariable=self.var_note_count, font=F_SMALL,
                     bg=C["card"], fg=C["sub"]).grid(row=0, column=3, padx=14)

            frm_fld = card(tab, "Поля карточки — откуда брать текст и куда писать звук")
            frm_fld.pack(fill="x", pady=(14, 0))
            body = frm_fld.body
            self.var_sent_src = tk.StringVar()
            self.var_sent_audio = tk.StringVar()
            self.var_word_src = tk.StringVar()
            self.var_word_audio = tk.StringVar()
            self.var_furi_src = tk.StringVar()
            rows = [
                ("Текст предложения ← поле", "sentence_src"),
                ("Звук предложения → поле", "sentence_audio"),
                ("Текст слова ← поле", "word_src"),
                ("Звук слова → поле", "word_audio"),
                # новая схема: основное слово читается строго по этому полю
                ("Фуригана слова ← поле", "furigana_src"),
            ]
            self._field_cbs = {}
            self._field_vars = {
                "sentence_src": self.var_sent_src,
                "sentence_audio": self.var_sent_audio,
                "word_src": self.var_word_src,
                "word_audio": self.var_word_audio,
                "furigana_src": self.var_furi_src,
            }
            for i, (label, attr) in enumerate(rows):
                r, c = divmod(i, 2)
                tk.Label(body, text=label, font=F_SMALL, bg=C["card"], fg=C["sub"]
                         ).grid(row=r, column=c * 2, sticky="w", padx=(0, 8), pady=4)
                cb = ttk.Combobox(body, textvariable=self._field_vars[attr],
                                  state="normal")
                cb.grid(row=r, column=c * 2 + 1, sticky="we",
                        padx=(0, 20 if c == 0 else 0), pady=4)
                self._field_cbs[attr] = cb
            body.columnconfigure(1, weight=1)
            body.columnconfigure(3, weight=1)
            # источник чтения необычного слова: отключено / конкретное поле
            # (поле может содержать простое чтение либо фуриганную разметку)
            self.READ_OFF = "Не подставлять (движок сам)"
            tk.Label(body, text="Источник чтения", font=F_SMALL,
                     bg=C["card"], fg=C["sub"]
                     ).grid(row=3, column=0, sticky="w", padx=(0, 8), pady=4)
            self.var_reading = tk.StringVar(value=self.READ_OFF)
            self.cmb_reading = ttk.Combobox(body, textvariable=self.var_reading,
                                            state="normal")
            self.cmb_reading.grid(row=3, column=1, sticky="we", padx=(0, 20), pady=4)
            self.cmb_reading["values"] = [self.READ_OFF]
            # подсказка: как работает новая схема чтения
            tk.Label(body,
                     text="Основное слово читается строго по полю фуриганы, "
                          "все остальные слова — автоматически.",
                     font=F_TINY, bg=C["card"], fg=C["sub"], anchor="w"
                     ).grid(row=4, column=0, columnspan=4, sticky="we",
                            pady=(6, 0))
            ttk.Button(body, text="Подставить поля выбранной колоды",
                       command=self._autofill_fields).grid(
                row=5, column=0, columnspan=4, sticky="w", pady=(8, 0))

            frm_par = card(tab, "Что озвучить")
            frm_par.pack(fill="x", pady=(14, 0))
            body = frm_par.body
            tk.Label(body, text="Режим", font=F_BODY, bg=C["card"], fg=C["text"]
                     ).pack(side="left", padx=(0, 8))
            self.var_mode = tk.StringVar(value="both")
            for val, label in (("both", "слово + предложение"),
                               ("sentence", "предложение"),
                               ("expression", "слово")):
                ttk.Radiobutton(body, text=label, value=val,
                                variable=self.var_mode).pack(side="left", padx=6)
            tk.Label(body, text="Лимит", font=F_SMALL, bg=C["card"], fg=C["sub"]
                     ).pack(side="left", padx=(22, 8))
            self.var_limit = tk.StringVar(value="0")
            ttk.Entry(body, textvariable=self.var_limit, width=6).pack(side="left")
            tk.Label(body, text="0 = все", font=F_TINY, bg=C["card"], fg=C["sub"]
                     ).pack(side="left", padx=(8, 20))
            self.var_force = tk.BooleanVar(value=False)
            ttk.Checkbutton(body, text="переозвучить всё заново",
                            variable=self.var_force).pack(side="left")

            self.var_anki_tab_status = tk.StringVar(value="")
            tk.Label(tab, textvariable=self.var_anki_tab_status, font=F_SMALL,
                     bg=C["page"], fg=C["sub"], anchor="w").pack(fill="x", pady=(12, 0))

        # --------------------------------------------------- вкладка «Финализация»
        def _build_tab_final(self):
            tab = self.tab_final

            frm_act = tk.Frame(tab, bg=C["page"])
            frm_act.pack(fill="x")
            self.btn_start = ttk.Button(frm_act, text="▶  Начать озвучку",
                                        style="Accent.TButton",
                                        command=self.start_voice)
            self.btn_start.pack(side="left")
            self.btn_stop = ttk.Button(frm_act, text="■  Остановить", state="disabled",
                                       style="Danger.TButton",
                                       command=self.stop_proc)
            self.btn_stop.pack(side="left", padx=10)
            ttk.Button(frm_act, text="Проверить колоду",
                       command=self.check_deck).pack(side="left", padx=6)
            ttk.Button(frm_act, text="Самопроверка",
                       command=self.run_selftest).pack(side="left", padx=6)

            frm_log = card(tab, "Ход работы")
            frm_log.pack(fill="both", expand=True, pady=(14, 0))
            self.log = scrolledtext.ScrolledText(
                frm_log.body, state="disabled", height=18, font=F_MONO,
                bg=C["console"], fg=C["console_fg"], insertbackground=C["console_fg"],
                relief="flat", highlightthickness=1, highlightbackground=C["border"],
                padx=12, pady=10, spacing1=1, spacing3=1,
                selectbackground=C["accent"], selectforeground=C["onaccent"])
            self.log.pack(fill="both", expand=True)

        # ------------------------------------------------------------- лог
        def log_line(self, line, tag=None):
            if tag is None:
                s = line.lstrip()
                if s.startswith("»"):
                    tag = "cmd"
                elif s.startswith(("✓", "OK", "Готово:", "Склонировано", "Сохранено")):
                    tag = "ok"
                elif s.startswith(("✗", "!!", "FAIL", "ПРОБЛЕМА", "Ошибка", "Не ")):
                    tag = "err"
            self.log.configure(state="normal")
            self.log.insert("end", line + "\n", tag or "")
            self.log.see("end")
            self.log.configure(state="disabled")

        def log_clear(self):
            self.log.configure(state="normal")
            self.log.delete("1.0", "end")
            self.log.configure(state="disabled")

        # ------------------------------------------------------- путь и голоса
        def _load_initial_path(self):
            cfg = load_config()
            path = cfg.get("gptsovits_path", "")
            if path and not validate_gptsovits(path):
                path = ""
            if not path:
                auto = find_gptsovits_automatic()
                if auto:
                    path = auto
                    self.log_line("Папка GPT-SoVITS найдена автоматически: %s" % path)
                else:
                    self.log_line("Укажи папку GPT-SoVITS кнопкой «Обзор…».")
            if path:
                self.var_path.set(path)
                self._apply_path()

        def browse_path(self):
            start = self.var_path.get() or "D:\\"
            chosen = filedialog.askdirectory(title="Папка GPT-SoVITS", initialdir=start)
            if chosen:
                self.var_path.set(chosen)
                self._apply_path()

        def check_path(self):
            self._apply_path()

        def _apply_path(self):
            path = self.var_path.get().strip()
            problems = validate_gptsovits(path)
            if problems:
                for p in problems:
                    self.log_line("ПРОБЛЕМА: " + p, "err")
                self.var_status.set("Папка GPT-SoVITS не подходит")
                return
            cfg = load_config()
            cfg["gptsovits_path"] = path
            save_config(cfg)
            # единый источник для pipeline.bat и voice_pipeline.py
            try:
                with open(os.path.join(code_dir(), "gptsovits_path.txt"),
                          "w", encoding="utf-8") as f:
                    f.write(path + "\n")
            except OSError:
                pass
            self.log_line("Папка GPT-SoVITS принята: %s" % path)
            self._load_voices()
            self._refresh_decks_async()

        # ---- голоса: дерево + редактор
        def _resolve(self, p):
            if not p:
                return ""
            p = os.path.expanduser(p)
            if os.path.isabs(p):
                return p
            return os.path.normpath(os.path.join(self.var_path.get().strip(), p))

        def _store_path(self, p):
            if not p:
                return ""
            p = os.path.expanduser(p)
            eng = self.var_path.get().strip()
            try:
                if eng and os.path.commonpath(
                        [os.path.abspath(p), os.path.abspath(eng)]) == os.path.abspath(eng):
                    return os.path.relpath(p, eng)
            except Exception:
                pass
            return p

        def _read_voices_file(self):
            p = os.path.join(code_dir(), "voices.json")
            try:
                with open(p, encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {"voices": {}}

        def _write_voices_file(self, cfg):
            p = os.path.join(code_dir(), "voices.json")
            with open(p, "w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)

        def _files_ok(self, v):
            for key in ("gpt", "sovits", "ref"):
                p = v.get(key, "")
                if not p or not os.path.exists(self._resolve(p)):
                    return False
            return True

        def _refresh_voice_tree(self, keep_selection=True):
            prev = self.current_voice
            self.tree_voices.delete(*self.tree_voices.get_children())
            for name in sorted(self.voices):
                v = self.voices[name]
                disp = v.get("display") or name
                ok = "✓" if self._files_ok(v) else "✗"
                self.tree_voices.insert("", "end", iid=name, values=(disp, ok),
                                        tags=("ok" if ok == "✓" else "err",))
            if keep_selection and prev in self.voices:
                self.tree_voices.selection_set(prev)
                self.tree_voices.focus(prev)

        def _load_voices(self):
            self.voices, self.default_voice = load_voices()
            self._refresh_voice_tree(keep_selection=False)
            self.var_info.set("Голосов: %d" % len(self.voices))
            names = sorted(self.voices)
            if names:
                sel = self.default_voice if self.default_voice in names else names[0]
                self.tree_voices.selection_set(sel)
                self.tree_voices.focus(sel)
                self._select_voice()
            if not names:
                self.var_voice_status.set("В voices.json нет голосов — добавь кнопкой «Добавить голос».")

        def _scan_voices_async(self, silent=False):
            """Ищет пары весов (GPT .ckpt + SoVITS .pth) в папке движка и
            дописывает новые голоса в voices.json (scan --apply)."""
            path = self.var_path.get().strip()
            problems = validate_gptsovits(path)
            out("[scan] старт: silent=%s problems=%r" % (silent, problems))
            if problems:
                if not silent:
                    messagebox.showerror(
                        APP_NAME, "Сначала укажи рабочую папку GPT-SoVITS.")
                return
            if not silent:
                self.var_status.set("Ищу голоса в папке движка…")
            lines = []

            def on_line(line):
                lines.append(line)
                out("[scan] >> " + line)

            def on_done(code):
                txt = "\n".join(lines)[-4000:]
                m = re.search(r"\{.*\}", txt, re.S)
                data = None
                try:
                    data = json.loads(m.group(0)) if m else None
                except Exception as e:
                    out("[scan] JSON не разобран: %r" % (e,))
                out("[scan] exit=%s data=%r" % (code, data))

                def done():
                    added = (data or {}).get("added") or []
                    if added:
                        self._load_voices()
                        self.var_status.set(
                            "Найдено новых голосов: %d (%s)"
                            % (len(added), ", ".join(added)))
                    elif not silent:
                        self.var_status.set(
                            "Новых голосов не найдено — всё уже учтено")
                try:
                    self.after(0, done)
                except Exception as e:
                    out("[after из потока не удался: %r]; выполняю напрямую" % (e,))
                    done()
            pipeline_cmd(path, ["scan", "--apply", "--json"],
                         on_line=on_line, on_done=on_done)

        def _select_voice(self, *a):
            sel = self.tree_voices.selection()
            if not sel:
                return
            name = sel[0]
            self.current_voice = name
            v = self.voices.get(name, {})
            self.var_ref.set(self._resolve(v.get("ref", "")))
            self._set_prompt_text(v.get("prompt_text", ""))
            self.var_prompt_lang.set(v.get("prompt_lang", "ja"))
            self._aux_list = [self._resolve(a) for a in (v.get("aux") or [])]
            self._refresh_aux_list()
            self.var_temp.set(float(v.get("temperature", DEFAULT_SAMPLING["temperature"])))
            self.var_topp.set(float(v.get("top_p", DEFAULT_SAMPLING["top_p"])))
            self.var_topk.set(int(v.get("top_k", DEFAULT_SAMPLING["top_k"])))
            self.var_speed.set(float(v.get("speed", 1.0)))
            self.var_seed.set(str(v.get("seed", 42)))
            # Пустой текст НЕ блокирует поле: раньше это ставило галку
            # «Без текста референса» и переводило поле в disabled —
            # в заблокированное поле невозможно было вставить текст.
            # Незаполненное поле сохраняется как "" (тот же результат,
            # что и при включённой галке), поэтому просто оставляем ввод.
            self.var_noref.set(False)
            self._toggle_noref()
            self.var_voice_status.set("Голос: %s" % (v.get("display") or name))

        def _set_prompt_text(self, t):
            self.txt_prompt.configure(state="normal")
            self.txt_prompt.delete("1.0", "end")
            self.txt_prompt.insert("1.0", t or "")

        def _get_prompt_text(self):
            return self.txt_prompt.get("1.0", "end-1c")

        def _toggle_noref(self):
            if self.var_noref.get():
                self.txt_prompt.configure(state="disabled")
            else:
                self.txt_prompt.configure(state="normal")

        def _add_edit_menu(self, w):
            """Правая кнопка мыши: Вырезать/Копировать/Вставить/Выделить всё.

            В tkinter контекстного меню по умолчанию нет — без этого вставка
            правой кнопкой невозможна.  Работает и для Text, и для Entry.
            """
            is_text = isinstance(w, (tk.Text, scrolledtext.ScrolledText))
            m = tk.Menu(w, tearoff=0, bg=C["input"], fg=C["text"],
                        activebackground=C["accent"], activeforeground=C["text"],
                        font=F_BODY, borderwidth=0)

            def state_ok():
                # в заблокированном поле команды неактивны
                try:
                    return str(w.cget("state")) != "disabled"
                except Exception:
                    return True

            def cut():
                if not state_ok():
                    return
                if is_text:
                    w.event_generate("<<Cut>>")
                else:
                    try:
                        sel = w.selection_get()
                        w.delete("sel.first", "sel.last")
                        w.insert("insert", "")
                        w.icursor("insert")
                    except Exception:
                        pass

            def copy():
                try:
                    if is_text:
                        w.event_generate("<<Copy>>")
                    else:
                        sel = w.selection_get()
                        w.clipboard_clear()
                        w.clipboard_append(sel)
                except Exception:
                    pass

            def paste():
                if not state_ok():
                    return
                try:
                    if is_text:
                        w.event_generate("<<Paste>>")
                    else:
                        t = w.clipboard_get()
                        try:
                            w.delete("sel.first", "sel.last")
                        except Exception:
                            pass
                        w.insert("insert", t)
                except Exception:
                    pass

            def select_all():
                try:
                    if is_text:
                        w.tag_add("sel", "1.0", "end-1c")
                    else:
                        w.selection_range(0, "end")
                except Exception:
                    pass

            def clear():
                if not state_ok():
                    return
                if is_text:
                    w.delete("1.0", "end")
                else:
                    w.delete(0, "end")

            m.add_command(label="Вырезать    Ctrl+X", command=cut)
            m.add_command(label="Копировать  Ctrl+C", command=copy)
            m.add_command(label="Вставить    Ctrl+V", command=paste)
            m.add_separator()
            m.add_command(label="Выделить всё  Ctrl+A", command=select_all)
            m.add_command(label="Очистить", command=clear)

            def show(e):
                # снять выделение не надо — просто показать меню
                m.tk_popup(e.x_root, e.y_root)
                return "break"

            w.bind("<Button-3>", show)
            w.bind("<Control-a>", lambda e: (select_all(), "break"))
            return m

        def paste_ref_path(self):
            """Кнопка «Вставить»: подставить путь референса из буфера обмена."""
            try:
                t = (self.clipboard_get() or "").strip().strip('"')
            except Exception:
                t = ""
            if not t:
                messagebox.showinfo(APP_NAME, "Буфер обмена пуст.\n"
                                    "Скопируй путь к файлу в проводнике (Ctrl+C).")
                return
            self.var_ref.set(t)

        def _refresh_aux_list(self):
            self.lst_aux.delete(0, "end")
            for a in self._aux_list:
                self.lst_aux.insert("end", a)

        def browse_ref(self):
            start = self._resolve(self.var_ref.get()) or self.var_path.get() or "D:\\"
            f = filedialog.askopenfilename(
                title="Референс (3–10 с)",
                initialdir=os.path.dirname(start) if start else "D:\\",
                filetypes=[("Audio", "*.wav *.mp3 *.flac *.ogg"), ("All", "*.*")])
            if f:
                self.var_ref.set(f)

        def play_ref(self):
            p = self._resolve(self.var_ref.get())
            if p and os.path.exists(p):
                os.startfile(p)
            else:
                messagebox.showerror(APP_NAME, "Файл референса не найден:\n%s" % p)

        def aux_add(self):
            f = filedialog.askopenfilename(
                title="Вспомогательный референс",
                filetypes=[("Audio", "*.wav *.mp3 *.flac *.ogg"), ("All", "*.*")])
            if f:
                self._aux_list.append(f)
                self._refresh_aux_list()

        def aux_remove(self):
            sel = self.lst_aux.curselection()
            if sel:
                del self._aux_list[sel[0]]
                self._refresh_aux_list()

        def save_voice(self):
            name = self.current_voice
            if not name:
                messagebox.showerror(APP_NAME, "Выбери голос слева.")
                return False
            cfg = self._read_voices_file()
            v = dict(cfg.get("voices", {}).get(name, {}))
            v["ref"] = self._store_path(self.var_ref.get().strip())
            v["prompt_text"] = "" if self.var_noref.get() else self._get_prompt_text()
            v["prompt_lang"] = self.var_prompt_lang.get().strip() or "ja"
            v["aux"] = [self._store_path(a) for a in self._aux_list]
            v["temperature"] = round(float(self.var_temp.get()), 2)
            v["top_p"] = round(float(self.var_topp.get()), 2)
            v["top_k"] = int(round(self.var_topk.get()))
            v["speed"] = round(float(self.var_speed.get()), 2)
            try:
                v["seed"] = int(self.var_seed.get())
            except ValueError:
                v["seed"] = 42
            cfg.setdefault("voices", {})[name] = v
            self._write_voices_file(cfg)
            self.voices[name] = v
            self._refresh_voice_tree()
            self.var_voice_status.set("Сохранено: %s" % name)
            return True

        def _run_pipeline(self, args, title, on_done_extra=None, switch=True):
            path = self.var_path.get().strip()
            self.log_clear()
            self.log_line("» " + " ".join(args))
            self.var_status.set(title)
            if switch:
                self.nb.select(self.tab_final)
            self.btn_start.configure(state="disabled")
            self.btn_stop.configure(state="normal")

            def on_line(line):
                self.after(0, lambda: self.log_line(line))

            def on_done(code):
                self.after(0, lambda: self._proc_done(code, title))
                if on_done_extra and code == 0:
                    self.after(0, on_done_extra)

            self.run = pipeline_cmd(path, args, on_line, on_done)

        def _proc_done(self, code, title):
            self.btn_start.configure(state="normal")
            self.btn_stop.configure(state="disabled")
            self.var_status.set(("%s — завершено (код %s)" % (title, code))
                                if code == 0 else ("%s — ошибки (код %s)" % (title, code)))
            if code == 0:
                self.log_line("✓ Готово.")
            else:
                self.log_line("✗ Завершено с ошибкой (код %s)." % code, "err")

        def _busy(self):
            if self.btn_start["state"] == "disabled":
                messagebox.showinfo(APP_NAME, "Дождись завершения текущей операции.")
                return True
            return False

        # ---------------------------------------------------- поля (вкладка Anki)
        def _on_deck_chosen(self, *a):
            deck = self._selected_deck()
            if not deck:
                return
            for name, n in self.decks:
                if name == deck:
                    self.var_note_count.set("Заметок: %s" % ("?" if n < 0 else n))
                    break
            self.var_anki_tab_status.set("Читаю поля колоды «%s»…" % deck)
            threading.Thread(target=self._fetch_fields_worker,
                             args=(deck,), daemon=True).start()

        def _fetch_fields_worker(self, deck):
            fl = list_note_fields(deck)
            self.after(0, lambda: self._set_fields(fl, deck))

        def _set_fields(self, fl, deck):
            if not fl:
                cnt = next((n for nm, n in self.decks if nm == deck), -1)
                if cnt == 0:
                    msg = "Колода «%s» пуста — брать поля неоткуда." % deck
                else:
                    msg = "Не удалось прочитать поля колоды «%s» (Anki закрыта?)." % deck
                self.var_anki_tab_status.set(msg)
                return
            guess = self._guess_fields(fl)
            for attr, cb in self._field_cbs.items():
                cb["values"] = fl
            # в списке источников чтения — ещё и поля самой колоды
            self.cmb_reading["values"] = [self.READ_OFF] + list(fl)
            self.var_sent_src.set(guess["sentence_src"])
            self.var_sent_audio.set(guess["sentence_audio"])
            self.var_word_src.set(guess["word_src"])
            self.var_word_audio.set(guess["word_audio"])
            self.var_furi_src.set(guess.get("furigana_src", ""))
            self.fields = guess
            furi = guess.get("furigana_src", "")
            self.var_anki_tab_status.set(
                "Поля колоды «%s»: %d. Фуригана: %s. Проверь и поправь при необходимости."
                % (deck, len(fl), furi or "нет (слово прочитается автоматически)"))

        def _autofill_fields(self):
            deck = self._selected_deck()
            if not deck:
                messagebox.showerror(APP_NAME, "Сначала выбери колоду.")
                return
            self._on_deck_chosen()

        def _guess_fields(self, fl):
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
            # поле фуриганы основного слова (новая схема чтения)
            furi = find(lambda l: l == "expressionfurigana"
                        or ("furigana" in l and "sentence" not in l)
                        or ("reading" in l and "expression" in l), "")
            return {"sentence_src": sent_src, "sentence_audio": sent_aud,
                    "word_src": word_src, "word_audio": word_aud,
                    "furigana_src": furi}

        def _current_fields(self):
            return {
                "sentence_src": self.var_sent_src.get().strip(),
                "sentence_audio": self.var_sent_audio.get().strip(),
                "word_src": self.var_word_src.get().strip(),
                "word_audio": self.var_word_audio.get().strip(),
                "furigana_src": self.var_furi_src.get().strip(),
            }

        def _reading_value(self):
            """GUI-значение источника чтения -> аргумент --reading пайплайна."""
            v = self.var_reading.get().strip()
            if not v or v == self.READ_OFF:
                return "off"
            return v            # пользователь ввёл/выбрал имя поля с чтением

        # ------------------------------------------------------------- статус
        def _poll_status(self):
            def worker():
                a = anki_status()
                t = tts_status()
                self.after(0, lambda: self._set_status(a, t))
            threading.Thread(target=worker, daemon=True).start()
            self.after(5000, self._poll_status)

        def _set_status(self, anki_ok, tts_ok):
            self.var_anki.set("Anki: " + ("подключена" if anki_ok else "НЕ подключена"))
            self.var_tts.set("Сервер: " + ("запущен" if tts_ok else "не запущен (поднимется сам)"))
            self.chip_anki.set_ok(anki_ok)
            self.chip_tts.set_ok(tts_ok)

        # ------------------------------------------------------------ колоды
        def _refresh_decks_async(self):
            if not anki_status():
                self.cmb_deck["values"] = []
                self.var_status.set("Anki не подключена — открой Anki")
                return
            self.var_status.set("Читаю колоды из Anki…")

            def worker():
                err = None
                try:
                    decks = list_decks()
                except Exception as e:
                    decks = None
                    err = e
                self.after(0, lambda: self._set_decks(decks, err))
            threading.Thread(target=worker, daemon=True).start()

        def _set_decks(self, decks, err):
            if decks is None:
                self.var_status.set("Не удалось прочитать колоды: %s" % err)
                return
            self.decks = decks
            values = ["%s  (%d)" % (n, c if c >= 0 else "?") for n, c in decks]
            self.cmb_deck["values"] = values
            # если пользователь уже выбрал колоду — не сбрасываем его выбор
            if self._selected_deck():
                self.var_status.set("Колод в Anki: %d" % len(decks))
                return
            if values:
                # по умолчанию — первая колода с заметками, а не пустой Default
                idx = next((i for i, (nm, n) in enumerate(self.decks) if n > 0), 0)
                self.var_deck.set(values[idx])
                self._on_deck_chosen()
            self.var_status.set("Колод в Anki: %d" % len(decks))

        def _selected_deck(self):
            raw = self.var_deck.get()
            return raw.rsplit("  (", 1)[0].strip() if raw else ""

        def _selected_voice(self):
            return self.current_voice

        # --------------------------------------------------------- действия
        def start_voice(self):
            if self._busy():
                return
            path = self.var_path.get().strip().strip('"').strip()
            if path:
                self.var_path.set(path)      # кавычки/пробелы из буфера не мешают
            problems = validate_gptsovits(path)
            if problems:
                # говорим ЧТО не так, а не просто «проверь папку»
                auto = find_gptsovits_automatic()
                msg = "Папка GPT-SoVITS не подходит:\n\n" + \
                      "\n".join("  • " + p for p in problems)
                if auto and os.path.normcase(auto) != os.path.normcase(path):
                    msg += ("\n\nНо папка найдена автоматически:\n  %s\n\n"
                            "Нажми «Да», чтобы подставить её." % auto)
                    if messagebox.askyesno(APP_NAME, msg):
                        self.var_path.set(auto)
                        self._apply_path()
                        path = auto
                    else:
                        return
                else:
                    msg += "\n\nУкажи её кнопкой «Обзор…» рядом с полем."
                    messagebox.showerror(APP_NAME, msg)
                    return
            else:
                auto = None
            voice = self._selected_voice()
            if not voice:
                messagebox.showerror(APP_NAME, "Выбери голос (вкладка «Голос»).")
                return
            deck = self._selected_deck()
            if not deck:
                messagebox.showerror(APP_NAME, "Выбери колоду (вкладка «Anki»).")
                return
            if not self.save_voice():
                return
            f = self._current_fields()
            args = ["voice", "--voice", voice, "--deck", deck,
                    "--mode", self.var_mode.get(),
                    "--sentence-src", f["sentence_src"], "--sentence-audio", f["sentence_audio"],
                    "--word-src", f["word_src"], "--word-audio", f["word_audio"]]
            if f["furigana_src"]:
                args += ["--furigana-src", f["furigana_src"]]
            reading = self._reading_value()
            if reading:
                args += ["--reading", reading]
            try:
                limit = int(self.var_limit.get() or 0)
            except ValueError:
                limit = 0
            if limit > 0:
                args += ["--limit", str(limit)]
            if self.var_force.get():
                args.append("--force")
            self._run_pipeline(args, "Озвучка колоды «%s»" % deck)

        def stop_proc(self):
            run = getattr(self, "run", None)
            if run and run.stop():
                self.log_line("⏹ Процесс остановлен.")
                self.var_status.set("Остановлено вручную")
                self.btn_start.configure(state="normal")
                self.btn_stop.configure(state="disabled")
            else:
                self.log_line("Нечего останавливать — процесс уже завершён.")

        def check_deck(self):
            if self._busy():
                return
            if not self.var_path.get().strip():
                return
            deck = self._selected_deck()
            if not deck:
                messagebox.showerror(APP_NAME, "Выбери колоду (вкладка «Anki»).")
                return
            f = self._current_fields()
            self._run_pipeline(["check", "--deck", deck,
                                "--sentence-audio", f["sentence_audio"],
                                "--word-audio", f["word_audio"]],
                               "Проверка колоды «%s»" % deck)

        def test_voice(self):
            if self._busy():
                return
            if not self.var_path.get().strip():
                return
            voice = self._selected_voice()
            if not voice:
                messagebox.showerror(APP_NAME, "Выбери голос (вкладка «Голос»).")
                return
            if not self.save_voice():
                return
            seed = self.var_seed.get().strip() or "42"
            args = ["test", "--voice", voice, "--text", "こんにちは、テストです。",
                    "--speed", "%.2f" % float(self.var_speed.get()), "--seed", seed]
            self._run_pipeline(args, "Тест синтеза «%s»" % voice,
                               on_done_extra=lambda v=voice: self._play_test(v))

        def _play_test(self, voice):
            for ext in ("ogg", "wav"):
                p = os.path.join(code_dir(), "test_%s.%s" % (voice, ext))
                if os.path.exists(p):
                    try:
                        os.startfile(p)
                    except Exception as e:
                        self.log_line("Не удалось проиграть %s: %r" % (p, e), "err")
                    return
            self.log_line("Файл теста не найден.", "err")

        def run_selftest(self):
            if self._busy():
                return
            if not self.var_path.get().strip():
                return
            self._run_pipeline(["selftest"], "Самопроверка пайплайна")

        # ----------------------------------------------------- добавление голоса
        def add_voice_dialog(self):
            dlg = tk.Toplevel(self)
            dlg.title("Добавить голос")
            dlg.geometry("520x300")
            dlg.configure(bg=C["page"])
            dlg.transient(self)
            dlg.grab_set()
            entries = {}
            fields = [("name (латиницей)", "name"), ("как показывать", "display"),
                      ("GPT .ckpt", "gpt"), ("SoVITS .pth", "sovits"),
                      ("референс 3–10 с", "ref"), ("текст референса", "prompt_text")]
            for i, (label, key) in enumerate(fields):
                ttk.Label(dlg, text=label).grid(row=i, column=0, sticky="w", padx=8, pady=3)
                e = ttk.Entry(dlg, width=52)
                e.grid(row=i, column=1, sticky="we", padx=8, pady=3)
                entries[key] = e
            dlg.columnconfigure(1, weight=1)

            def browse(key):
                f = filedialog.askopenfilename(parent=dlg, filetypes=[("All", "*.*")])
                if f:
                    entries[key].delete(0, "end")
                    entries[key].insert(0, f)

            for key, lbl in (("gpt", "…"), ("sovits", "…"), ("ref", "…")):
                r = [k for _, k in fields].index(key)
                ttk.Button(dlg, text=lbl, width=3,
                           command=lambda k=key: browse(k)).grid(row=r, column=2, padx=(0, 8))

            def ok():
                vals = {k: e.get().strip() for k, e in entries.items()}
                for req in ("name", "gpt", "sovits", "ref", "prompt_text"):
                    if not vals[req]:
                        messagebox.showerror(APP_NAME, "Заполни обязательные поля.", parent=dlg)
                        return
                path = self.var_path.get().strip()
                args = ["add", "--name", vals["name"], "--display", vals["display"] or vals["name"],
                        "--gpt", vals["gpt"], "--sovits", vals["sovits"],
                        "--ref", vals["ref"], "--prompt-text", vals["prompt_text"],
                        "--prompt-lang", "ja", "--force"]
                self.log_line("» " + " ".join(args))
                self.nb.select(self.tab_final)
                pipeline_cmd(path, args, on_line=lambda l: self.after(0, lambda: self.log_line(l)),
                             on_done=lambda c: self.after(0, self._load_voices))
                dlg.destroy()

            ttk.Button(dlg, text="Добавить", command=ok).grid(row=len(fields), column=1,
                                                              sticky="e", padx=8, pady=10)

        def edit_voices(self):
            f = os.path.join(code_dir(), "voices.json")
            if os.path.exists(f):
                os.startfile(f)
            else:
                messagebox.showerror(APP_NAME, "Файл не найден:\n%s" % f)

        def on_close(self):
            self.destroy()

    app = App(open_tab)
    app.log.tag_configure("err", foreground="#FF8A80")
    app.log.tag_configure("ok", foreground="#7AE2A8")
    app.log.tag_configure("cmd", foreground="#8AB4F8")
    app.mainloop()


# ==================================================================== точка входа
def main():
    ap = argparse.ArgumentParser(description=APP_NAME)
    ap.add_argument("--tab", default=None, choices=["voice", "anki", "final"],
                    help="открыть окно сразу на указанной вкладке (только --classic)")
    ap.add_argument("--classic", action="store_true",
                    help="старое tkinter-окно вместо веб-интерфейса")
    ap.add_argument("--no-open", action="store_true",
                    help="веб: не открывать браузер автоматически")
    ap.add_argument("--port", type=int, default=0,
                    help="веб: порт (0 — свободный автоматически)")
    sub = ap.add_subparsers(dest="cmd")
    d = sub.add_parser("doctor", help="диагностика без интерфейса")
    d.add_argument("--path", default=None, help="папка GPT-SoVITS")
    d.add_argument("--json", action="store_true")
    args = ap.parse_args()
    if args.cmd == "doctor":
        sys.exit(doctor(args.path, args.json))
    if args.classic:
        run_gui(args.tab)
        return
    # основной режим — локальный веб-интерфейс (anki_web)
    # sys.path явно: pyruntime собран с safe_path=True и папку скрипта
    # в путь импорта сама не добавляет
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import anki_web
    sys.exit(anki_web.serve(open_browser=not args.no_open, port=args.port))


if __name__ == "__main__":
    # глобальный перехватчик: в windowed-сборке traceback уходит только в файл
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        msg = traceback.format_exc()
        try:
            with open(CRASH_LOG, "a", encoding="utf-8") as f:
                f.write(msg + "\n")
        except Exception:
            pass
        out(msg)
        raise


