# -*- coding: utf-8 -*-
"""
Проверка произношения: сказали ли мы то, что просили.

Зачем. GPT-SoVITS режет текст на куски (так устроен text_split_method),
и на стыках модель может «потерять» фрагмент или придумать лишний.
Длительность при этом нормальная, поэтому старый QC (тишина, длина, дубль,
обрезка) такое пропускает: файл выглядит и звучит как речь, но это не то
предложение. На замерах на реальных карточках так ломались примерно 4%
озвученных предложений — их длина была в норме, а содержание — мусор.

Как проверяем.
  1. Ожидаемый текст -> кана (наша же разметка) + маска латиницы и цифр:
     ASR читает «TIN» как японское слово, и это не ошибка синтеза.
  2. Распознаём СВОЙ же звук (faster-whisper, если он есть в питоне движка).
  3. Сравниваем покрытие: доля ожидаемой каны, которую удалось услышать
     (LCS). «Модель пропустила кусок» — покрытие низкое; «прочитала
     слово не так» — покрытие высокое, а CER большой. Это разные поломки,
     и лечатся они по-разному.
  4. Порог: абсолютный пол + своя база по голосу (у разных голосов и
     колод CER разный, сравнивать надо с соседями, а не с нуля).

Модель нужна одна: faster-whisper в питоне движка и скачанные веса.
Если их нет — проверка просто выключена, приложение работает как раньше.
"""
# ВНИМАНИЕ: здесь нельзя писать `from __future__ import annotations` —
# модуль импортируется из замороженного exe (PyInstaller), а `__future__`
# в сборке нет: это директива компилятора, а не обычный импорт.
import json
import os
import re
import sys

WILD = "\ue000"          # заглушка: «здесь может быть что угодно»
LATIN = re.compile(r"([A-Za-z]+|[0-9]+)")

# модели faster-whisper по убыванию качества (крупные — точнее, но тяжелее)
_MODEL_ORDER = [
    "faster-whisper-large-v3-turbo",
    "faster-whisper-large-v3",
    "faster-whisper-medium",
    "faster-whisper-small",
    "faster-whisper-base",
    "faster-whisper-tiny",
]

# Пороги подобраны на замерах (43 озвученные карточки):
#   покрытие  median 0.90 | у двух настоящих галлюцинаций 0.31 и 0.46
#   следующий «хороший» клип — 0.58. Значит 0.55 отделяет мусор от нормы.
#   CER       median 0.17 | мусор 0.97-1.09 | норма до 0.42
COVER_FAIL = 0.55         # ниже — модель потеряла кусок фразы
COVER_SUSPECT = 0.80      # ниже — стоит послушать или переделать
CER_FAIL = 0.85           # услышали совсем другое предложение
CER_SUSPECT = 0.45        # местами прочитано не так
MIN_MORAS = 8             # короче — ASR слишком ненадёжен, не судим
MIN_SECONDS = 1.2         # короче — то же


def hf_cache_dirs():
    """Каталоги кэша HuggingFace (где лежат скачанные модели)."""
    out = []
    env = os.environ.get("HF_HOME")
    if env:
        out.append(os.path.join(env, "hub"))
    home = os.path.expanduser("~")
    out.append(os.path.join(home, ".cache", "huggingface", "hub"))
    for p in out:
        if os.path.isdir(p):
            yield p


def cached_models():
    """Скачанные модели faster-whisper: [(id, полный путь), ...]."""
    found = {}
    for hub in hf_cache_dirs():
        try:
            names = os.listdir(hub)
        except OSError:
            continue
        for n in names:
            if not n.startswith("models--") or "faster-whisper" not in n:
                continue
            mid = n[len("models--"):].replace("--", "/")
            found[mid] = os.path.join(hub, n)
    def rank(mid):
        for i, pref in enumerate(_MODEL_ORDER):
            if pref in mid:
                return i
        return len(_MODEL_ORDER)
    return sorted(found.items(), key=lambda kv: rank(kv[0]))


def pick_model(explicit=None):
    """Какую модель взять: заданную пользователем или лучшую из кэша."""
    if explicit:
        return explicit
    env = os.environ.get("ANKI_VOICE_ASR_MODEL")
    if env:
        return env
    models = cached_models()
    return models[0][0] if models else None


def expected_kana_masked(text, kanaize):
    """Ожидаемая кана + маска «здесь латиница/цифры».

    kanaize — функция перевода в кана (у нас это voice_pipeline.kanaize).
    """
    exp, wild = [], []
    for part in LATIN.split(text or ""):
        if not part:
            continue
        if LATIN.fullmatch(part):
            for _ in part:
                exp.append(WILD)
                wild.append(True)
        else:
            for ch in kanaize(part):
                exp.append(ch)
                wild.append(False)
    return "".join(exp), wild


def _lcs_len(a, b):
    if not a or not b:
        return 0
    prev = [0] * (len(b) + 1)
    for ca in a:
        cur = [0] * (len(b) + 1)
        for j, cb in enumerate(b, 1):
            cur[j] = prev[j - 1] + 1 if ca == cb else max(prev[j], cur[j - 1])
        prev = cur
    return prev[-1]


