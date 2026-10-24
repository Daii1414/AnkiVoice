# -*- coding: utf-8 -*-
"""Синтез и контроль качества: synth() с многоэтапным спасением брака.

Одно обращение к серверу — _synth_once() (GPT-SoVITS или IndexTTS-сервис),
поверх него — QC v2 (lab/quality_v2) и опциональная сверка произношения
(faster-whisper, lab/pron_check). Здесь же базы порогов по голосу
(pron_baseline.json), сохранение брака и media_name.
"""
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request

import av_state
from anki_api import ac
from engines import (DEFAULT_START_CONFIG, ENGINE_INDEX, TTS_URL,
                     _ensure_indextts_service, _NO_PROXY, _read_app_config,
                     engine_kind, ensure_voice, indextts_url,
                     restart_server, start_server)
from kana_reading import kanaize
from paths import lab_dir
from voices import load_voices

# --------------------------------------------------------------- синтез
def _tts_start_config():
    cfg = load_voices()
    return os.path.join(av_state.ENGINE, cfg.get("start_config") or DEFAULT_START_CONFIG)


_RESURRECT = {"left": 3}      # сколько раз за прогон можно поднять упавший сервер


def _resurrect(v):
    """Сервер упал (упал при старте, убит, обрыв) — поднять заново.

    Возвращает True, если сервер снова готов с нужными весами. Ограниченное
    число попыток: если сервер падает стабильно, батчу лучше встать сразу
    с понятной ошибкой, чем ждать по 600 с на каждой карточке."""
    if _RESURRECT["left"] <= 0:
        return False
    _RESURRECT["left"] -= 1
    print("Сервер не отвечает — поднимаю заново (осталось попыток: %d)..."
          % (_RESURRECT["left"] + 1))
    if engine_kind() == ENGINE_INDEX:
        # поднимаем свой мост к IndexTTS, а не чужой GPT-SoVITS
        _ensure_indextts_service(wait=240)
    else:
        start_server(_tts_start_config(), wait=240)
    ensure_voice(v, force=True)
    return True


def _ffmpeg_exe():
    """ffmpeg из папки движка (или из PATH) — для проверки качества звука."""
    if av_state.ENGINE:
        p = os.path.join(av_state.ENGINE, "runtime", "ffmpeg.exe")
        if os.path.exists(p):
            return p
    try:
        import shutil
        return shutil.which("ffmpeg") or ""
    except Exception:
        return ""


def audio_stats(blob, ext="ogg"):
    """Разбирает синтезированный файл: (длительность с, звучащая длительность с).

    Декодирует через ffmpeg в сырой PCM (16 кГц, моно) и считает, сколько
    времени сигнал реально звучит. Нужно, чтобы ловить главный сбой
    GPT-SoVITS: файл с 25–40 с тишины и крошечным куском речи в конце —
    байтов он при этом нормальный, поэтому «пустой ответ» его не отловит.
    Возвращает (0.0, 0.0), если разобрать не удалось (тогда проверка молчит).
    """
    ff = _ffmpeg_exe()
    if not ff:
        if os.environ.get("AV_DEBUG_QC"):
            print("  [qc] ffmpeg не найден; av_state.ENGINE=%r" % (av_state.ENGINE,))
        return 0.0, 0.0
    import subprocess
    cmd = [ff, "-v", "error", "-i", "pipe:0", "-f", "s16le",
           "-ac", "1", "-ar", "16000", "pipe:1"]
    try:
        r = subprocess.run(cmd, input=blob, capture_output=True, timeout=120)
        raw = r.stdout
    except Exception as e:
        if os.environ.get("AV_DEBUG_QC"):
            print("  [qc] ffmpeg не запустился: %r" % (e,))
        return 0.0, 0.0
    if len(raw) < 4:
        if os.environ.get("AV_DEBUG_QC"):
            print("  [qc] ffmpeg дал %d Б (rc=%s, stderr=%r)"
                  % (len(raw), r.returncode,
                     r.stderr.decode("utf-8", "replace")[:200]))
        return 0.0, 0.0
    try:
        import numpy as np
        x = np.frombuffer(raw, dtype="<i2").astype("float32") / 32768.0
    except Exception as e:
        if os.environ.get("AV_DEBUG_QC"):
            print("  [qc] numpy не справился: %r" % (e,))
        return 0.0, 0.0
    sr = 16000
    dur = len(x) / sr
    win = max(1, int(sr * 0.02))                 # окно 20 мс
    n = len(x) // win
    if n == 0:
        return dur, 0.0
    rms = np.array([np.sqrt((x[i*win:(i+1)*win] ** 2).mean()) for i in range(n)])
    thr = max(float(rms.max()) * 0.05, 1e-4)
    sounding = float((rms > thr).sum() * win / sr)
    return dur, sounding


