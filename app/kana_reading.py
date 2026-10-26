# -*- coding: utf-8 -*-
"""Чтение японского текста: иероглифы -> кана.

Главный вход — kanaize(): NFKC -> латиница катаканой -> g2p только для
кусков с иероглифами -> хирагана. Основной движок — Haqumei (помощник
g2p_core.py в pyruntime, при его отсутствии in-process), запасные ходы —
SudachiPy и pyopenjtalk. Здесь же разбор фуриганной разметки и подстановка
чтения из карточки: _parse_furigana, furiga_pair, inject_reading*,
replace_term (границы слова), kanaize_card.
"""
import json
import os
import re
import subprocess
import sys
import unicodedata
import zipfile

import av_state
import oscompat
from anki_api import plain
from fields_config import DEFAULT_FIELDS
from paths import CODE, ROOT, bundled

try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

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


try:
    import en_translit
    _translit_en_local = en_translit.transliterate_en
except Exception:
    en_translit = None
    _translit_en_local = None


def latin2kana(s):
    """Транслитерация латиницы: гибрид e2k + словарь аббревиатур + fallback."""
    if not s or not re.search(r"[A-Za-z0-9]", s):
        return s
    # 1. Локальный запуск (если e2k доступен прямо в текущем Python 3.10+)
    if en_translit is not None and getattr(en_translit, "has_e2k", lambda: False)():
        try:
            return _translit_en_local(s)
        except Exception:
            pass
    # 2. Через фоновый процесс pyruntime (Python 3.9 в рантайме GPT-SoVITS -> Python 3.13 с e2k)
    try:
        c = core_client()
        if c and hasattr(c, "translit"):
            res = c.translit(s)
            if res:
                return res
    except Exception:
        pass
    # 3. Локальный transliterate_en (хотя бы по словарю ACRONYMS / дефисам) или fallback
    if _translit_en_local is not None:
        try:
            return _translit_en_local(s)
        except Exception:
            pass
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
# Причина: MeCab читает хирагану как частицу (こんにちは -> コンニチワ,
# こんばんは -> コンバンワ), а катакану читает верно. Финальный kata2hira
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
PYRUNTIME_DIR = os.path.join(ROOT, "pyruntime")
PYRUNTIME_PY = oscompat.pyruntime_python(ROOT)
SUDACHI_HELPER = os.path.join(CODE, "sudachi_g2p.py")
PYRUNTIME_ZIP = bundled("pyruntime.zip")

_SUDACHI_PROC = None      # None — ещё не пробовали, False — недоступно
_sudachi_warned = False


def _ensure_pyruntime():
    """Развернуть встроенный Python из pyruntime.zip, если его ещё нет."""
    if os.path.isfile(PYRUNTIME_PY):
        return True
    if not oscompat.IS_WIN:
        # pyruntime.zip — Windows-сборка (python.exe). На Linux pyruntime —
        # обычный venv, его создаёт install.sh; если его нет, чтение делает
        # in-process Haqumei (см. _core_local) или запасная цепочка
        return False
    if not os.path.isfile(PYRUNTIME_ZIP):
        return False
    print("-- Собираю встроенный разбор текста (pyruntime, один раз)...")
    with zipfile.ZipFile(PYRUNTIME_ZIP) as zf:
        # архив содержит верхний каталог pyruntime/, поэтому распаковываем в
        # ROOT: python.exe окажется ровно в PYRUNTIME_DIR, где его ждут
        # sudachi_g2p/g2p_core и pipeline_cmd (extractall(CODE) клал его в
        # app\pyruntime — на свежей установке помощники не запускались вовсе)
        zf.extractall(ROOT)
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
            if oscompat.IS_WIN:
                print("   Проверь, что рядом со скриптом лежат pyruntime.zip "
                      "и sudachidict.zip.")
            else:
                print("   Нет %s — запусти install.sh ещё раз." % PYRUNTIME_PY)
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

    def translit(self, text):
        """Транслитерация английских слов в катакану (e2k) через встроенный Python."""
        for _ in range(2):
            if self.proc is None and not self.start():
                return None
            try:
                req = (json.dumps({"id": 1, "action": "translit", "text": text},
                                  ensure_ascii=False) + "\n").encode("utf-8")
                self.proc.stdin.write(req)
                self.proc.stdin.flush()
                line = self.proc.stdout.readline()
                if not line:
                    self.proc = None
                    continue
                msg = json.loads(line.decode("utf-8"))
                return msg.get("result")
            except Exception:
                self.proc = None
        return None

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