def compare(expected, wild, heard):
    """Сравнение ожидаемой каны и услышанной.

    coverage — доля ожидаемого, что удалось услышать (LCS);
    cer      — доля несовпадений (замены+вставки+удаления);
    skipped  — куски, которые прозвучали вместо ожидаемого.
    """
    e = [c for c in expected if c != WILD]
    h = [c for c in heard if c != WILD]
    n = len(e)
    if not n:
        return {"coverage": 1.0, "cer": 0.0, "n_jp": 0, "verdict": "пусто"}
    # выравнивание с подстановкой: латиница в expected совпадает с чем угодно
    INF = 10 ** 6
    m = len(h)
    dp = [[INF] * (m + 1) for _ in range(n + 1)]
    dp[0][0] = 0
    for i in range(n + 1):
        for j in range(m + 1):
            c = dp[i][j]
            if c == INF:
                continue
            if i < n and j < m:
                cost = 0 if wild[i] else (0 if e[i] == h[j] else 1)
                if c + cost < dp[i + 1][j + 1]:
                    dp[i + 1][j + 1] = c + cost
            if i < n:
                cost = 0 if wild[i] else 1
                if c + cost < dp[i + 1][j]:
                    dp[i + 1][j] = c + cost
            if j < m and c + 1 < dp[i][j + 1]:
                dp[i][j + 1] = c + 1
    cost = dp[n][m]
    cov = _lcs_len(e, h) / float(n)
    cer = cost / float(n)
    if n < MIN_MORAS:
        verdict, fail = "коротко", False
    elif cov < COVER_FAIL:
        verdict, fail = "пропущено", True
    elif cer > CER_FAIL:
        verdict, fail = "не то предложение", True
    elif cov < COVER_SUSPECT or cer > CER_SUSPECT:
        verdict, fail = "подозрительно", False
    else:
        verdict, fail = "ок", False
    return {"coverage": cov, "cer": cer, "n_jp": n, "cost": cost,
            "verdict": verdict, "fail": fail}


class Verifier(object):
    """Распознаёт наш звук и сравнивает с ожидаемым текстом.

    Модель грузится один раз и держится в процессе (5–10 с на прогретом
    кэше, проверка клипа — около 0.5 с на GPU).
    """

    def __init__(self, model=None, device=None, compute_type="int8", kanaize=None):
        self.model_id = model
        self.device = device
        self.compute_type = compute_type
        self.kanaize = kanaize
        self._model = None
        self._tried = False
        self.error = ""

    # ---------------------------------------------------------------- model
    def available(self):
        """(доступно ли, почему нет)."""
        if self._model is not None:
            return True, "модель загружена"
        if self._tried and self.error:
            return False, self.error
        self._tried = True
        try:
            import faster_whisper  # noqa: F401
        except Exception as e:
            self.error = ("faster-whisper не установлен в питоне движка "
                          "(%s)" % (repr(e)[:60],))
            return False, self.error
        mid = pick_model(self.model_id)
        if not mid:
            self.error = ("нет скачанной модели faster-whisper "
                          "(нужна папка models--*--faster-whisper-* в кэше HuggingFace)")
            return False, self.error
        return True, "модель %s" % mid

    def load(self):
        if self._model is not None:
            return self._model
        ok, why = self.available()
        if not ok:
            return None
        from faster_whisper import WhisperModel
        device = self.device
        if not device:
            try:
                import ctranslate2
                device = "cuda" if ctranslate2.get_cuda_device_count() > 0 else "cpu"
            except Exception:
                device = "cpu"
        mid = pick_model(self.model_id)
        self._model = WhisperModel(mid, device=device, compute_type=self.compute_type)
        self.device = device
        self.model_id = mid
        return self._model

    # ---------------------------------------------------------------- audio
    def transcribe(self, path):
        """path -> текст (японский)."""
        model = self.load()
        if model is None:
            return ""
        segs, _info = model.transcribe(path, language="ja", beam_size=1,
                                       vad_filter=False,
                                       condition_on_previous_text=False)
        return "".join(s.text for s in segs)

    def transcribe_bytes(self, blob, ext="wav", workdir=None):
        """blob -> текст: пишем во временный файл и распознаём."""
        import tempfile
        fd, path = tempfile.mkstemp(suffix="." + (ext or "wav"), dir=workdir)
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(blob)
            return self.transcribe(path)
        finally:
            try:
                os.remove(path)
            except OSError:
                pass

    # ---------------------------------------------------------------- verdict
    def check(self, blob, ext, src_text, kanaize=None):
        """Проверить кусок: {ok, coverage, cer, heard, verdict}."""
        kanaize = kanaize or self.kanaize
        if kanaize is None:
            return {"ok": True, "verdict": "нет разметки", "coverage": 1.0, "cer": 0.0}
        expected, wild = expected_kana_masked(src_text or "", kanaize)
        n_jp = sum(1 for w in wild if not w)
        if n_jp < MIN_MORAS:
            return {"ok": True, "verdict": "коротко", "coverage": 1.0,
                    "cer": 0.0, "n_jp": n_jp}
        heard_raw = self.transcribe_bytes(blob, ext)
        heard = kanaize(heard_raw) if heard_raw.strip() else ""
        res = compare(expected, wild, heard)
        res["heard"] = heard
        res["heard_raw"] = heard_raw
        res["ok"] = not res.get("fail")
        res["suspect"] = res["verdict"] == "подозрительно"
        return res
