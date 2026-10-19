"""Метрики качества синтезированного звука v2 — несколько независимых сигналов.

Одной «долей звука» мусор поймать можно, но не отличить его от короткого
слова, тихого голоса или записи с длинной паузой внутри. Считаем сразу
несколько признаков:

  dur        — общая длительность, с
  sounding   — длительность реально звучащего куска, с
  lead/tail  — вступительная/финальная тишина, с
  gap_max    — самая длинная тишина ВНУТРИ речи, с
  rate       — мор ( знаков текста ) в секунду речи
  peak       — максимальная амплитуда (0..1)
  dbfs       — средний уровень речи, дБ
  clip       — доля обрезанных сэмплов
  loop       — насколько силуэт повторяется сам на себе (0..1)
  segs       — число звучащих кусков
"""
from __future__ import annotations

import os
import subprocess
import unicodedata

import numpy as np

# окно анализа, с
WIN = 0.02


def ffmpeg_exe(engine: str) -> str:
    p = os.path.join(engine, "runtime", "ffmpeg.exe")
    if os.path.exists(p):
        return p
    try:
        import shutil
        return shutil.which("ffmpeg") or ""
    except Exception:
        return ""


def decode(blob: bytes, ff: str, sr: int = 16000):
    """ogg/wav -> моно float32."""
    if not ff:
        return None, 0
    cmd = [ff, "-v", "error", "-i", "pipe:0", "-f", "s16le",
           "-ac", "1", "-ar", str(sr), "pipe:1"]
    try:
        r = subprocess.run(cmd, input=blob, capture_output=True, timeout=120)
    except Exception:
        return None, 0
    if r.returncode != 0 or len(r.stdout) < 4:
        return None, 0
    x = np.frombuffer(r.stdout, dtype="<i2").astype("float32") / 32768.0
    return x, sr


