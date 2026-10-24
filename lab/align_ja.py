# -*- coding: utf-8 -*-
"""
Посимвольное выравнивание: где именно в звуке потерялась фраза.

Зачем. Сравнение по распознанному тексту (LCS) отвечает на вопрос
«похоже ли то, что услышали, на ожидаемое», но не показывает, ГДЕ разошлось.
Выравнивание по акустической модели отвечает точнее: модель сама
сопоставляет свои же символы звуку и говорит, какой кусок ожидаемого текста
в звуке отсутствует или произнесён неверно.

Как. Японская char-level CTC-модель (reazon-research/japanese-wav2vec2-base-rs35kh)
даёт для каждого кадра распределение по символам. Дальше — треллис
(CTC forced alignment, как в torchaudio): ищем самый вероятный путь
«ожидаемый текст → звук» и получаем время и уверенность каждого символа.

Покрытие по выравниванию честнее, чем по тексту ASR: акустическая модель
не путает мелкие каны, не «слышит» TIN как японское слово и не зависит от
того, как ASR переписал слово.

Модель нужна одна: ~380 МБ в кэше HuggingFace. Если её нет — слой просто
выключен, всё остальное работает как раньше.
"""
# ВНИМАНИЕ: без `from __future__ import annotations` — модуль импортируется
# из замороженного exe, а `__future__` в сборке нет.
import os
import re

MODEL_NAME = "reazon-research/japanese-wav2vec2-base-rs35kh"
ENV_MODEL = "ANKI_VOICE_ALIGN_MODEL"

_STATE = {"model": None, "proc": None, "vocab": None, "tried": False,
          "error": ""}

# символы, которые не произносятся и не должны попадать в выравнивание
_SKIP = re.compile(r"[\s\u3000\u30fb\u309b\u309c]|[,.!?;:]")


def model_name():
    return os.environ.get(ENV_MODEL) or MODEL_NAME


def available():
    """(доступно ли, описание).

    Слой экспериментальный: модель reazon-research оперирует японскими
    подсловами, и выравнивание по ним на наших коротких клипах неустойчиво.
    Поэтому включается только явно: ANKI_VOICE_ALIGN=1. По умолчанию
    локализацию делают таймстемпы слов ASR.
    """
    if _STATE["model"] is not None:
        return True, "модель загружена"
    if not os.environ.get("ANKI_VOICE_ALIGN"):
        _STATE["error"] = "акустическое выравнивание выключено (ANKI_VOICE_ALIGN=1)"
        return False, _STATE["error"]
    if _STATE["tried"] and _STATE["error"]:
        return False, _STATE["error"]
    _STATE["tried"] = True
    try:
        import torch  # noqa: F401
        import transformers  # noqa: F401
    except Exception as e:
        _STATE["error"] = "в питоне движка нет torch/transformers (%s)" % (repr(e)[:50],)
        return False, _STATE["error"]
    return True, "модель %s" % model_name()


def _fix_conv_weights(model, name):
    """Веса позиционной свёртки: чекпоинт в новом формате, модель — в старом.

    Чекпоинт reazon-research кладёт свёртку как
    conv.parametrizations.weight.original0/1, а transformers 4.43 с torch 2.0
    ждёт conv.weight_g/weight_v. Без переименования свёртка остаётся
    случайной — и модель выдаёт NaN.
    """
    try:
        from huggingface_hub import try_to_load_from_cache
        import safetensors.torch as _st
        path = try_to_load_from_cache(name, "model.safetensors")
        if not path or not os.path.exists(path):
            return
        sd = _st.load_file(path)
        base = "wav2vec2.encoder.pos_conv_embed.conv"
        kg = base + ".parametrizations.weight.original0"
        kv = base + ".parametrizations.weight.original1"
        if kg in sd and kv in sd:
            sd[base + ".weight_g"] = sd.pop(kg)
            sd[base + ".weight_v"] = sd.pop(kv)
            model.load_state_dict(sd, strict=False)
    except Exception:
        pass


def load():
    """Модель + токенизатор (грузится один раз)."""
    if _STATE["model"] is not None:
        return _STATE["model"], _STATE["vocab"]
    ok, why = available()
    if not ok:
        return None, None
    try:
        from transformers import AutoModelForCTC, AutoProcessor
        name = model_name()
        proc = AutoProcessor.from_pretrained(name)
        model = AutoModelForCTC.from_pretrained(name)
        _fix_conv_weights(model, name)
        model.eval()
        _STATE["model"] = model
        _STATE["proc"] = proc
        _STATE["vocab"] = proc.tokenizer.get_vocab()
        return model, _STATE["vocab"]
    except Exception as e:
        _STATE["error"] = "не удалось загрузить %s: %s" % (model_name(), repr(e)[:80])
        return None, None


def _ffmpeg():
    """ffmpeg движка: им декодируем звук в 16 кГц моно."""
    eng = os.environ.get("GPT_SOVITS_ROOT") or ""
    for p in (os.path.join(eng, "runtime", "ffmpeg.exe"),
              os.path.join(eng, "runtime", "ffmpeg"),
              "ffmpeg"):
        if p and (os.path.isfile(p) or p == "ffmpeg"):
            return p
    return None