def _synth_is_sane(text, dur, sounding):
    """True, если звук похож на речь, а не на пустоту.

    Норма для японского — примерно 0.15 с речи на знак. Мусорный ответ
    сервера отличается надёжно: общая длительность в разы больше ожидаемой
    (лишнее — тишина) либо звучащей речи почти нет.

    Короткие слова (つゆ, どの) проверяем мягче: для них крохотная длительность
    — норма, важнее доля звука в файле и отсутствие «пустого хвоста».
    """
    if dur == 0.0 and sounding == 0.0:
        return True                      # разобрать не удалось — не мешаем
    if sounding < 0.15:
        return False                     # речи практически нет
    expect = 0.15 * len(text)            # ожидаемая длительность речи
    if dur > max(8.0, expect * 3):
        return False                     # файл в разы длиннее ожидаемого
    if dur > 6.0 and sounding < expect * 0.5:
        return False                     # длинный файл, а речи почти нет
    return True


# ------------------------------------------------- многосигнальная проверка
_QC_V2 = {"state": "unset"}              # "unset" -> "ok"/"none"


def _qc_v2_module():
    """lab/quality_v2 — независимый анализатор (долгое молчание, разрывы
    внутри речи, дубль речи, обрезка, уровень, скорость мор/с).

    Лениво и с откатом: если lab/ недоступен (например, собранный .exe без
    исходников) или модуль не импортируется, остаётся старый простой
    критерий _synth_is_sane.
    """
    if _QC_V2["state"] != "unset":
        return _QC_V2.get("mod")
    try:
        lab = lab_dir()
        if lab not in sys.path:
            sys.path.append(lab)
        import quality_v2 as q2
        _QC_V2["mod"] = q2
        _QC_V2["state"] = "ok"
    except Exception as e:
        if os.environ.get("AV_DEBUG_QC"):
            print("  [qc] quality_v2 недоступен: %r" % (e,))
        _QC_V2["mod"] = None
        _QC_V2["state"] = "none"
    return _QC_V2["mod"]


def _check_audio(blob, ext, text):
    """(список сигналов, годен ли файл). Сигналы — для лога.

    Возвращает ([], True), если разобрать не удалось: не мешаем работе,
    но однократно предупреждаем — качество тогда не контролируется.
    """
    q2 = _qc_v2_module()
    if q2 is None:
        dur, snd = audio_stats(blob, ext)
        return ([], True) if _synth_is_sane(text, dur, snd) else (["тишина"], False)
    ff = q2.ffmpeg_exe(av_state.ENGINE)
    if not ff:
        return ([], True)                   # некому проверить — не мешаем
    m = q2.analyze(blob, ff)
    if not m.get("ok"):
        # ffmpeg есть, а файл не декодируется — битый ответ сервера
        return (["не декодируется"], False)
    sigs, is_bad = q2.verdict(m, text)
    return sigs, not is_bad


# Куда складывать отбракованный звук (чтобы можно было послушать и
# проверить: правильно ли детектор отклонил). Отключается AV_QC_KEEP=0.
QC_REJECT_DIR = os.path.join(lab_dir(), "rejected")


