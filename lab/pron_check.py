# -*- coding: utf-8 -*-
"""
Проверка произношения: сказали ли мы то, что просили.

Зачем. GPT-SoVITS режет текст на куски (так устроен text_split_method),
и на стыках модель может «потерять» фрагмент или придумать лишний.
Длительность при этом нормальная, и старый QC (тишина/длина/дубль) такое
не видит: файл выглядит и звучит как речь, но это не то предложение.

Как проверяем.
  1. Ожидаемый текст -> кана (наша же разметка) + маска латиницы и цифр:
     ASR читает «TIN» как японское слово, и это не ошибка синтеза.
  2. Распознаём СВОЙ же звук (faster-whisper, если он есть в питоне движка).
  3. Сравниваем:
       покрытие — доля ожидаемой речи, которую удалось услышать (LCS).
                  «модель пропустила кусок» -> низкое покрытие;
       cer      — доля несовпадений: «прочитала не так» -> высокий cer,
                  а покрытие высокое.
  4. Где именно поехало: по таймстемпам слов ASR находим первое расхождение
     и отдаём временной участок (секунды) — его можно послушать отдельно.
  5. Неразборчивое: если ASR неуверен (низкий средний лог-вероятность) или
     ушёл в другой алфавит — это «не разобрано», а не брак.

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

# --- пороги (абсолютные; относительные считаются по своей базе) -----------
COVER_FAIL = 0.55         # ниже — модель потеряла кусок фразы
COVER_SUSPECT = 0.80      # ниже — стоит послушать или переделать
CER_FAIL = 0.85           # услышали совсем другое предложение
CER_SUSPECT = 0.45        # местами прочитано не так
MIN_MORAS = 8             # короче — ASR слишком ненадёжен, не судим
MIN_SECONDS = 1.2         # короче — то же
MIN_SEC_PER_MORA = 0.055  # быстрее — физически не успеть прочитать
LOW_CONFIDENCE = -0.85     # средний лог-вероятность ASR ниже — не доверяем
ACOUSTIC_FAIL = 0.50      # акустическое покрытие ниже — кусок реально потерян
HIGH_NOSPEECH = 0.6        # ASR решил, что это не речь


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


SMALL_KANA = {
    "\u3041": "\u3042", "\u3043": "\u3044", "\u3045": "\u3046",
    "\u3047": "\u3048", "\u3049": "\u304a",
    "\u3083": "\u3084", "\u3085": "\u3086", "\u3087": "\u3088",
    "\u308e": "\u308f", "\u3095": "\u3096", "\u3096": "\u3099",
}
PUNCT = "\u3001\u3002\u3000-\u2026,.;:!?\u300c\u300d\u300e\u300f()[]\u30fb"


def norm_char(ch):
    """Один знак в сравнимом виде: мелкий кана -> обычный, пунктуация вон."""
    if ch in PUNCT or ch.isspace():
        return ""
    return SMALL_KANA.get(ch, ch)


def normalize_kana(s):
    """Приводим каны к сравнимому виду.

    ASR не различает мелкие каны (ぃ пишет как い) и может поставить свою
    пунктуацию. Это не ошибка синтеза, поэтому сравниваем «нормализованные»
    строки: мелкие каны -> обычные, пунктуация выбрасывается.
    """
    return "".join(x for x in (norm_char(c) for c in (s or "")) if x)


def expected_kana_masked(text, kanaize):
    """Ожидаемая кана + маска «здесь латиница/цифры».

    kanaize — функция перевода в кана (у нас это voice_pipeline.kanaize).
    Латиницу тоже переводим в кана (она будет произнесена по буквам) и
    маскируем каждый знак: длина маски обязана совпадать с длиной каны,
    иначе выравнивание едет.
    """
    exp, wild = [], []
    for part in LATIN.split(text or ""):
        if not part:
            continue
        is_latin = bool(LATIN.fullmatch(part))
        for ch in kanaize(part):
            if is_latin:
                exp.append(WILD)          # сколько знаков в кана — столько и масок
                wild.append(True)
            else:
                nch = norm_char(ch)
                if nch:
                    exp.append(nch)
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


def _looks_foreign(expected, heard):
    """Услышали не японский? Тогда вердикт по содержанию невозможен."""
    exp_jp = any("\u3040" <= ch <= "\u30ff" for ch in (expected or ""))
    if not exp_jp:
        return False
    lat = sum(1 for ch in (heard or "") if ch.isascii() and ch.isalpha())
    kana = sum(1 for ch in (heard or "") if "\u3040" <= ch <= "\u30ff")
    return lat >= 3 and kana == 0


def compare(expected, wild, heard, limits=None):
    """Сравнение ожидаемой каны и услышанной.

    coverage — доля ожидаемого, что удалось услышать (LCS по не-маскированным
              знакам): «модель потеряла кусок фразы» -> низкое покрытие;
    cer      — доля несовпадений: замены + удаления + лишнее;
    fail     — брак (кусок потерян или услышали совсем другое);
    suspect  — сомнительно (слово прочитано не так, но фраза на месте).

    Латиница в expected помечена заглушкой WILD: она совпадает с любым
    услышанным куском, а «лишнее» рядом с ней (модель прочитала TIN как
    японское слово) ошибкой не считается.

    limits — свои пороги (присваиваются по своей базе, см. baseline).
    """
    lim = dict(COVER_FAIL=COVER_FAIL, COVER_SUSPECT=COVER_SUSPECT,
               CER_FAIL=CER_FAIL, CER_SUSPECT=CER_SUSPECT, MIN_MORAS=MIN_MORAS)
    if limits:
        lim.update(limits)
    heard = normalize_kana(heard)
    exp = list(expected)                 # с заглушками, индексы совпадают с wild
    h = list(heard)
    n_full = len(exp)
    plain = [c for c in exp if c != WILD]
    n = len(plain)
    if not n:
        return {"coverage": 1.0, "cer": 0.0, "n_jp": 0, "verdict": "пусто",
                "fail": False, "suspect": False}
    INF = 10 ** 6
    m = len(h)
    dp = [[INF] * (m + 1) for _ in range(n_full + 1)]
    dp[0][0] = 0
    for i in range(n_full + 1):
        for j in range(m + 1):
            c = dp[i][j]
            if c == INF:
                continue
            if i < n_full and j < m:
                cost = 0 if wild[i] else (0 if exp[i] == h[j] else 1)
                if c + cost < dp[i + 1][j + 1]:
                    dp[i + 1][j + 1] = c + cost
            if i < n_full:
                cost = 0 if wild[i] else 1
                if c + cost < dp[i + 1][j]:
                    dp[i + 1][j] = c + cost
            if j < m:
                near_wild = ((i < n_full and wild[i]) or
                             (i > 0 and wild[i - 1]))
                cost = 0 if near_wild else 1
                if c + cost < dp[i][j + 1]:
                    dp[i][j + 1] = c + cost
    cost = dp[n_full][m]
    cov = _lcs_len(plain, h) / float(n)
    cer = cost / float(n)
    if n < lim["MIN_MORAS"]:
        verdict, fail, suspect = "коротко", False, False
    elif cov < lim["COVER_FAIL"]:
        verdict, fail, suspect = "пропущено", True, False
    elif cer > lim["CER_FAIL"]:
        verdict, fail, suspect = "не то предложение", True, False
    elif cov < lim["COVER_SUSPECT"] or cer > lim["CER_SUSPECT"]:
        verdict, fail, suspect = "подозрительно", False, True
    else:
        verdict, fail, suspect = "ок", False, False
    return {"coverage": cov, "cer": cer, "n_jp": n, "cost": cost,
            "verdict": verdict, "fail": fail, "suspect": suspect}


def locate_span(expected, wild, words):
    """Где именно поехало: первое слово, на котором текст разошёлся.

    words — слова с таймстемпами от ASR: [{"start":..,"end":..,"text":..}].
    Возвращает (start, end, услышано, ожидалось) или None.
    """
    exp = normalize_kana(expected)
    pos = 0
    for w in words or []:
        wn = normalize_kana(w.get("text", ""))
        if not wn:
            continue
        seg = exp[pos:pos + len(wn)]
        if seg != wn:
            return (w.get("start"), w.get("end"), w.get("text", ""), seg)
        pos += len(wn)
    return None


class Verifier(object):
    """Распознаёт наш звук и сравнивает с ожидаемым текстом.

    Модель грузится один раз и держится в процессе (5–10 с на прогретом
    кэше, сама проверка клипа — около 0.5 с на GPU).
    """

    def __init__(self, model=None, device=None, compute_type="int8", kanaize=None,
                 limits=None):
        self.model_id = model
        self.device = device
        self.compute_type = compute_type
        self.kanaize = kanaize
        self.limits = limits or {}
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
    def transcribe(self, path, words=True):
        """path -> (текст, слова, метаданные)."""
        model = self.load()
        if model is None:
            return "", [], {}
        segs, info = model.transcribe(path, language="ja", beam_size=1,
                                      vad_filter=False,
                                      condition_on_previous_text=False,
                                      word_timestamps=words)
        text = "".join(s.text for s in segs)
        wlist = []
        for s in segs:
            for w in (getattr(s, "words", None) or []):
                wlist.append({"start": getattr(w, "start", None),
                              "end": getattr(w, "end", None),
                              "text": getattr(w, "word", "") or ""})
        meta = {"avg_logprob": getattr(info, "avg_logprob", None),
                "no_speech_prob": getattr(info, "no_speech_prob", None),
                "duration": getattr(info, "duration", None)}
        return text, wlist, meta

    def transcribe_bytes(self, blob, ext="wav", workdir=None):
        """blob -> (текст, слова, метаданные)."""
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
        """Проверить кусок: {ok, coverage, cer, heard, verdict, span...}."""
        kanaize = kanaize or self.kanaize
        if kanaize is None:
            return {"ok": True, "verdict": "нет разметки", "coverage": 1.0, "cer": 0.0}
        expected, wild = expected_kana_masked(src_text or "", kanaize)
        n_jp = sum(1 for w in wild if not w)
        if n_jp < MIN_MORAS:
            return {"ok": True, "verdict": "коротко", "coverage": 1.0,
                    "cer": 0.0, "n_jp": n_jp}
        path = self._write_temp(blob, ext)
        try:
            raw, words, meta = self._transcribe_path(path)
            return self._judge(expected, wild, raw, words, meta, path,
                               kanaize, n_jp)
        finally:
            try:
                os.remove(path)
            except OSError:
                pass

    def _write_temp(self, blob, ext):
        import tempfile
        fd, path = tempfile.mkstemp(suffix="." + (ext or "wav"))
        with os.fdopen(fd, "wb") as f:
            f.write(blob)
        return path

    def _transcribe_path(self, path):
        return self.transcribe(path)

    def _judge(self, expected, wild, raw, words, meta, path, kanaize, n_jp):
        heard = kanaize(raw) if raw.strip() else ""
        res = compare(expected, wild, heard, limits=self.limits)
        res["heard"] = heard
        res["heard_raw"] = raw
        res["avg_logprob"] = meta.get("avg_logprob")
        res["no_speech_prob"] = meta.get("no_speech_prob")
        res["duration"] = meta.get("duration")
        # акустическое выравнивание: где именно потерялся кусок
        al = None
        try:
            import align_ja
            if align_ja.available():
                al = align_ja.align(path, expected)
        except Exception:
            al = None
        if al and al.get("reliable"):
            res["coverage_acoustic"] = al.get("coverage")
            if al.get("worst"):
                res["span"] = {"start": al["worst"]["start"],
                               "end": al["worst"]["end"],
                               "heard": al["worst"]["text"],
                               "expected": al["worst"]["text"]}
            # акустика верит больше, чем текст ASR: сильно разошедшееся
            # выравнивание — почти наверняка реальная потеря
            cov_a = al.get("coverage")
            if cov_a is not None and cov_a < ACOUSTIC_FAIL:
                if not res.get("fail"):
                    res["fail"] = True
                    res["verdict"] = "пропущено (по звуку)"
                    res.setdefault("sigs", []).append(
                        "акустика: покрытие %.2f" % cov_a)
        # ASR неуверен или ушёл в другой алфавит — судить не по чему
        conf = meta.get("avg_logprob")
        nos = meta.get("no_speech_prob")
        dur = meta.get("duration")
        if conf is not None and conf < LOW_CONFIDENCE:
            res["verdict"], res["fail"] = "не разобрано (ASR неуверен)", False
        elif nos is not None and nos > HIGH_NOSPEECH:
            res["verdict"], res["fail"] = "не разобрано (не похоже на речь)", False
        elif dur and n_jp and dur < MIN_SEC_PER_MORA * n_jp:
            res["verdict"], res["fail"] = "не разобрано (слишком коротко)", False
        elif _looks_foreign(expected, heard):
            res["verdict"], res["fail"] = "не разобрано", False
        else:
            span = locate_span(expected, wild, words)
            if span:
                res["span"] = {"start": span[0], "end": span[1],
                               "heard": span[2], "expected": span[3]}
        res["ok"] = not res.get("fail")
        res["suspect"] = res["verdict"].startswith("подозрительно")
        return res