_CORE_LOCAL = None        # None — ещё не пробовали, False — недоступен


class _CoreLocal(object):
    """Тот же протокол reads()/translit(), но Haqumei работает В ЭТОМ
    интерпретаторе (g2p_core.reads).

    Сюда попадаем, только если haqumei уже импортируется в текущем питоне
    (CI, собранный exe, dev-venv): в питон движка сами его не ставим — там
    чужой numpy, который нельзя подменять. Долгоживущий процесс pyruntime
    при этом остаётся первым ходом на Windows.
    """

    def __init__(self, mod, version):
        self._mod = mod
        self.version = version

    def translit(self, text):
        try:
            from en_translit import transliterate_en
            return transliterate_en(text)
        except Exception:
            return text

    def reads(self, text):
        try:
            return [list(w) for w in self._mod.reads(text)]
        except Exception:
            return None


def _core_local():
    """In-process ядро (Haqumei из текущего интерпретатора) или None."""
    global _CORE_LOCAL
    if _CORE_LOCAL is None:
        try:
            import g2p_core as _gc
            from importlib.metadata import version as _pkgver
            ver = _pkgver("haqumei")
            if not _gc.reads("試し"):        # прогрев: модель обязана работать
                raise RuntimeError("haqumei вернул пустую разметку")
            _CORE_LOCAL = _CoreLocal(_gc, ver)
        except Exception:
            _CORE_LOCAL = False
    return _CORE_LOCAL or None


def core_client():
    """Помощник-ядро (Haqumei): pyruntime-процесс, иначе in-process, иначе None."""
    global _CORE_PROC, _core_warned
    if _CORE_PROC is None:
        proc = _CoreProc()
        _CORE_PROC = proc if proc.start() else False
    if _CORE_PROC is False:
        local = _core_local()
        if local is not None:
            return local
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
                  % (av_state.PYTHON or oscompat.engine_python_label()))
            _g2p_warned = True
        return text


_KATA_ONLY = re.compile(r"^[\u30a0-\u30ff]+$")


def _span_drift(surface, word):
    """Спаны помощника съехали относительно текста — разметке верить нельзя.

    Случай: в числе с разделителями («1,280») нормальная форма короче
    поверхности, и хвостовые токены получают ЧУЖИЕ поверхности: слово 円
    указывает на запятую, «です» — на «2». У куска без букв (только знаки
    препинания) слово обязано совпадать с поверхностью; иначе уводим всё
    предложение в запасную цепочку. Кандзи/цифры/кана/латиница не
    проверяются: там word легитимно отличается (нормализация 十/百/千,
    ляпсусы словаря вроде シュミレーション).
    """
    s = surface or ""
    if not s or s.isspace() or KANJI_RE.search(s):
        return False
    if any(c.isdigit() for c in s):
        return False
    if re.search(r"[\u3040-\u30ff\u31f0-\u31ff\uff66-\uff9fa-zA-Z]", s):
        return False
    return unicodedata.normalize("NFKC", word or "") != \
        unicodedata.normalize("NFKC", s)


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
        if s == e:
            # нулевой спан: Haqumei вставил знак нормализации без поверхности
            # (разряды 十/百/千 в числах: 2024 -> 二千[二十四]). Поверхности
            # нет, источник истины — чтение токена; без этого 2024年
            # собирался как にせんによねん (じゅう терялся).
            if not read or KANJI_RE.search(read):
                return None                 # чтения нет — запасная цепочка
            out.append(read)
        elif _span_drift(surface, word):
            return None                     # спаны съехали — не доверяем
        elif KANJI_RE.search(surface):
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


def g2p_kana(text):
    """Иероглифы -> катану: ядро Haqumei, запасной ход Sudachi / pyopenjtalk.

    Первый ход — ядро (g2p_core.py, Haqumei): слово читается В КОНТЕКСТЕ
    ПРЕДЛОЖЕНИЯ. Не справилось — Sudachi по словарю UniDic, затем
    pyopenjtalk. Хирагана/катакана и знаки проходят как есть — их g2p не
    трогает.

    Бывшая «система чтения» (furigana_map, доменный словарь, резолвер)
    удалена: доменный словарь никогда не наполнялся, furigana_map никто не
    передавал, резолвер не вызывался — мёртвый код (аудит v1.9, M3).
    Реальная подстановка чтения из фуриганы карточки живёт выше — в
    kanaize_card / inject_reading.
    """
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