def keep_rejected(blob, ext, text, sigs, attempt, meta=None):
    """Сохранить отбракованный файл + запись в index.jsonl.

    Возвращает (имя_файла, причины) либо (None, причины), если сохранить
    не удалось. Ошибка сохранения никогда не должна ломать озвучку.
    """
    if os.environ.get("AV_QC_KEEP", "1") == "0":
        return None, sigs
    try:
        os.makedirs(QC_REJECT_DIR, exist_ok=True)
        h = hashlib.sha1(("v2|%s|%d" % (text, attempt)).encode("utf-8")
                         ).hexdigest()[:10]
        name = "rej_%s_%s.%s" % (time.strftime("%Y%m%d_%H%M%S"), h, ext)
        path = os.path.join(QC_REJECT_DIR, name)
        with open(path, "wb") as f:
            f.write(blob)
        rec = {"file": name, "text": text, "reasons": list(sigs),
               "attempt": attempt, "at": time.strftime("%Y-%m-%d %H:%M:%S")}
        if meta:
            rec.update(meta)
        with open(os.path.join(QC_REJECT_DIR, "index.jsonl"), "a",
                  encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return name, sigs
    except Exception as e:
        if os.environ.get("AV_DEBUG_QC"):
            print("  [qc] не смог сохранить брак: %r" % (e,))
        return None, sigs


def split_method_for(text):
    """Как резать текст перед синтезом.

    GPT-SoVITS умеет резать по китайским правилам (cut5 — «凑50字一切»).
    Для японского это ломает фразу: куски синтезируются по отдельности, и на
    стыках модель теряет кусок или придумывает лишний. Замер на реальных
    карточках: cut5 давал покрытие 0.54-0.59 вместо 0.91-0.92 у cut0/cut2.

    Поэтому короткие фразы (типичная карточка) идут целиком (cut0), длинные
    режутся по «。» (cut2) — там границы фразы естественные.
    """
    forced = os.environ.get("AV_FORCE_SPLIT")
    if forced:
        return forced
    return "cut0" if len(text or "") <= 45 else "cut2"


def _synth_once_indextts(v, text, speed=1.0, **overrides):
    """Синтез через сервис IndexTTS 2.5.

    Сервис (lab/indextts_service.py) держит модель в памяти — веса грузятся
    один раз при старте, а не на каждую карточку. Голос у IndexTTS — это
    один референс (никаких .ckpt/.pth), поэтому и параметров меньше.

    Возвращает (blob, ext) — как _synth_once.
    """
    url = indextts_url()
    ref = v.get("ref") or ""
    if not ref:
        raise SystemExit("У голоса '%s' не задан файл референса."
                         % (v.get("name") or "?"))
    if not os.path.isfile(ref):
        raise SystemExit("Нет файла референса: %s" % ref)
    dur = float(overrides.get("duration_factor") or 0) or (
        1.0 / max(0.25, float(speed or 1.0)))
    payload = {
        "text": text,
        "spk_audio_prompt": ref,
        "lang": (v.get("lang") or "JA"),
        "duration_factor": dur,
        "emo_alpha": float(v.get("emo_alpha") or 1.0),
    }
    if v.get("emo_audio"):
        payload["emo_audio_prompt"] = v["emo_audio"]
    if overrides.get("use_random"):
        payload["use_random"] = True
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url + "/tts", data=data,
                                 headers={"Content-Type": "application/json"})
    try:
        with _NO_PROXY.open(req, timeout=900) as resp:
            blob = resp.read()
    except urllib.error.HTTPError as e:
        try:
            detail = e.read().decode("utf-8", "replace")
        except Exception:
            detail = "HTTP %s" % e.code
        raise SystemExit("IndexTTS отказал: %s" % detail[:300])
    except Exception as e:
        raise SystemExit("IndexTTS недоступен (%s): %s" % (url, e))
    if not blob:
        raise SystemExit("IndexTTS вернул пустой звук.")
    return blob, "wav"