def metrics_from_pcm(x: np.ndarray, sr: int) -> dict:
    dur = len(x) / sr
    win = max(1, int(sr * WIN))
    n = len(x) // win
    if n == 0:
        return {"dur": dur, "sounding": 0.0, "lead": dur, "tail": 0.0,
                "gap_max": 0.0, "peak": 0.0, "dbfs": -120.0, "clip": 0.0,
                "loop": 0.0, "dup": 0.0, "segs": 0, "ok": True}

    peak = float(np.abs(x).max())
    # порог «слышно»: абсолютный -45 дБFS либо на 30 дБ ниже пика
    thr = max(10 ** (-45 / 20), peak * 0.03)
    rms = np.array([np.sqrt((x[i * win:(i + 1) * win] ** 2).mean())
                    for i in range(n)])
    on = rms > thr

    def t(i):
        return i * win / sr

    idx = np.where(on)[0]
    if idx.size == 0:
        return {"dur": dur, "sounding": 0.0, "lead": dur, "tail": 0.0,
                "gap_max": dur, "peak": peak, "dbfs": -120.0,
                "clip": float((np.abs(x) >= 0.999).mean()), "loop": 0.0,
                "dup": 0.0, "segs": 0, "ok": True}

    lead = t(idx[0])
    tail = dur - t(idx[-1] + 1)
    sounding = float(on.sum() * win / sr)

    # сегменты звука и разрывы между ними
    segs, gaps = [], []
    start = idx[0]
    prev = idx[0]
    for i in idx[1:]:
        if i != prev + 1:
            segs.append((start, prev))
            gaps.append(t(i) - t(prev + 1))
            start = i
        prev = i
    segs.append((start, prev))
    gap_max = max(gaps) if gaps else 0.0

    # уровень речи
    voiced = rms[on]
    dbfs = 20 * np.log10(float(voiced.mean()) + 1e-9)

    # Залипшая генерация (один и тот же кусок речи повторяется).
    # Силуэт даёт ложные срабатывания на обычной волнообразной речи
    # (корреляция 0.75+ бывает и без дубля), поэтому считаем двумя
    # способами и верим только их СОВПАДЕНИЮ:
    #   loop  — корреляция силуэта (дешёвая, широкая сетка),
    #   dup   — корреляция сырого PCM на том же лаге (строгая: дубль
    #           должен буквально повторять волну, а не просто «похожую
    #           по громкости» последовательность).
    loop = dup = 0.0
    best_lag = 0
    if sounding > 1.5:
        e = rms - rms.mean()
        best = 0.0
        lo = max(4, int(0.3 / WIN))            # от 0.3 с
        hi = min(len(e) // 2, int(5.0 / WIN))  # до 5 с
        for lag in range(lo, hi):
            a, b = e[:-lag], e[lag:]
            d = float(np.linalg.norm(a) * np.linalg.norm(b))
            if d == 0:
                continue
            c = float(np.dot(a, b) / d)
            if c > best:
                best, best_lag = c, lag
        loop = best
        if loop > 0.6 and best_lag:
            # та же проверка на PCM (один и тот же лаг)
            a = x[:len(x) - best_lag * win]
            b = x[best_lag * win:len(x)]
            if len(a) > sr // 2:
                d = float(np.linalg.norm(a) * np.linalg.norm(b))
                dup = float(np.dot(a, b) / d) if d else 0.0

    return {"dur": dur, "sounding": sounding, "lead": lead, "tail": tail,
            "gap_max": gap_max, "peak": peak, "dbfs": dbfs,
            "clip": float((np.abs(x) >= 0.999).mean()), "loop": loop,
            "dup": dup, "segs": len(segs), "ok": True}


def analyze(blob: bytes, ff: str) -> dict:
    x, sr = decode(blob, ff)
    if x is None:
        return {"dur": 0.0, "sounding": 0.0, "lead": 0.0, "tail": 0.0,
                "gap_max": 0.0, "peak": 0.0, "dbfs": -120.0, "clip": 0.0,
                "loop": 0.0, "dup": 0.0, "segs": 0, "ok": False}
    m = metrics_from_pcm(x, sr)
    m["ok"] = True
    return m


def sound_chars(text: str) -> int:
    """«Звуковые» знаки текста: NFKC (полукатакана ｶﾞ -> ガ) и без пунктуации,
    пробелов и разделителей (・, 。, - и т.п.).

    Из этого числа строится ожидаемая длительность речи — грубая, но
    работающая для любой системы письма: иероглифы, кана, полукатакана,
    латиница. Пунктуация не должна занижать ожидание.
    """
    skip = set(" 　・、,。．.!?！？…‥「」『』（）()［］[]【】\n\r\t"
               "-―～~/'\"“”")
    t = unicodedata.normalize("NFKC", text or "")
    return sum(1 for ch in t if ch not in skip and not ch.isspace())


def mora_count(text: str) -> int:
    """Грубая оценка числа мор в японском тексте (кана): малые кана, っ, ゃюё
    входят в предыдущую мору, ー считается отдельной морой, прочие знаки
    (латиница, цифры, пробелы, пунктуация) не считаются."""
    small = set("ゃゅょャュョぁぃぅぇぉァィゥェォゎヮ")
    kana = set(
        "あいうえおかきくけこさしすせそたちつてとなにぬねのはひふへほ"
        "まみむめもやゆよらりるれろわをんアイウエオカキクケコサシスセソ"
        "タチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲン"
        "がぎぐげござじずぜぞだぢづでどばびぶべぼぱぴぷぺぽ"
        "ガギグゲゴザジズゼゾダヂヅデドバビブベボパピプペポ")
    n = 0
    prev_was_mora = False
    for ch in text:
        if ch in small and prev_was_mora:
            continue                    # объединяется с предыдущей
        if ch in kana or ch == "ー":
            n += 1
            prev_was_mora = True
        elif ch.isascii() and ch.isalnum():
            # латиница/цифры: делим на моры грубо — по 2 знака на мору
            n += 1
            prev_was_mora = True
        else:
            prev_was_mora = False
    return n


def _limits(exp_s: float) -> dict:
    """Пороги в зависимости от ожидаемой длительности речи.

    Физика разная. У одиночного слова речи 0.3–1.3 с, и постоянная
    добавка (вступление, хвост, интонационное растяжение) съедает львиную
    долю — поэтому у слов доля «речи мало» может быть низкой и без брака,
    а единый жёсткий порог давал бы ложные отбраковки. У предложений
    речи 1.5–5.4 с, та же добавка становится процентами и мусор от
    нормы отделяется куда резче.

    Разделение по exp_s (ожидаемая длительность), а не по имени поля:
    оно работает для любой системы письма и не зависит от того, как
    пользователь назвал поля. Эмпирика — 151 файл бенча:

      слово (exp < 1.5 с):  норма ratio >= 0.50, мусор 0.30 и 0.40
      предложение:          норма ratio >= 0.55, мусора в группе нет
    """
    word = exp_s < 1.5
    return {
        "word": word,
        # нижняя граница доли «речи от ожидаемой»
        "min_sounding_ratio": 0.45 if word else 0.50,
        # допустимое вступительное молчание
        "max_lead": 1.2,
        # допустимый финальный хвост тишины
        "max_tail": 1.2,
    }


def verdict(m: dict, text: str = "") -> tuple:
    """(список сработавших сигналов, True=мусор).

    Сигналы независимы и трактуются консервативно: любой сам по себе
    достаточен, чтобы отклонить файл.
    """
    if not m.get("ok"):
        return [], False
    n = sound_chars(text) if text else 0
    exp_s = 0.15 * n if n else 0.0
    lim = _limits(exp_s) if exp_s else None

    v = []
    if m["sounding"] < 0.15:
        v.append("тишина(речь %.2f с)" % m["sounding"])
    if m["dur"] > 8.0 and m["sounding"] < 1.5:
        v.append("пустой хвост(%.1f с файла, речь %.1f)" % (m["dur"], m["sounding"]))
    max_lead = lim["max_lead"] if lim else 1.2
    max_tail = lim["max_tail"] if lim else 1.2
    if m["lead"] > max_lead:
        v.append("долгое молчание в начале %.1f с" % m["lead"])
    if m["tail"] > max_tail:
        v.append("долгий хвост %.1f с" % m["tail"])
    if exp_s:
        if m["dur"] > max(8.0, exp_s * 3):
            v.append("длина x%.1f от ожидаемой" % (m["dur"] / max(exp_s, 0.1)))
        if m["dur"] > 6.0 and m["sounding"] < exp_s * 0.5:
            v.append("речи < 50%% ожидаемого")
        # Речи почти нет, хотя текст есть («тихая» запись: формально звук
        # есть, но доли секунды на много знаков). Порог раздельный:
        # см. _limits. sound_chars учитывает полукатакану и иероглифы
        # (NFKC) и не считает пунктуацию.
        if m["sounding"] < exp_s * lim["min_sounding_ratio"]:
            v.append("речи мало: %.2f с из ожидаемых ~%.1f"
                     % (m["sounding"], exp_s))
        # скорость речи: мор в секунду звучания
        mo = mora_count(text)
        if mo and m["sounding"] > 0.2:
            rate = mo / m["sounding"]
            if rate > 14:
                v.append("речь ускорена x%.1f" % (rate / 8.0))
    if m["gap_max"] > 4.0:
        v.append("разрыв внутри речи %.1f с" % m["gap_max"])
    # застрявшее повторение: силуэт И волна повторяются (см. metrics)
    if m.get("loop", 0) > 0.7 and m.get("dup", 0) > 0.6 and m["sounding"] > 2.0:
        v.append("дубль речи (loop %.2f / dup %.2f)"
                 % (m["loop"], m["dup"]))
    if m["dbfs"] < -45:
        v.append("слишком тихо (%.0f дБ)" % m["dbfs"])
    if m["clip"] > 0.001:
        v.append("обрезка %.2f%%" % (m["clip"] * 100))
    return v, bool(v)