def kanaize(text):
    """Текст -> хирагана: NFKC -> словарь -> латиница катаканой -> сегменты
    -> g2p только иероглифы -> хирагана.

    Главный принцип: MeCab надёжно читает иероглифы и катакану, но портит
    уже готовую хирагану (применяет правила частиц: こんにちは -> コンニチワ).
    Поэтому ядру Haqumei подаётся текст с катеканой как есть — она даёт
    контекст для чтения иероглифов (ロッピャク殿 -> ドノ, а не トノ),
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
            reading = _content(segs[idxs[0]]).replace("\u30fb", "")
            if re.search(r"[\u3005\u3400-\u4dbf\u4e00-\u9fff]", base):
                # Разметка «на всё слово» или «только на кандзи» по записи
                # неразличима — различаем по звучанию: если кана вокруг
                # кандзи уже звучит в чтении (点群データ[てんぐんでーた]),
                # чтение на всё слово; иначе эта кана — своя, терять её
                # нельзя (アーク溶接棒[ようせつぼう] -> アークようせつぼう,
                # а не голое ようせつぼう).
                if _reading_covers_word(base, reading):
                    return reading
                return _base_reading(base, reading)
            return reading
    return _concat().replace("\u30fb", "")


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
        return kanaize(replace_term(t, norm_expr, reading))

    # латиница в предложении может отличаться регистром (PLATEAU vs plateau)
    if norm_expr and re.search(r"[A-Za-z]", norm_expr):
        k = KANJI_RE.pattern
        pat = re.compile(r"(?<!%s)%s(?!%s)" % (k, re.escape(norm_expr), k),
                         re.IGNORECASE)
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


def _kana_norm(s):
    """Кана к сравнимому виду: катакана -> хирагана, мелкие -> полные."""
    s = kata2hira(s or "")
    for a, b in (("\u3041", "\u3042"), ("\u3043", "\u3044"), ("\u3045", "\u3046"),
                 ("\u3047", "\u3048"), ("\u3049", "\u304a"), ("\u3083", "\u3084"),
                 ("\u3085", "\u3086"), ("\u3087", "\u3088")):
        s = s.replace(a, b)
    # «·» — разделитель, а не звук: в чтении его не бывает
    s = s.replace("\u30fb", "").replace("\u00b7", "")
    return s


def _reading_covers_word(base, reading):
    """Чтение покрывает слово целиком, а не только иероглифы.

    В колодах два формата разметки:
      * «点群データ[てんぐんでーた]» — чтение на всё слово. Окуригану
        («データ») добавлять нельзя: получится «データてんぐんでーた», и
        «データ» прозвучит дважды.
      * «アーク溶接棒[ようせつぼう]» — чтение только на иероглифы, окуригана
        («アーク») нужна.

    Различаем по звучанию: если окуригана уже звучит внутри чтения — значит,
    чтение покрывает слово целиком.
    """
    base = (base or "").strip()
    reading = _kana_norm(reading)
    if not base or not reading:
        return False
    # окуригана в основе — всё, кроме иероглифов (по частям: она может
    # быть и до иероглифов, и после)
    parts = re.split(KANJI_RE.pattern, base)
    for part in parts:
        q = _kana_norm(part)
        if q and q in reading:
            return True
    return False


def furiga_pair(text):
    """(поверхность, чтение) для разметки «основа[чтение]…хвост».

    «相欠[あいが]き継[つ]ぎ» -> («相欠き継ぎ», «あいがきつぎ»).
    Хвост после последней скобки без чтения остаётся как есть.
    (None, None) — если разметки нет.
    Многовариантное чтение («生花[いけばな,せいか]») берётся первым
    вариантом до запятой — как в _parse_furigana, иначе запятая уезжает
    в текст синтеза.
    """
    if "[" not in text:
        return None, None

    def _first(s):
        return s.split(",", 1)[0].strip()

    parts = re.split(r"\[([^\[\]]*)\]", text)
    last = len(parts) - 1
    # Одна скобка в самом конце: чтение либо на всё слово
    # («点群データ[てんぐんでーた]» — окуригану добавлять нельзя, иначе
    # «データ» прозвучит дважды), либо только на иероглифы
    # («アイススケート場[じょう]» — окуригана нужна).
    if len(parts) == 3 and parts[2] == "" and \
            _reading_covers_word(parts[0], _first(parts[1])):
        return parts[0], _first(parts[1]).replace("\u30fb", "")
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
            read.append(_base_reading(parts[i], _first(parts[i + 1])))
            i += 1
        i += 1
    # «・» в чтении — это разделитель морфем, а не знак для произнесения:
    # с ним модель начинает коверкать фразу (проверено: на «スキャン・トゥ・BIM»
    # выходило «тй-»). Убираем.
    return "".join(surf), "".join(read).replace("\u30fb", "")


def expression_inject_pair(note, reading_field, word_field="Expression"):
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

    # поле слова — настраиваемое (word_src): у колод оно бывает Word/Слово
    surface = re.sub(r"\[[^\[\]]*\]", "", fld(word_field)).strip()
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


def _doubled_okurigana(surface, text):
    """Окуригана прозвучит в готовом тексте дважды — вернём её (если нашли).

    Считаем в самом тексте, а не по формату записи, поэтому правило работает
    и для незнакомых форматов фуриганы. «データ» + «てんぐんでーた» ->
    «でーた» и «でーた»: модель сказала бы «データ» дважды.

    Возвращает найденный кусок (пустая строка — всё в порядке).
    """
    flat = _kana_norm(text)
    for part in re.split(KANJI_RE.pattern, surface or ""):
        q = _kana_norm(part)
        # окуригана короче двух знаков (частица «の», слог «ки») слишком часто
        # встречается в чтении случайно — на всей основной колоде такая проверка
        # срабатывала бы на 1.8% карточек и мешала бы правильной подстановке
        if len(q) >= 2 and flat.count(q) >= 2:
            return q
    return ""


def replace_term(text, surface, repl):
    """Заменить surface -> repl только там, где совпадение — целое слово.

    Простая string-замена бьёт и по чужим словам: 星 (ほし) внутри 火星 даёт
    «火ほし», 女王 (おう) — «女おう». Заменяем только совпадения, к которым
    НЕ прилегает иероглиф: прилегание слева/справа означает, что найденный
    кусок — часть кандзи-композита, а не сам термин. Прилегающая кана —
    разрешена (окуригана, частицы: 相欠き+を), латиница тоже (I形+鋼 — сам
    термин содержит латиницу и меняется вместе с ней).
    """
    k = KANJI_RE.pattern
    pat = re.compile(r"(?<!%s)%s(?!%s)" % (k, re.escape(surface), k))
    return pat.sub(lambda _m: repl, text)


def inject_reading_lenient(sentence, note, reading_field, word_field="Expression"):
    """Подставить чтение из поля в предложение без ограничения.

    Обычный вариант inject_reading требует, чтобы поверхность термина содержит кандзи
    (иногда термин — латинская аббревиатура вроде). Для режима
    «кандзи + чтение термина из фуриганы» подставовка нужна и для латинцы.
    """
    f = note["fields"]

    def fld(name):
        return plain(f.get(name, {}).get("value", ""))

    reading = fld(reading_field).strip()
    if not reading:
        return sentence
    surface = re.sub(r"\[[^\[\]]*\]", "", fld(word_field)).strip()
    if "[" in reading:
        fur_surf, fur_read = furiga_pair(reading)
        if fur_surf is None:
            return sentence
        surface = (fur_surf or "").strip() or surface
        reading = (fur_read or "").strip()
    if not reading or not surface or reading == surface:
        return sentence
    if KANJI_RE.search(reading):
        return sentence
    if surface not in sentence:
        return sentence
    repl = kata2hira(reading)
    # страховка: в ЗАМЕНЕ окуригана не должна прозвучать дважды. Если разбор
    # ошибся и окуригана попала в чтение второй раз — оставляем термин как
    # есть, пусть его прочитает сам движок. Считаем только в замене: в самом
    # предложении частица «を» может встречаться сколько угодно.
    dup = _doubled_okurigana(surface, repl)
    if dup:
        print("  [прочтение] окуригана %r прозвучала бы дважды — термин "
              "оставлен как есть" % dup)
        return sentence
    return replace_term(sentence, surface, repl)


def inject_reading(sentence, note, reading="", word_field="Expression"):
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
    kanji, rd = expression_inject_pair(note, reading_field=reading,
                                       word_field=word_field)
    if not kanji or not rd:
        return sentence
    if kanji not in sentence:
        return sentence
    return replace_term(sentence, kanji, kata2hira(rd))