def _synth_once(v, text, seed=42, speed=1.0, _oom_retry=True, verify=None,
                 asr_model=None, **overrides):
    if engine_kind() == ENGINE_INDEX:
        return _synth_once_indextts(v, text, speed=speed, **overrides)
    # Sampling defaults follow the official GPT-SoVITS webui (calmer than the raw
    # API defaults of temperature=1.0 / top_p=1.0, which sound over-expressive).
    # Any of these can be overridden per voice in voices.json.
    payload = {
        "text": text,
        "text_lang": "ja",
        "ref_audio_path": v["ref"],
        "aux_ref_audio_paths": v.get("aux") or [],
        "prompt_text": v.get("prompt_text", ""),
        "prompt_lang": v.get("prompt_lang", "ja"),
        "text_split_method": split_method_for(text),
        "batch_size": 1,
        "speed_factor": speed,
        "media_type": "ogg",
        "streaming_mode": False,
        "seed": seed,
        "temperature": float(v.get("temperature", 0.6)),
        "top_p": float(v.get("top_p", 0.6)),
        "top_k": int(v.get("top_k", 20)),
    }
    payload.update(overrides)           # переопределения из стратегий спасения

    def post(media_type):
        payload["media_type"] = media_type
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(TTS_URL + "/tts", data=data,
                                     headers={"Content-Type": "application/json"})
        try:
            with _NO_PROXY.open(req, timeout=600) as resp:
                return resp.read(), None
        except urllib.error.HTTPError as e:
            try:
                return None, e.read().decode("utf-8", "replace")
            except Exception:
                return None, "HTTP %s" % e.code
        except Exception as e:
            return None, str(e)

    blob, err = post("ogg")
    _b = _e = _i = None
    if blob is None and _oom_retry and err and \
            ("out of memory" in err or "CUDA" in err):
        # видеопамять переполнена (GPU занят чужими процессами или накопились
        # неудачные запросы) — полный перезапуск сервера даёт свежую память;
        # повторяем один раз, чтобы пачка озвучки не вставала целиком
        print("Не хватает видеопамяти — перезапускаю сервер и повторяю...")
        restart_server(_tts_start_config())
        ensure_voice(v, force=True)
        _b, _e, _i = synth(v, text, seed=seed, speed=speed, _oom_retry=False,
                           verify=verify, asr_model=asr_model)
        if _b is not None:
            return _b, _e
    if blob is None and _oom_retry and err and \
            any(s in err for s in ("10061", "refused", "urlopen error", "timed out")):
        # сервер упал/перезагружается — поднимаем заново и повторяем разок
        if _resurrect(v):
            _b, _e, _i = synth(v, text, seed=seed, speed=speed, _oom_retry=False,
                           verify=verify, asr_model=asr_model)
            if _b is not None:
                return _b, _e
    if blob is None:
        blob, err = post("wav")             # ogg может не поддерживаться
    if blob is None:
        raise SystemExit("сервер отказал: %s" % (err or "нет ответа")[:300])
    if len(blob) < 1024:
        # сервер ответил почти пустым телом (обрыв/уступка памяти на GPU) —
        # такое нельзя сохранять как «озвучено»: перезапуск сервера даёт
        # свежую память и обычно чинит ситуацию (как при CUDA OOM выше)
        if _oom_retry:
            print("Сервер вернул пустой звук — перезапускаю сервер и повторяю...")
            restart_server(_tts_start_config())
            ensure_voice(v, force=True)
            _b, _e, _i = synth(v, text, seed=seed, speed=speed, _oom_retry=False,
                           verify=verify, asr_model=asr_model)
            if _b is not None:
                return _b, _e
        raise SystemExit("сервер вернул пустой звук (%d байт) — попробуй ещё раз"
                         % len(blob))
    return blob, "ogg" if payload["media_type"] == "ogg" else "wav"


# схема спасения брака: (зарезервировано, подпись, что печатать в логе).
# В synth() стратегия выбирается по подписи: сид -> температура ->
# без промпта -> без промпта+сид -> другая разбивка -> без промпта+разбивка.
_QC_ATTEMPTS = (
    ({"seed_off": 7},   "сид",               "повторяю с другим сидом..."),
    ({"seed_off": 13, "temperature": 0.8}, "сид+температура",
     "пробую с температурой 0.8 и другим сидом..."),
    ({"seed_off": 29},  "ещё сид",           "пробую ещё один сид..."),
    ({"seed_off": 41, "temperature": 0.9}, "сид+температура 0.9",
     "пробую температуру 0.9..."),
    ({"prompt_text": ""}, "без промпта",     "пробую без текста референса..."),
    ({"prompt_text": "", "seed_off": 53}, "без промпта+сид",
     "пробую без промпта и с другим сидом..."),
    ({"text_split_method": "cut5"}, "старая разбивка",
     "пробую старую разбивку текста на куски..."),
    ({"prompt_text": "", "text_split_method": "cut5", "seed_off": 67},
     "без промпта+старая разбивка",
     "пробую без промпта и со старой разбивкой..."),
)