def _read_wav16k(path):
    """Звук -> numpy float32 16 кГц моно (None, если не вышло)."""
    import subprocess
    import tempfile
    import wave
    import numpy as np
    ff = _ffmpeg()
    if not ff:
        return None
    fd, tmp = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    try:
        r = subprocess.run([ff, "-v", "quiet", "-y", "-i", path, "-ac", "1",
                            "-ar", "16000", "-f", "wav", tmp],
                           capture_output=True, timeout=120)
        if r.returncode != 0 or not os.path.getsize(tmp):
            return None
        with wave.open(tmp, "rb") as w:
            n = w.getnframes()
            raw = w.readframes(n)
            sw = w.getsampwidth()
            ch = w.getnchannels()
        if sw == 2:
            data = np.frombuffer(raw, dtype="<i2").astype("float32") / 32768.0
        elif sw == 4:
            data = np.frombuffer(raw, dtype="<i4").astype("float32") / 2147483648.0
        else:
            return None
        if ch > 1:
            data = data.reshape(-1, ch).mean(axis=1)
        return data
    except Exception:
        return None
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass


def _tokens(expected, vocab):
    """Ожидаемый текст -> список (символ, id токена)."""
    out = []
    for ch in expected or "":
        if _SKIP.match(ch):
            continue
        tid = vocab.get(ch)
        if tid is None:
            continue
        out.append((ch, int(tid)))
    return out


def _tokenize(expected, proc):
    """Ожидаемый текст -> id токенов модели (у неё японские подслова)."""
    try:
        ids = proc.tokenizer(expected, add_special_tokens=False)["input_ids"]
        return [int(i) for i in ids]
    except Exception:
        return []


def align(audio_path, expected):
    """Выровнять ожидаемый текст по звуку.

    Возвращает {"coverage": доля токенов, найденных в звуке,
    "tokens": [...], "worst": (начало, конец, текст)} — худший участок.
    """
    model, vocab = load()
    if model is None or not vocab:
        return None
    try:
        import numpy as np
        import torch
    except Exception:
        return None
    proc = _STATE.get("proc")
    if proc is None:
        return None
    ids = _tokenize(expected, proc)
    if len(ids) < 2:
        return None
    wav = _read_wav16k(audio_path)
    if wav is None or len(wav) < 1600:
        return None
    try:
        # нормализация процессора (нулевое среднее, единичная дисперсия) —
        # без неё модель выдаёт NaN
        inputs = proc(wav, sampling_rate=16000, return_tensors="pt")
        with torch.no_grad():
            logits = model(inputs.input_values).logits[0]
        emissions = torch.log_softmax(logits, dim=-1).numpy()
    except Exception:
        return None
    if not np.isfinite(emissions).all():
        return None
    T, V = emissions.shape
    S = len(ids)
    if T < S:
        return None
    blank = 0
    # треллис: trellis[t, s] — «выдано s токенов, дошли до кадра t»
    trellis = np.full((T, S + 1), -1e9, dtype=np.float32)
    trellis[:, 0] = 0.0
    for t in range(T):
        trellis[t, 1] = emissions[t, blank]
        for s in range(1, S + 1):
            stay = trellis[t - 1, s] + emissions[t, ids[s - 1]]
            skip = trellis[t - 1, s - 1] + emissions[t, blank]
            trellis[t, s] = max(stay, skip)
    if trellis[T - 1, S] <= -1e8:
        return None
    frames = [0] * S
    t = T - 1
    s = S
    while s > 0 and t >= 0:
        if t == 0 or trellis[t, s] == trellis[t - 1, s] + emissions[t, ids[s - 1]]:
            frames[s - 1] = t
            s -= 1
        t -= 1
    frame = 0.02                      # 20 мс на кадр у wav2vec2
    out = []
    for i, tid in enumerate(ids):
        a = frames[i]
        b = a + 1
        sc = float(np.mean(emissions[a:b, tid]))
        bm = float(np.mean(emissions[a:b, blank]))
        try:
            txt = proc.tokenizer.decode([tid])
        except Exception:
            txt = ""
        out.append({"ch": txt, "start": round(a * frame, 2),
                    "end": round(b * frame, 2), "score": round(sc, 3),
                    "blank": round(bm, 3)})
    good = 0
    for o in out:
        # токен засчитан, если модель в его кадрах верит в него сильнее,
        # чем в пустоту (иначе его в звуке просто нет)
        if o["score"] > o["blank"] - 0.5 and o["score"] > -3.0:
            good += 1
    cov = good / float(len(out))
    mean_score = sum(max(o["score"], -8.0) for o in out) / float(len(out))
    if mean_score < -3.0:
        # выравнивание ненадёжное (короткий клип, шум) — лучше ничего,
        # чем ложный «кусок потерян»
        return None
    worst = None
    run = 0
    best = None
    for i, o in enumerate(out):
        if o["score"] <= o["blank"] - 0.5 or o["score"] < -3.0:
            run += 1
            if run >= 1 and (best is None or run > best[0]):
                best = (run, i - run + 1, i + 1)
        else:
            run = 0
    if best:
        _, a, b = best
        worst = {"start": out[a]["start"], "end": out[b - 1]["end"],
                 "text": "".join(o["ch"] for o in out[a:b])}
    return {"coverage": round(cov, 4), "tokens": out, "worst": worst,
            "reliable": True, "mean_score": round(mean_score, 3)}