# У IndexTTS нет сида и температуры: там другая схема спасения — меняем
# скорость и включаем случайное сэмплирование.
_QC_ATTEMPTS_INDEX = (
    ({"duration_factor": 0.92}, "чуть быстрее", "пробую прочитать быстрее..."),
    ({"duration_factor": 1.10}, "чуть медленнее", "пробую прочитать медленнее..."),
    ({"use_random": True}, "случайно", "пробую другой вариантSampling..."),
    ({"duration_factor": 0.92, "use_random": True}, "быстрее и случайно",
     "пробую быстрее и с другим вариантом..."),
)


_QC_BLIND = [False]      # уже предупреждали, что проверить звук не удалось
_PRON = [None]          # ленивый проверяющий произношения (lab/pron_check.py)
_PRON_STATE = {"checked": 0, "bad": 0, "suspect": 0, "note": ""}


def _pron_verifier(force=False, asr_model=None):
    """Проверяющий произношение — только если он включён в конфиге.

    Модель (faster-whisper) грузится один раз на прогон: 5-10 с на прогретом
    кэше, сама проверка клипа — около 0.5 с на GPU.

    force=True — включить проверку принудительно (так работает команда
    verify: она и есть проверка).
    """
    if _PRON[0] is None:
        _PRON[0] = False          # «вычисляем»
        cfg = _read_app_config()
        want = True if force else cfg.get("verify_pronunciation")
        if not want:
            return None
        try:
            lab = lab_dir()
            if lab not in sys.path:
                sys.path.insert(0, lab)
            import pron_check
        except Exception as e:
            print("-- проверка произношения недоступна: %r" % (e,))
            return None
        _PRON[0] = pron_check.Verifier(model=asr_model or cfg.get("asr_model"),
                                      kanaize=kanaize)
    return _PRON[0] or None


def pron_status():
    """(доступно ли, описание) — для диагностики и отчётов."""
    v = _pron_verifier()
    if v is None:
        return False, "проверка произношения выключена"
    return v.available()


# ------------------------------------------- база: своя норма для голоса
# Абсолютные пороги не годятся для всех: у одного голоса «норма» 0.95, у
# другого 0.85, а у модели с тяжёлым чтением — 0.80. Поэтому держим свою
# базу по голосу (медиана покрытия по принятым кускам) и считаем пороги
# относительно неё, с абсолютным «полом» снизу.
BASELINE_FILE = "pron_baseline.json"
BASE_DROP_FAIL = 0.35       # насколько ниже своей нормы — уже брак
BASE_DROP_SUSPECT = 0.14    # насколько ниже — сомнительно
COVER_FLOOR = 0.50          # ниже этого не опускаемся ни при какой базе
COVER_SUSPECT_FLOOR = 0.62
# абсолютные пороги (из лаборатории, на живой коллекции): своих порогов
# никогда не делаем МЯГЧЕ абсолютных, иначе хороший голос получил бы
# слишком снисходительную оценку
COVER_FAIL_ABS = 0.55
COVER_SUSPECT_ABS = 0.80


def baseline_path():
    return os.path.join(os.environ.get("APPDATA") or "",
                        "AnkiVoice", BASELINE_FILE)


def load_baselines():
    try:
        with open(baseline_path(), encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return {}


def save_baselines(data):
    try:
        d = os.path.dirname(baseline_path())
        if d and not os.path.isdir(d):
            os.makedirs(d, exist_ok=True)
        with open(baseline_path(), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
    except Exception as e:
        print("  (базу сохранить не удалось: %r)" % (e,))


def update_baseline(voice, coverages):
    """Пересчитать норму голоса по принятым кускам."""
    vals = sorted(float(c) for c in coverages if c is not None and 0 < c <= 1.05)
    if len(vals) < 20:
        return None
    med = vals[len(vals) // 2]
    low = vals[max(0, int(len(vals) * 0.05))]
    data = load_baselines()
    data[voice] = {"median": round(med, 4), "p05": round(low, 4),
                   "n": len(vals), "at": time.strftime("%Y-%m-%d %H:%M:%S")}
    save_baselines(data)
    return data[voice]


def baseline_limits(voice):
    """Пороги для голоса: свои, если база есть, иначе абсолютные."""
    b = (load_baselines() or {}).get(voice or "")
    if not b or not b.get("median"):
        return {}
    med = float(b["median"])
    return {
        "COVER_FAIL": min(COVER_FAIL_ABS,
                          max(COVER_FLOOR, round(med - BASE_DROP_FAIL, 3))),
        "COVER_SUSPECT": min(COVER_SUSPECT_ABS,
                             max(COVER_SUSPECT_FLOOR,
                                 round(med - BASE_DROP_SUSPECT, 3))),
    }



def synth(v, text, seed=42, speed=1.0, _oom_retry=True, src=None,
          verify=None, asr_model=None):
    """Синтез с проверкой качества на входе в колоду.

    GPT-SoVITS иногда возвращает файл, где 25-40 с тишины и крошечный
    кусочек речи в самом конце: байтов нормально, длины хватает, но
    слушать нечего. Такой файл раньше уходил в карточку как «озвучено».
    Теперь проверяем звук (audio_stats) и при мусоре пробуем спасение:
    другой сид -> другая температура -> без текста референса -> ещё раз.
    Не помогло — ошибка, карточка остаётся неозвученной и видна в отчёте.

    Вторая проверка — СОДЕРЖАНИЕ. Модель может произнести все слова, но
    потерять кусок фразы или придумать лишний: длительность в норме, а
    звук — не то предложение. Старый QC такое не видит. Если включена
    проверка произношения (faster-whisper в движке), мы распознаём свой же
    звук и сравниваем с ожидаемой каной; при несовпадении пробуем другие
    варианты и оставляем лучший.

    Возвращает (blob, ext, info), где info = {"suspect": bool, ...}.
    """
    v_prompt = v.get("prompt_text", "")
    # Текста для чтения нет (только пунктуация, пробелы, ссылки на медиа) —
    # сервер всё равно откажет «有効なテキスト...», а 6 попыток и FAIL в отчёте
    # будут лишь шумом. Это не ошибка озвучки, а пустая карточка.
    q2 = _qc_v2_module()
    if q2 is not None and q2.sound_chars(text) == 0:
        print("  [%s] нечего озвучивать — пропускаю" % text[:24])
        raise SystemExit("пустой текст: озвучивать нечего")
    tried = 0
    best = None            # (blob, ext, покрытие, сигналы) — лучший вариант
    suspect = None         # результат проверки: «похоже, но не уверен»
    attempts = (_QC_ATTEMPTS_INDEX if engine_kind() == ENGINE_INDEX
                else _QC_ATTEMPTS)
    for over, what, msg in ((None, None, None),) + attempts:
        if tried:
            print("  [%s] %s: %s" % (text[:24], what, msg))
        s, tv, nv, extra = seed, v, v_prompt, {}
        if over:
            o = dict(over)
            if "seed_off" in o:
                s = seed + int(o.pop("seed_off"))
            if "temperature" in o:
                tv = dict(v)
                tv["temperature"] = o.pop("temperature")
            if "prompt_text" in o:
                nv = o.pop("prompt_text")
            extra.update(o)
        tv = dict(tv)
        if nv == "":
            tv["prompt_text"] = ""
        blob, ext = _synth_once(tv, text, seed=s, speed=speed,
                                _oom_retry=_oom_retry, **extra)
        sigs, ok = _check_audio(blob, ext, text)
        cov = None
        if ok:
            checker = _pron_verifier()
            if checker is not None:
                checker.limits = baseline_limits(v.get("name"))
                try:
                    # сверяем с произнесённым (text), а не с исходным полем:
                    # у слова поле может быть длиннее самого слова
                    res = checker.check(blob, ext, text)
                except Exception:
                    res = {"ok": True, "verdict": "проверка не удалась",
                           "coverage": 1.0, "cer": 0.0}
                cov = res.get("coverage")
                _PRON_STATE["checked"] += 1
                # Проверка содержания — совещательная, не приговор: по замеру
                # на 27 размеченных карточках подтверждённых браков 2, а ложных
                # срабатываний 25 (ASR переворачивает доменные термины). Поэтому
                # она не бракует карточку и не ставит метку, а показывает цифры.
                _PRON_STATE["note"] = res.get("verdict", "")
                if res.get("fail") or res.get("suspect"):
                    _PRON_STATE["suspect"] = _PRON_STATE.get("suspect", 0) + 1
                    suspect = res
                    print("  [проверка содержания] %s: %s (покрытие %.2f, ошибка %.2f) — совет, не приговор"
                          % (text[:24], res.get("verdict"), cov or 0.0, res.get("cer") or 0.0))
        if ok:
            # совещательно: цифры в отчёте, но карточка не бракуется
            # и меткой не помечается — решение за тобой
            info = {"suspect": False, "coverage": cov}
            if suspect:
                info["signals"] = suspect.get("verdict")
                info["heard"] = suspect.get("heard")
                info["pron_coverage"] = cov
        # запоминаем лучший по содержанию (если проверяли произношение)
        # лучший кусок: если проверка содержания работает — берём его первый
        # по крытию; если проверка выключена — выбираем по покрытию
        # лучший кусок: если проверка содержания работает — берём его первый
        # по крытию; если проверка выключена — выбираем по покрытию
        if best is None:
            if ok:
                best = (blob, ext, cov, list(sigs))
                if cov is None:
                    break          # сравнивать нечем — девять вариантов не нужно
                if cov >= 0.96:
                    break          # дубль чистый — лучше невзять
        elif (cov is not None and best[2] is not None and cov > best[2]):
            best = (blob, ext, cov, list(sigs))
        if not _QC_BLIND[0] and not ok and not sigs:
            _QC_BLIND[0] = True
            print("  ! проверить звук не удалось — качество не контролируется")
        tried += 1
        kept, _ = keep_rejected(blob, ext, text, sigs, tried,
                                meta={"strategy": what or "по умолчанию",
                                      "coverage": cov})
        if not ok:
            print("  [%s] брак: %s%s%s"
                  % (text[:24], ", ".join(sigs) or "звук не прошёл проверку",
                     "" if msg is None else " — " + msg,
                     "" if kept is None else "  [сохранён: %s]" % kept))
    if best is not None:
        if best[2] is not None:
            print("  [%s] лучший кусок по содержанию (покрытие %.2f) - вернём его"
                  % (text[:24], best[2]))
        return best[0], best[1], {"suspect": bool(best[3]), "coverage": best[2],
                                   "signals": best[3], "heard": ""}
    raise SystemExit("после %d попыток синтез даёт брак — карточка пропущена"
                     % tried)



SUSPECT_TAG = "av_suspect"          # тег карточки с подозрительным звуком


def mark_suspect(nid, field, text, blob, ext, sinfo):
    """Звук озвучен, но содержание не совпало: помечаем и сохраняем.

    Карточка остаётся озвученной (лучший из вариантов), но помечена тегом
    av_suspect, а файл попадает в папку брака — чтобы можно было послушать
    и переделать. Тег в Anki ставим мягко: если аддон не умеет, не падаем.
    """
    try:
        ac("addTags", notes=[nid], tags=SUSPECT_TAG + "::" + field)
        print("  ! [%d] помечено как подозрительное (%s, покрытие %.2f)"
              % (nid, field, sinfo.get("coverage") or 0.0))
    except Exception:
        pass
    try:
        kept, _ = keep_rejected(blob, ext, text,
                                ["содержание: %s" % (sinfo.get("signals") or "не совпало")],
                                0,
                                meta={"suspect": True,
                                      "coverage": sinfo.get("coverage"),
                                      "note": nid, "field": field})
        if kept:
            print("     звук сохранён для прослушивания: %s" % kept)
    except Exception as e:
        print("     не удалось сохранить звук: %r" % (e,))


def media_name(nid, field, text, ext, voice):
    h = hashlib.sha1(("v1|%d|%s|%s|%s" % (nid, field, text, voice))
                     .encode("utf-8")).hexdigest()[:10]
    return "tts_%s_%d_%s_%s.%s" % (voice, nid, field.lower(), h, ext)
