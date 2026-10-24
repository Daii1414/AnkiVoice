# -*- coding: utf-8 -*-
"""voice_pipeline.py — единый пайплайн озвучки колод Anki голосами GPT-SoVITS.

Автономный пайплайн: скрипт лежит в любой папке (например, в репозитории на
GitHub), а движок GPT-SoVITS может стоять где угодно. Папка движка ищется
в таком приоритете (первый найденный берётся):
  1. переменная окружения GPT_SOVITS_ROOT=C:\\...\\GPT-SoVITS
  2. файл gptsovits_path.txt рядом с этим скриптом (одна строка — путь)
  3. %APPDATA%\\AnkiVoice\\config.json  ->  "gptsovits_path"  (его пишет AnkiVoice.exe;
     старый путь %APPDATA%\\AnkiTTS\\config.json тоже читается)
  4. сама папка скрипта (если скрипт лежит внутри GPT-SoVITS — старое поведение)

Быстрый старт (движок уже настроен, см. выше):
  pipeline.bat                                        -> интерактивное меню
  pipeline.bat list
  pipeline.bat add --name sakura ^
      --gpt GPT_weights_v2Pro/Sakura-e15.ckpt ^
      --sovits SoVITS_weights_v2Pro/Sakura_e8_s368.pth ^
      --ref "C:\\...\\sakura.wav" --prompt-text "..."
  pipeline.bat make-deck --voice sakura --query "deck:Архитектура" --limit 20
  pipeline.bat voice --voice sakura --deck "Sakura" --mode both
  pipeline.bat check --deck "Sakura"
  pipeline.bat selftest

Что делает автоматически:
  * поднимает API-сервер GPT-SoVITS, если он не запущен;
  * переключает веса голоса на лету (при нехватке памяти — перезапуск и повтор);
  * переводит текст карточек в хирагану (Haqumei в контексте предложения;
    запасной ход — SudachiPy по словарю UniDic и pyopenjtalk), латиницу
    IEC/ISO/I形 -> катакана по буквам;
  * синтезирует слово и предложение, кладёт ogg в медиа Anki, пишет [sound:...] в поля;
  * проверяет результат (поля заполнены, файлы на месте).

Голоса хранятся в voices.json (рядом со скриптом). Референс обязан быть 3–10 секунд.
Относительные пути в voices.json (к весам и референсам) считаются от папки ДВИЖКА.
"""

import argparse
import base64
import hashlib
import html
import json
import os
import random
import re
import shutil
import unicodedata
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile

try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
try:
    if hasattr(sys.stdin, "reconfigure"):
        sys.stdin.reconfigure(encoding="utf-8")
except Exception:
    pass

# ------------------------------------------------------------------ константы
# CODE  — папка самого инструмента (этот скрипт, voices.json).
# ROOT  — корень репозитория (на уровень выше): там lab/ и bundled/.
# av_state.ENGINE — папка установленного GPT-SoVITS (runtime\python.exe, api_v2.py, веса).
# ------------------------------------------------- пути (app/paths.py)
from paths import (  # noqa: F401 — фасад
    CODE, ROOT, bundled, lab_dir,
)


# ------------------------------------------------- поля карточки (app/fields_config.py)
from fields_config import (  # noqa: F401 — фасад
    DEFAULT_FIELDS, audio_fields, resolve_fields,
)
import av_state
import engines

# ------------------------------------------------- движки (app/engines.py),
# голоса (app/voices.py): имена переэкспортируются для внешних потребителей.
from engines import (  # noqa: F401 — фасад
    DEFAULT_START_CONFIG,
    ENGINE_GPT,
    ENGINE_INDEX,
    INDEXTTS_DEFAULT_URL,
    TTS_URL,
    _BAD_ENGINES,
    _ensure_indextts_service,
    _get,
    _indextts_health,
    _is_engine,
    _norm,
    _read_app_config,
    _read_engine_gui_config,
    _read_engine_local_file,
    _resolved,
    _start_indextts_service,
    _wait_indextts,
    active_voice,
    apply_engine,
    cmd_indextts_server,
    engine_kind,
    ensure_voice,
    indextts_dir,
    indextts_url,
    port_pid,
    port_process_name,
    require_engine,
    resolve_engine,
    restart_server,
    set_active_voice,
    set_weights,
    start_server,
    tts_ready,
    wait_port,
)
from voices import (  # noqa: F401 — фасад
    ENGINE_LOCAL_FILE,
    VOICES_FILE,
    _epoch_of,
    _find_ref_for,
    _gpt_identity,
    _other_engine_dir,
    _pretty_name,
    _voice_file,
    get_voice,
    load_voices,
    ref_duration,
    save_voices,
    scan_engine_voices,
)

# движок резолвим сразу (не бросает исключений: нет движка — av_state.av_state.ENGINE
# останется None; все обращения к состоянию движка идут через av_state)
_resolved = engines.resolve_engine()
if _resolved:
    engines.apply_engine(_resolved)

# ------------------------------------------------------------ AnkiConnect
# С 1.9.2 живёт в app/anki_api.py; имена переэкспортируются, чтобы
# все внешние потребители (kana_stress, bench_rohan, тесты) работали
# как раньше: from voice_pipeline import kanaize, ac, plain, ...
from anki_api import (  # noqa: F401 — фасад
    ANKI_CONNECT, SOUND_TAG_RE, TAG_RE, _NO_PROXY,
    _chunks, ac, notes_info, plain,
)
def cmd_scan(args):
    engine = require_engine()
    found = scan_engine_voices(engine)
    cfg = load_voices()
    existing = cfg.setdefault("voices", {})
    known_gpt = {_gpt_identity(v.get("gpt", "")) for v in existing.values()}
    added = []
    skipped = []
    for item in found:
        # голос уже зарегистрирован (иначе ключей) — в т.ч. той же модели,
        # но с другой эпохой: дубликаты с пустым референсом не нужны
        if _gpt_identity(item["gpt"]) in known_gpt:
            continue
        # без референса голос не озвучить: не добавляем в список
        if not (item.get("ref") or "").strip():
            skipped.append(item["name"])
            continue
        existing[item["name"]] = {
            "display": item["display"],
            "gpt": item["gpt"],
            "sovits": item["sovits"],
            "ref": item["ref"],
            "aux": [],
            "prompt_text": "",
            "prompt_lang": "ja",
        }
        known_gpt.add(_gpt_identity(item["gpt"]))
        added.append(item["name"])
    if added and args.apply:
        save_voices(cfg)
    if args.json:
        print(json.dumps({"found": len(found), "added": added,
                          "apply": bool(args.apply)}, ensure_ascii=False))
    else:
        print("Найдено пар весов: %d" % len(found))
        for it in found:
            mark = "+" if it["name"] in added else "="
            print("  %s %-22s %-24s ref=%s"
                  % (mark, it["name"], it["display"], it["ref"] or "—"))
        if skipped:
            print("Пропущены (нет референса): %s" % ", ".join(skipped))
            print("  Их можно добавить вручную на вкладке «Голос».")
        if added and not args.apply:
            print("Новые голоса НЕ записаны — запусти с --apply.")
        elif added:
            print("Добавлено в voices.json: %s" % ", ".join(added))
    return True


# ------------------------------------------------- чтение (app/kana_reading.py)
# Чтение иероглифов и разбор фуриганы живут в kana_reading.py; здесь
# имена переэкспортируются ради внешних потребителей.
from kana_reading import (  # noqa: F401 - фасад
    CORE_HELPER,
    KANJI_RE,
    LATIN,
    PYRUNTIME_DIR,
    PYRUNTIME_PY,
    PYRUNTIME_ZIP,
    SUDACHI_HELPER,
    _CORE_LOCAL,
    _CORE_PROC,
    _CoreLocal,
    _CoreProc,
    _KANA_CACHE,
    _KATA_EXTRA,
    _KATA_ONLY,
    _KEEP_KATA,
    _SEG_RE,
    _SUDACHI,
    _SUDACHI_PROC,
    _SudachiProc,
    _VOICED,
    _base_reading,
    _core_local,
    _core_warned,
    _doubled_okurigana,
    _ensure_pyruntime,
    _g2p_core,
    _g2p_warned,
    _kana_norm,
    _normalize_furigana,
    _parse_furigana,
    _pyopenjtalk_g2p,
    _reading_covers_word,
    _segments,
    _span_drift,
    _sudachi_warned,
    core_client,
    expression_inject_pair,
    furiga_pair,
    g2p_kana,
    inject_reading,
    inject_reading_lenient,
    kanaize,
    kanaize_card,
    kanaize_from_fields,
    kata2hira,
    latin2kana,
    normalize_text,
    replace_term,
    sudachi_client,
    sudachi_local,
)
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


# ----------------------------------------------------- операции с колодами
def word_text(note, word_src, reading=""):
    """Текст слова из поля word_src.

    word_src == 'Expression' учитывает режим источника reading:
      * "off"/"" — написание без разметки, движок читает его само;
      * имя поля — готовое чтение строго из этого поля (простое чтение
        либо фуриганная разметка); поле пустое — как при off.
    Для произвольного поля word_src — просто текст поля."""
    if word_src == "Expression":
        if reading and reading != "off":
            v = plain(note["fields"].get(reading, {}).get("value", ""))
            if "[" in v:                      # поле с фуриганой -> кана целиком
                _, v = furiga_pair(v)
                v = (v or "").strip()
            if v:
                return v
        return re.sub(r"\[[^\[\]]*\]", "",
                      plain(note["fields"].get("Expression", {})
                            .get("value", ""))).strip()
    return plain(note["fields"].get(word_src, {}).get("value", ""), strip_media=True)


def _speakable(text):
    """Есть ли в тексте хотя бы один звуковой знак.

    «！？…» или поле, состоящее из ссылок на медиа, — синтезировать нечего:
    сервер откажет, а 6 попыток и FAIL в отчёте будут лишь шумом. Если
    quality_v2 недоступен (собранный .exe), возвращаем True — не мешаем.
    """
    q2 = _qc_v2_module()
    if q2 is None:
        return True
    return q2.sound_chars(text) > 0


def term_has_latin(note, fields):
    """Есть ли в термине латиница или цифры (3D, PLATEAU, BIM/CIM, 2.0).

    Такие термины движок читает лучше сам: собственная транслитерация
    («3D» -> «すりーでぃー») звучит хуже и вводит модель в цикл
    (замер: 96 секунд и покрытие 0.89 против 4 секунд и 1.00).
    """
    f = (note.get("fields") or {})
    for name in (fields.get("furigana_src") or "ExpressionFurigana",
                 fields.get("word_src") or "Expression"):
        val = plain(f.get(name, {}).get("value", ""))
        if "[" in val:
            val = val.split("[", 1)[0]
        if re.search(r"[0-9A-Za-z]", val):
            return True
    return False


def reading_mode(fields, note, reading=""):
    """Режим чтения для этой карточки.

    Замер на карточках с редкими кандзи-терминами (движок IndexTTS 2.5):
    с подстановкой чтения из фуриганы покрытие распознавания выше
    (0.92-0.97 против 0.88-0.90 у «только кандзи»), поэтому «авто» и для
    IndexTTS берёт чтение из фуриганы. Синтаксис-аннотация самого IndexTTS
    (<base|reading>) примерили — хуже (0.64-0.92), в конвейер не вошёл.

    * "asis" — всегда кандзи, движок читает сам;
    * "mix" — термин всегда по фуригане;
    * пусто (авто) — если в поле с фуриганой что-то есть, берём термин — по фуригане; если поля пустое — всё кандзи.

    Решение принимается на каждую карточку: у чей есть фуригана — чтение по фуригане, а где ее нет — движок читает кандзи.

    Режим переключается на карточку: у других колод фуригана есть — смешание кандзи, а где пусто — кандзи.
    """
    r = (reading or "").strip().lower()
    if r == "asis":
        return "asis"
    if r == "mix":
        return "mix"
    name = fields.get("furigana_src") or "ExpressionFurigana"
    val = plain(((note.get("fields") or {}).get(name) or {}).get("value", ""))
    return "mix" if val.strip() else "asis"


def build_jobs(notes, mode, force, fields=None):
    fields = fields or DEFAULT_FIELDS
    jobs = []
    for n in notes:
        f = n["fields"]

        def tgt(name):
            return plain(f.get(name, {}).get("value", ""))

        def tgt_text(name):
            # текст на синтез: [sound:...] внутри поля вырезаем
            return plain(f.get(name, {}).get("value", ""), strip_media=True)

        src_text = ""
        # Режим для этой карточки. Термины с латиницей или цифрами
        # (3D, PLATEAU, BIM/CIM, 2.0) оставляем как есть: собственная
        # транслитерация («3D» -> «すりーでぃー») читается хуже и вводит
        # модель в цикл — замер: 96 с и покрытие 0.89 против 4 с и 1.00.
        rmode = reading_mode(fields, n, fields.get("reading", ""))
        if rmode == "mix" and term_has_latin(n, fields):
            rmode = "asis"
        if mode in ("sentence", "both"):
            text = tgt_text(fields["sentence_src"])
            if text and (force or not tgt(fields["sentence_audio"])):
                # режим «как есть»: движок получает кандзи и читает сам —
                # без подстановки чтения из фуриганы
                if rmode == "mix":
                    # кандзи + чтение термина из фуриганы:
                    # обычный текст читается в кандзи (контекст сохраняется),
                    # а термин читается ровно по фуригане
                    text = inject_reading_lenient(
                        text, n,
                        reading_field=fields.get("furigana_src", "ExpressionFurigana"))
                else:
                    # «только кандзи»: текст остаётся кандзи,
                    # движок читает сам в контексте
                    pass
                src_text = text          # исходный текст: во что будет прознесено
                if not _speakable(text):        # только пунктуация и медиа
                    continue
                jobs.append((n["noteId"], fields["sentence_audio"], text, src_text))
        if mode in ("expression", "both"):
            asis = rmode == "asis"
            text = word_text(n, fields["word_src"],
                             reading=("off" if asis else fields.get("reading", "")))
            src_text = text           # исходник: в нём ещё есть латиница
            if text and (force or not tgt(fields["word_audio"])):
                # Фуригана для основного слова — из настраиваемого поля
                furigana = plain(f.get(fields.get("furigana_src", "ExpressionFurigana"),
                                       {}).get("value", ""))
                expression = plain(f.get(fields.get("word_src", "Expression"),
                                         {}).get("value", ""))
                if not asis:
                    text = kanaize_card(text, expression=expression, furigana=furigana)
                if not _speakable(text):        # только пунктуация и медиа
                    continue
                jobs.append((n["noteId"], fields["word_audio"], text, src_text))
    return jobs


def _plural(n, one, few, many):
    """Правильное окончание: 1 операция, 2 операции, 5 операций."""
    n = abs(int(n))
    if n % 10 == 1 and n % 100 != 11:
        return one
    if 2 <= n % 10 <= 4 and not (12 <= n % 100 <= 14):
        return few
    return many


def _human_dur(sec):
    """Секунды -> «45 с» / «7 мин»."""
    sec = int(max(0, sec))
    if sec < 90:
        return "%d с" % sec
    return "%d мин" % round(sec / 60)


# ------------------------------------------------- итог последнего прогона
# last_run.json — мост между прогоном и «Перепробовать неудашиеся» / CLI
# voice --retry: сюда падают счётчики и список неудавшихся карточек.
LAST_RUN_FILE = os.path.join(os.environ.get("APPDATA") or "",
                             "AnkiVoice", "last_run.json")


def _write_last_run(info):
    try:
        d = os.path.dirname(LAST_RUN_FILE)
        if d and not os.path.isdir(d):
            os.makedirs(d, exist_ok=True)
        tmp = LAST_RUN_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(info, f, ensure_ascii=False, indent=1)
        os.replace(tmp, LAST_RUN_FILE)
    except Exception as e:
        print("  (итог прогона сохранить не удалось: %r)" % (e,))


def read_last_run():
    """Итог последнего прогона или {}."""
    try:
        with open(LAST_RUN_FILE, encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return {}


# --------------------------------- манифест озвученного (для «только изменённые»)
# {nid: {поле: хэш(голос, seed, speed, итоговый текст)}}. Пишется после
# каждого успешного прогона; по нему работает voice --changed: перезапись
# трогает только карточки, чей текст или голос изменились с прошлого раза.
VOICED_MANIFEST_FILE = os.path.join(os.environ.get("APPDATA") or "",
                                    "AnkiVoice", "voiced_manifest.json")


def load_voiced_manifest():
    try:
        with open(VOICED_MANIFEST_FILE, encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return {}


def save_voiced_manifest(m):
    try:
        d = os.path.dirname(VOICED_MANIFEST_FILE)
        if d and not os.path.isdir(d):
            os.makedirs(d, exist_ok=True)
        tmp = VOICED_MANIFEST_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(m, f, ensure_ascii=False, indent=1)
        os.replace(tmp, VOICED_MANIFEST_FILE)
    except Exception as e:
        print("  (манифест озвученного сохранить не удалось: %r)" % (e,))


def _audio_hash(voice_name, seed, speed, text):
    """Хэш того, что определяет звук: голос + сэмпл + скорость + текст."""
    return hashlib.sha1(("v1|%s|%s|%s|%s"
                         % (voice_name, seed, speed, text))
                        .encode("utf-8")).hexdigest()


def _filter_changed_jobs(jobs, notes, fields, manifest, voice_by_nid,
                         seed=42, speed=1.0):
    """«Пересобрать только изменённые»: оставить операции, чей звук изменился.

    Операция пропускается, если хэш (голос, seed, speed, итоговый текст)
    совпадает с манифестом И поле карточки до сих пор озвучено. Чистая
    функция — тестируется без Anki. Возвращает (kept, skipped).
    """
    has_audio = {}
    for n in notes:
        for fname in audio_fields(fields):
            val = plain((n.get("fields") or {}).get(fname, {})
                        .get("value", ""))
            has_audio[(n["noteId"], fname)] = bool(val)
    kept, skipped = [], 0
    for nid, field, text, src in jobs:
        vname = voice_by_nid.get(nid) or ""
        h = _audio_hash(vname, seed, speed, text)
        m = manifest.get(str(nid)) or {}
        if m.get(field) == h and has_audio.get((nid, field)):
            skipped += 1
            continue
        kept.append((nid, field, text, src))
    return kept, skipped


def assign_voices(nids, voice_names, seed=42, prior=None):
    """Случайно распределить карточки между голосами ансамбля.

    prior: {nid: голос} — карточки, уже озвученные одним из выбранных
    голосов (тег av_voice::имя), сохраняют его: частая перезвонка части
    колоды не меняет голос у уже озвученного.
    Детерминировано при фиксированном seed — тот же набор карточек
    даёт то же распределение.
    """
    rng = random.Random(seed)
    names = list(voice_names)
    out = {}
    for nid in nids:
        v = (prior or {}).get(nid)
        out[nid] = v if v in names else rng.choice(names)
    return out


def _mode_title(mode):
    """Режим озвучки по-человечески."""
    return {"both": "слово + предложение", "sentence": "только предложение",
            "expression": "только слово"}.get(mode, mode)


def _field_title(field, fields):
    """Человеческое название поля звука вместо 'sentence_audio'."""
    fields = fields or DEFAULT_FIELDS
    if field == fields.get("sentence_audio"):
        return "звук предложения"
    if field == fields.get("word_audio"):
        return "звук слова"
    return field


def voice_notes(ids, voice_name, mode="both", force=False, seed=42, speed=1.0,
                fields=None, verify=None, asr_model=None, extra_voices=None,
                only_changed=False):
    """Озвучить карточки.

    Голосов может быть несколько (extra_voices): тогда карточки случайно
    распределяются между ними (assign_voices) и озвучиваются ПАРТИЯМИ —
    веса каждого голоса грузятся один раз за прогон, а в колоде голоса
    чередуются максимально случайно. Карточка с тегом av_voice::имя
    сохраняет свой прежний голос.
    Успешно озвученным карточкам ставится тег av_voiced — по нему работает
    voice --new. Итог прогона пишется в last_run.json — по нему работает
    voice --retry. Манифест озвученного (voiced_manifest.json) обновляется
    после каждого прогона; only_changed=True («Пересобрать только
    изменённые») пропускает операции, чей голос/текст не изменились.
    """
    names = [voice_name]
    for n in (extra_voices or []):
        n = (n or "").strip()
        if n and n not in names:
            names.append(n)
    voices = {n: get_voice(n) for n in names}
    notes = notes_info(ids)
    jobs = build_jobs(notes, mode, force, fields=fields)
    if not jobs:
        print("Озвучивать нечего: у выбранных карточек уже есть звук "
              "(или пустой текст). Переозвучивай ключом --force "
              "(в интерфейсе — «Пересобрать всё заново»).")
        return 0, 0
    main_v = voices[names[0]]
    if len(names) > 1:
        prior = {}
        for n in names:
            try:
                for i in ac("findNotes", query='tag:"av_voice::%s"' % n):
                    prior[i] = n
            except Exception:
                pass
        assign = assign_voices({j[0] for j in jobs}, names, seed=seed,
                               prior=prior)
        print("Ансамбль: %s. Карточки распределены случайно, озвучка "
              "партиями — веса переключатся %d %s."
              % (", ".join(names), len(names),
                 _plural(len(names), "раз", "раза", "раз")))
        for n in names:
            cnt = sum(1 for v in assign.values() if v == n)
            print("  «%s»: %d %s" % (n, cnt,
                                     _plural(cnt, "карточка", "карточки",
                                             "карточек")))
    else:
        assign = {j[0]: names[0] for j in jobs}
    if only_changed:
        jobs, skipped_same = _filter_changed_jobs(
            jobs, notes, fields, load_voiced_manifest(), assign,
            seed=seed, speed=speed)
        if skipped_same:
            print("Без изменений с прошлой озвучки: %d %s — пропускаю."
                  % (skipped_same, _plural(skipped_same, "операция",
                                           "операции", "операций")))
        if not jobs:
            print("Пересобирать нечего: тексты и голоса всех операций "
                  "совпадают с прошлой озвучкой.")
            return 0, 0
    ncards = len({j[0] for j in jobs})
    print("К озвучке: %d %s в %d %s (голос «%s», режим: %s)"
          % (len(jobs), _plural(len(jobs), "операция", "операции", "операций"),
             ncards, _plural(ncards, "карточке", "карточках", "карточках"),
             main_v.get("display") or main_v["name"], _mode_title(mode)))
    done, failed = 0, 0
    failed_jobs = []
    recs = []              # записи для отчёта run_*.md
    voiced_fields = {}     # nid -> {успешно записанные поля этого прогона}
    cache = {}             # ключ включает голос: один текст у двух голосов
    t0 = time.time()       # — это два разных звука
    total = len(jobs)
    # партии по голосам, внутри партии — исходный порядок карточек
    ordered = []
    for n in names:
        ordered.extend(j for j in jobs if assign[j[0]] == n)
    v = None
    v_cur = None
    for i, (nid, field, text, src_text) in enumerate(ordered, 1):
        name = assign[nid]
        if name != v_cur:
            v = voices[name]
            v_cur = name
            ensure_voice(v)
        # ETA по фактической скорости прогона (после первых операций)
        eta = ""
        if i > 1:
            elapsed = time.time() - t0
            if elapsed > 5:
                eta = " · осталось ~%s" % _human_dur(
                    (total - i + 1) * elapsed / (i - 1))
        print("Карточка %d из %d%s — %s: %s"
              % (i, total, eta, _field_title(field, fields), text[:40]))
        try:
            key = (name, text, seed, speed)
            if key not in cache:
                # содержание сверяем только у предложения: изолированное
                # слово распознаётся ненадёжно (см. замер на 300 словах)
                content_check = bool(verify) and (
                    field == fields.get("sentence_audio"))
                cache[key] = synth(v, text, seed=seed, speed=speed,
                                   src=src_text, verify=content_check,
                                   asr_model=asr_model)
                time.sleep(0.2)
            blob, ext, sinfo = cache[key]
            fname = media_name(nid, field, text, ext, v["name"])
            stored = ac("storeMediaFile", filename=fname, overwrite=True,
                        data=base64.b64encode(blob).decode("ascii"))
            if stored != fname:
                fname = stored
            ac("updateNoteFields", note={"id": nid, "fields": {field: "[sound:%s]" % fname}})
            done += 1
            voiced_fields.setdefault(nid, set()).add(field)
            recs.append({"nid": nid, "field": field, "voice": name,
                         "status": "OK", "text": text})
            print("OK   [%d] %-16s %s (%s, %.0f КБ)"
                  % (nid, _field_title(field, fields), text[:40], ext,
                     len(blob) / 1024))
            # проверка содержания больше ничего не решает: метку снимаем,
            # решение принимаешь ты (колода «Брак» и вердикты в ней)
            try:
                ac("removeTags", notes=[nid], tags="av_suspect::" + field)
            except Exception:
                pass
        except SystemExit as e:
            failed += 1
            failed_jobs.append((nid, field))
            recs.append({"nid": nid, "field": field, "voice": name,
                         "status": "FAIL", "text": text, "error": str(e)})
            print("FAIL [%d] %s: %s" % (nid, field, e))
        except Exception as e:
            failed += 1
            failed_jobs.append((nid, field))
            msg = str(e)
            if "editor" in msg.lower():
                msg += "  <- закой карточку в редакторе Anki"
            recs.append({"nid": nid, "field": field, "voice": name,
                         "status": "FAIL", "text": text, "error": msg})
            print("FAIL [%d] %s: %s" % (nid, field, msg))
    # теги проставляем пачкой и только ПОЛНОСТЬЮ успешным карточкам этого
    # прогона: у карточки с одной неудавшейся операцией av_voiced не будет —
    # следующий voice --new её подхватит
    all_fields = {}
    for nid, field, _t, _s in jobs:
        all_fields.setdefault(nid, set()).add(field)
    ok_cards = sorted(nid for nid, fl in voiced_fields.items()
                      if all_fields.get(nid) and fl >= all_fields[nid])
    for tags, card_ids in (("av_voiced", ok_cards),):
        for chunk in _chunks(card_ids, 400):
            try:
                ac("addTags", notes=chunk, tags=tags)
            except Exception as e:
                print("  (тег %s проставить не удалось: %s)" % (tags, e))
    for n in names:
        ids_n = [nid for nid in ok_cards if assign.get(nid) == n]
        for chunk in _chunks(ids_n, 400):
            try:
                ac("addTags", notes=chunk, tags="av_voice::" + n)
            except Exception:
                pass
    extra = ""
    if _PRON_STATE.get("checked"):
        extra = (" | произношение проверено: %d, подозрительных: %d, брака: %d"
                 % (_PRON_STATE["checked"], _PRON_STATE.get("suspect", 0),
                    _PRON_STATE.get("bad", 0)))
    print("\nГотово: %d, ошибок: %d%s" % (done, failed, extra))

    # манифест озвученного: обновляем по УСПЕШНЫМ операциям этого прогона,
    # чтобы «Пересобрать только изменённые» знало, что уже звучит так же
    manifest = load_voiced_manifest()
    for nid, field, text, _src in jobs:
        if field not in voiced_fields.get(nid, ()):
            continue
        m = manifest.setdefault(str(nid), {})
        m[field] = _audio_hash(assign.get(nid) or names[0], seed, speed, text)
    save_voiced_manifest(manifest)

    # человекочитаемый отчёт прогона
    try:
        rep_dir = os.path.join(os.environ.get("APPDATA") or "",
                               "AnkiVoice", "reports")
        os.makedirs(rep_dir, exist_ok=True)
        rp = os.path.join(rep_dir, "run_%s.md" % time.strftime("%Y%m%d_%H%M%S"))
        with open(rp, "w", encoding="utf-8") as f:
            f.write("# Прогон %s\n\n" % time.strftime("%Y-%m-%d %H:%M:%S"))
            f.write("Голос(а): %s | режим: %s | готово: %d, ошибок: %d\n\n"
                    % (", ".join("`%s`" % n for n in names),
                       _mode_title(mode), done, failed))
            f.write("| # | карточка | поле | голос | статус | текст | ошибка |\n")
            f.write("|---|---|---|---|---|---|---|\n")
            for i, r in enumerate(recs, 1):
                f.write("| %d | %d | %s | %s | %s | %s | %s |\n"
                        % (i, r["nid"], _field_title(r["field"], fields),
                           r["voice"], r["status"],
                           (r["text"] or "").replace("|", "\|")[:60],
                           (r.get("error") or "").replace("|", "\|")[:80]))
        print("Отчёт: %s" % rp)
    except Exception as e:
        print("  (отчёт сохранить не удалось: %r)" % (e,))
    _write_last_run({
        "voice": names[0] if len(names) == 1 else names,
        "mode": mode,
        "fields": fields or {},
        "done": done,
        "failed": failed,
        "failed_ids": sorted({nid for nid, _f in failed_jobs}),
        "ok_cards": ok_cards,
        "at": time.strftime("%Y-%m-%d %H:%M:%S"),
    })
    return done, failed


def clone_cards(query, to_deck, limit=None, tag=None, force=False, fields=None):
    cfg = fields or DEFAULT_FIELDS
    afs = set(audio_fields(cfg))
    existing = ac("findNotes", query='deck:"%s"' % to_deck)
    if existing and not force:
        raise SystemExit("Колода '%s' уже содержит %d карточек — дозови командой voice "
                         "или добавь --force, чтобы клонировать ещё набор."
                         % (to_deck, len(existing)))
    ids = ac("findNotes", query=query)
    if limit:
        ids = ids[:limit]
    if not ids:
        raise SystemExit("По запросу '%s' ничего не найдено." % query)
    ac("createDeck", deck=to_deck)
    created = []
    for n in notes_info(ids):
        nfields = {}
        for k, val in n["fields"].items():
            nfields[k] = "" if k in afs else val["value"]
        tags = list(n.get("tags") or [])
        if tag and tag not in tags:
            tags.append(tag)
        nid = ac("addNote", note={
            "deckName": to_deck, "modelName": n["modelName"], "fields": nfields,
            "options": {"allowDuplicate": True, "duplicateScope": "deck"},
            "tags": tags,
        })
        created.append(nid)
    print("Склонировано в '%s': %d карточек." % (to_deck, len(created)))
    return created


def check_deck(deck, fields=None, verify_files=True):
    """verify_files=False — быстрая проверка (только поля, без скачивания
    аудиофайлов из Anki; на больших колодах это десятки МБ и минуты)."""
    cfg = fields or DEFAULT_FIELDS
    afs = audio_fields(cfg)
    ids = ac("findNotes", query='deck:"%s"' % deck)
    if not ids:
        print("Колода '%s' не найдена или пуста (опечатка в имени?)." % deck)
        return False
    ok, problems = 0, []
    for n in notes_info(ids):
        expr = plain(n["fields"].get(cfg["word_src"], {}).get("value", ""))
        bad = []
        for fld in afs:
            tag = plain(n["fields"].get(fld, {}).get("value", ""))
            m = re.search(r"\[sound:([^\]]+)\]", tag)
            if not m:
                bad.append("%s пусто" % fld)
            elif verify_files and not ac("retrieveMediaFile", filename=m.group(1)):
                bad.append("%s: файл %s пропал" % (fld, m.group(1)))
        if bad:
            problems.append((n["noteId"], expr, "; ".join(bad)))
        else:
            ok += 1
    print("Колода '%s': %d карточек, из них полностью готово: %d"
          % (deck, len(ids), ok))
    for nid, expr, msg in problems:
        print("  ПРОБЛЕМА [%d] %s: %s" % (nid, expr, msg))
    return len(problems) == 0


# --------------------------------------------------------- один экземпляр
_LOCK_HANDLE = None


def acquire_lock():
    """Один экземпляр пайплайна.

    Два параллельных запуска дерутся за веса и перезапуск сервера — второй
    получает понятную ошибку вместо тихой порчи звука. Блокировка снимается
    сама при выходе процесса (закрытие файла)."""
    global _LOCK_HANDLE
    require_engine()
    lockp = os.path.join(av_state.ENGINE, "logs", "pipeline.lock")
    os.makedirs(os.path.dirname(lockp), exist_ok=True)
    f = open(lockp, "a+")
    try:
        import msvcrt
        msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        f.close()
        raise SystemExit(
            "Пайплайн уже запущен другим процессом (%s).\n"
            "Дождись его завершения (или убой зависший процесс)." % lockp)
    _LOCK_HANDLE = f


# --------------------------------------------------------------- команды
def ask(prompt, default=None):
    suffix = " [%s]" % default if default else ""
    v = input(prompt + suffix + ": ").strip()
    return v or (default or "")


def cmd_list(args=None):
    cfg = load_voices()
    if not cfg["voices"]:
        print("Голосов пока нет. Добавь: voice_pipeline.py add ...")
        return
    print("Голоса (по умолчанию: %s):" % (cfg.get("default_voice") or "—"))
    for name, v in sorted(cfg["voices"].items()):
        gpt_ok = os.path.exists(v["gpt"]) if os.path.isabs(v.get("gpt", "")) else \
            os.path.exists(os.path.join(av_state.ENGINE, v.get("gpt", "")))
        sov_ok = os.path.exists(v["sovits"]) if os.path.isabs(v.get("sovits", "")) else \
            os.path.exists(os.path.join(av_state.ENGINE, v.get("sovits", "")))
        ref = v["ref"] if os.path.isabs(v.get("ref", "")) else os.path.join(av_state.ENGINE, v.get("ref", ""))
        dur = ref_duration(ref)
        dur_s = ("%.1f с" % dur) if dur else ("НЕ НАЙДЕН" if not os.path.exists(ref) else "? с")
        flags = []
        if not gpt_ok:
            flags.append("нет GPT-весов")
        if not sov_ok:
            flags.append("нет SoVITS-весов")
        if dur and not (3.0 <= dur <= 10.0):
            flags.append("референс вне 3–10 с!")
        print("  %-12s %-14s референс: %-8s %s"
              % (name, v.get("display", ""), dur_s, ("  !! " + ", ".join(flags)) if flags else "ok"))


def cmd_add(args):
    cfg = load_voices()
    if args.name in cfg["voices"] and not args.force:
        raise SystemExit("Голос '%s' уже есть. --force — перезаписать." % args.name)
    for path, what in ((args.gpt, "GPT-веса"), (args.sovits, "SoVITS-веса"), (args.ref, "референс")):
        if not os.path.exists(path):
            raise SystemExit("Не найден файл %s: %s" % (what, path))
    dur = ref_duration(args.ref)
    if dur is not None and not (3.0 <= dur <= 10.0):
        raise SystemExit("Референс %.1f с — API требует 3–10 с. Вырежи другой кусок." % dur)
    cfg["voices"][args.name] = {
        "display": args.display or args.name,
        "gpt": os.path.relpath(args.gpt, av_state.ENGINE) if os.path.abspath(args.gpt).startswith(av_state.ENGINE) else args.gpt,
        "sovits": os.path.relpath(args.sovits, av_state.ENGINE) if os.path.abspath(args.sovits).startswith(av_state.ENGINE) else args.sovits,
        "ref": os.path.relpath(args.ref, av_state.ENGINE) if os.path.abspath(args.ref).startswith(av_state.ENGINE) else args.ref,
        "aux": args.aux or [],
        "prompt_text": args.prompt_text,
        "prompt_lang": args.prompt_lang,
    }
    if not cfg.get("default_voice"):
        cfg["default_voice"] = args.name
    save_voices(cfg)
    print("Голос '%s' добавлен в voices.json." % args.name)


def cmd_server(args):
    """Поднять api_v2 и выйти, не загружая голос.

    Нужен мастеру первого запуска: сервер можно подготовить отдельно,
    а тестовую фразу синтезировать следующим шагом.
    """
    start_server(_tts_start_config(), wait=args.wait)
    print("Сервер GPT-SoVITS готов.")


def cmd_serve(args):
    ensure_voice(get_voice(args.voice), force=args.force)
    print("Сервер работает с голосом '%s'." % args.voice)


def cmd_test(args):
    v = get_voice(args.voice)
    ensure_voice(v)
    text = kanaize(args.text)
    print("Текст: %s\nКиана: %s" % (args.text, text))
    blob, ext, _sinfo = synth(v, text, seed=args.seed, speed=args.speed)
    out = os.path.join(CODE, "test_%s.%s" % (v["name"], ext))
    with open(out, "wb") as f:
        f.write(blob)
    print("Сохранено: %s (%.0f КБ) — проиграй файл." % (out, len(blob) / 1024))


def cmd_clone(args):
    to_deck = args.to_deck or args.voice
    clone_cards(args.query, to_deck, limit=args.limit,
                tag=args.tag or args.voice, force=args.force)


def profile_for(deck):
    """Сохранённые настройки полей для этой колоды (профиль)."""
    profs = (_read_app_config() or {}).get("profiles") or {}
    return profs.get(deck or "") or {}


def _fields_from_args(args, deck=None):
    """Поля: аргументы CLI -> профиль колоды -> дефолты пайплайна."""
    prof = profile_for(deck) if deck else {}

    def pick(key, cli):
        v = getattr(args, cli, None)
        if v:
            return v
        return prof.get(key) or None

    return resolve_fields(
        sentence_src=pick("sentence_src", "sentence_src"),
        sentence_audio=pick("sentence_audio", "sentence_audio"),
        word_src=pick("word_src", "word_src"),
        word_audio=pick("word_audio", "word_audio"),
        furigana_src=pick("furigana_src", "furigana_src"),
        reading=pick("reading", "reading"),
    )


def _qfield(name):
    """Имя поля в поисковом запросе Anki (с пробелами — в кавычках)."""
    name = (name or "").strip()
    if not name:
        return "SentenceAudio"
    if re.search(r"[\s:]", name):
        return '"%s"' % name
    return name


def _pending_notes(ids, limit, fields, mode="both"):
    """Первые `limit` заметок, которым ещё нужен звук.

    Лимит «озвучить 10 карточек» должен означать «10 карточек работы».
    Раньше брались первые N заметок колоды, и на почти озвученной колоде
    приложение отвечало «всё уже озвучено», хотя не озвучено ещё сотня.

    Звук в Anki лежит в поле как [sound:...], поэтому «карточка без звука»
    ищется поиском: deck:"..." -Поле:*sound*.
    """
    fields = fields or DEFAULT_FIELDS
    parts = []
    if mode in ("sentence", "both"):
        parts.append("-" + _qfield(fields.get("sentence_audio")) + ":*sound*")
    if mode in ("expression", "both"):
        parts.append("-" + _qfield(fields.get("word_audio")) + ":*sound*")
    if parts:
        q = "(" + " OR ".join(parts) + ")"
        try:
            pend = ac("findNotes", query=q)
        except SystemExit:
            pend = None
        if pend is not None:
            keep = set(ids)
            return [i for i in pend if i in keep][:limit]
    # запасной путь: читаем заметки кусками и смотрим поля сами
    need = []
    for chunk in _chunks(ids, 400):
        for n in notes_info(chunk):
            f = n.get("fields", {})

            def _val(key):
                return plain(f.get(key, {}).get("value", ""), strip_media=True)

            def _has(key):
                return plain(f.get(key, {}).get("value", ""))

            need_sent = _val(fields["sentence_src"]) and not _has(fields["sentence_audio"])
            need_word = _val(fields["word_src"]) and not _has(fields["word_audio"])
            if need_sent or need_word:
                need.append(n["noteId"])
                if len(need) >= limit:
                    return need
    return need



def _select_note_ids(args, fields):
    """Общая выборка карточек для voice/preview: deck / ids / tag / --limit / --new.

    Возвращает список id; пустая выборка — SystemExit с понятным текстом.
    """
    tag = getattr(args, "tag", None)
    ids = []
    if args.deck:
        if getattr(args, "new", False):
            # ежедневный сценарий: только карточки без av_voiced
            ids = ac("findNotes",
                     query='deck:"%s" -tag:av_voiced' % args.deck)
            if not ids:
                print("Новых карточек нет: у всех карточек колоды '%s' есть "
                      "тег av_voiced." % args.deck)
                return []
            print("Новых карточек (без av_voiced): %d." % len(ids))
        else:
            ids = ac("findNotes", query='deck:"%s"' % args.deck)
        if tag:
            # внутри колоды оставляем только карточки с тегом
            tagged = set(ac("findNotes", query='tag:"%s"' % tag))
            ids = [i for i in ids if i in tagged]
            if not ids:
                raise SystemExit("В колоде '%s' нет карточек с тегом '%s'."
                                 % (args.deck, tag))
        if not ids:
            raise SystemExit("Колода '%s' пуста." % args.deck)
        if args.limit:
            if args.force:
                # «Пересобрать всё заново» + лимит: берём первые N карточек
                # колоды и переозвучиваем их. Раньше лимит отбрасывал уже
                # озвученные карточки, и пересборка не работала вовсе.
                ids = ids[:args.limit]
            else:
                ids = _pending_notes(ids, args.limit, fields, mode=args.mode)
    elif tag:
        ids = ac("findNotes", query='tag:"%s"' % tag)
        if args.limit:
            if args.force:
                ids = ids[:args.limit]
            else:
                ids = _pending_notes(ids, args.limit, fields, mode=args.mode)
    elif args.ids:
        ids = [int(x) for x in args.ids]
    else:
        raise SystemExit("Укажи --deck или --ids.")
    return ids


def cmd_voice(args):
    fields = _fields_from_args(args, deck=args.deck)
    if getattr(args, "retry", False):
        # перезапуск неудавшихся операций прошлого прогона: force=False,
        # поэтому уже озвученные поля пропускаются сами
        lr = read_last_run()
        fids = lr.get("failed_ids") or []
        if not fids:
            raise SystemExit("Перепробовать нечего: у прошлого прогона "
                             "ошибок нет (или итогового файла ещё нет).")
        print("Перепробовать %d %s прошлого прогона (%s)."
              % (len(fids), _plural(len(fids), "карточку", "карточки",
                                    "карточек"),
                 lr.get("at") or "время неизвестно"))
        lr_voice = lr.get("voice")
        if isinstance(lr_voice, list):
            lr_voice, lr_extra = lr_voice[0], lr_voice[1:]
        else:
            lr_extra = []
        voice_notes(fids, lr_voice or args.voice or None,
                    mode=lr.get("mode", "both"), force=False,
                    fields=lr.get("fields") or fields,
                    verify=getattr(args, "verify", None),
                    asr_model=getattr(args, "asr_model", None),
                    extra_voices=lr_extra)
        return
    if getattr(args, "changed", False) and args.force:
        raise SystemExit("«Пересобрать всё заново» и «Только изменённые» "
                         "взаимоисключающие — выбери что-то одно.")
    ids = _select_note_ids(args, fields)
    if not ids:
        return
    extra = [x.strip() for x in (getattr(args, "voices", "") or "").split(",")
             if x.strip()]
    # голос из профиля колоды (его пишет интерфейс при запуске озвучки)
    voice = args.voice
    if not voice and args.deck:
        voice = profile_for(args.deck).get("voice") or None
    voice_notes(ids, voice, mode=args.mode, force=args.force,
                seed=args.seed, speed=args.speed, fields=fields,
                verify=getattr(args, "verify", None),
                asr_model=getattr(args, "asr_model", None),
                extra_voices=extra,
                only_changed=getattr(args, "changed", False))



def cmd_cleanup_media(args):
    """Осиротевшие озвучки в медиа Anki: tts_*.ogg/wav, на которые больше
    не ссылается ни одна карточка (остаются после переозвучки с изменённым
    текстом). Без --apply — только отчёт; с --apply — удалить.
    """
    query = 'deck:"%s"' % args.deck if args.deck else ""
    ids = ac("findNotes", query=query)
    referenced = set()
    inner = re.compile(r"\[(?:sound|audio):([^\]]+)\]", re.IGNORECASE)
    for chunk in _chunks(ids, 400):
        for n in notes_info(chunk):
            for f in (n.get("fields") or {}).values():
                for m in inner.finditer(f.get("value", "") or ""):
                    referenced.add(m.group(1).strip().lower())
    files = []
    for pat in ("tts_*.ogg", "tts_*.wav"):
        try:
            files.extend(ac("getMediaFilesNames", pattern=pat) or [])
        except Exception as e:
            raise SystemExit("getMediaFilesNames недоступен: %s — обнови "
                             "AnkiConnect." % e)
    files = sorted(set(files))
    orphans = [f for f in files if f.lower() not in referenced]
    print("Файлов tts_* в медиа: %d | на которые есть ссылки: %d | "
          "мусор: %d" % (len(files), len(files) - len(orphans), len(orphans)))
    for f in orphans:
        print("  мусор:", f)
    if not orphans:
        print("Чистить нечего.")
        return
    if not args.apply:
        print("Это только отчёт. Удалить: cleanup-media --apply "
              "(действие необратимо).")
        return
    n = 0
    for f in orphans:
        try:
            ac("deleteMediaFile", filename=f)
            n += 1
        except Exception as e:
            print("  не удалось удалить %s: %s" % (f, e))
    print("Удалено: %d из %d." % (n, len(orphans)))


def _preview_report(jobs, fields, rmode_by_nid, src_by_nid=None):
    """Строки предпросмотра + сводка. Чистая функция: без Anki и движка.

    src_by_nid: {nid: сырое поле предложения} — база для сравнения при
    подстановке (build_jobs возвращает src уже ПОСЛЕ инъекции, поэтому
    базой служит исходное поле карточки).

    Показывает то, что реально уйдёт в синтез, и помечает главное:
      * подстановка чтения из фуриганы сработала или НЕ сработала
        (термин не найден в предложении / отклонён страховкой);
      * слово уйдёт каной (какой именно) или кандзи;
      * какой режим чтения выбрался карточке.
    """
    sent_field = fields.get("sentence_audio")
    rows = []
    st = {"ops": len(jobs), "cards": len({j[0] for j in jobs}),
          "inj_ok": 0, "inj_miss": 0, "asis": 0, "word_kana": 0,
          "word_kanji": 0}
    for nid, field, text, src in jobs:
        kind = _field_title(field, fields)
        rmode = rmode_by_nid.get(nid, "mix")
        baseline = (src_by_nid or {}).get(nid, src)
        if field == sent_field:
            if rmode == "asis":
                st["asis"] += 1
                note = "кандзи — движок читает сам (режим asis)"
            elif text != baseline:
                st["inj_ok"] += 1
                note = "подстановка чтения ✓"
            else:
                st["inj_miss"] += 1
                note = ("⚠ подстановка НЕ сработала (термин не найден в "
                        "предложении или отклонён) — движок прочитает сам")
        else:
            if rmode == "asis" or KANJI_RE.search(text):
                st["word_kanji"] += 1
                note = "как написано — движок прочитает сам"
            else:
                st["word_kana"] += 1
                note = "кана: %s" % text
        rows.append((nid, kind, note, text[:60]))
    return rows, st


def cmd_preview(args):
    """Предпросмотр озвучки: что и как будет озвучено, без синтеза и GPU.

    Прогоняет ту же выборку и build_jobs, что и voice, показывает текст
    каждой операции, режим чтения карточки и результат подстановки фуриганы
    (включая промахи). С --voices — ещё и случайное распределение карточек
    по голосам ансамбля, как его сделает реальный прогон.
    """
    fields = _fields_from_args(args, deck=args.deck)
    ids = _select_note_ids(args, fields)
    if not ids:
        return
    notes = notes_info(ids)
    jobs = build_jobs(notes, args.mode, args.force, fields=fields)
    skipped = len({n["noteId"] for n in notes}) - len({j[0] for j in jobs})
    rmode_by_nid = {n["noteId"]: reading_mode(fields, n,
                                              fields.get("reading", ""))
                    for n in notes}
    print("Предпросмотр озвучки%s (режим: %s, пересборка: %s)"
          % (" колоды «%s»" % args.deck if args.deck else "",
             _mode_title(args.mode), "да" if args.force else "нет"))
    if not jobs:
        print("Озвучивать нечего: у выбранных карточек уже есть звук "
              "(или пустой текст). Для пересмотра включи «Пересобрать всё "
              "заново» (--force).")
        return
    # ансамбль: та же раскладка, что сделает реальный прогон
    voice_by_nid = None
    extra = [x.strip() for x in (getattr(args, "voices", "") or "").split(",")
             if x.strip()]
    names = []
    for n in ([args.voice] if args.voice else []) + extra:
        if n and n not in names:
            names.append(n)
    if len(names) > 1:
        prior = {}
        for n in names:
            try:
                for i in ac("findNotes", query='tag:"av_voice::%s"' % n):
                    prior[i] = n
            except Exception:
                pass
        voice_by_nid = assign_voices({j[0] for j in jobs}, names,
                                     seed=args.seed, prior=prior)
        print("Ансамбль: %s" % ", ".join(names))
    # сырые поля предложений: база сравнения для подстановки
    sent_f = fields.get("sentence_src", "Sentence")
    src_by_nid = {}
    for n in notes:
        f = (n.get("fields") or {}).get(sent_f) or {}
        src_by_nid[n["noteId"]] = plain(f.get("value", ""), strip_media=True)
    rows, st = _preview_report(jobs, fields, rmode_by_nid, src_by_nid)
    for nid, kind, note, text in rows:
        v = (" «%s»" % voice_by_nid[nid]) if voice_by_nid else ""
        print("  [%d] %-12s %s — %s%s" % (nid, kind, note, text, v))
    print("\nИтого: %d %s на %d %s | подстановок ✓ %d, ✗ %d | asis %d | "
          "слово каной %d, кандзи %d | пропущено (уже озвучено/нечего "
          "озвучивать) %d"
          % (st["ops"], _plural(st["ops"], "операция", "операции",
                                "операций"),
             st["cards"], _plural(st["cards"], "карточка", "карточки",
                                  "карточек"),
             st["inj_ok"], st["inj_miss"], st["asis"],
             st["word_kana"], st["word_kanji"], skipped))
    if st["inj_miss"]:
        print("⚠ Есть промахи подстановки: у этих карточек термин прочитает "
              "сам движок. Проверь фуригану и написание термина в "
              "предложении — или оставь как есть.")


def check_target(job):
    """Что сверяем с записанным звуком.

    У слова в поле может лежать длинная фраза, а озвучено только чтение
    («アイリング・ヌートセンの残響式» -> «ざんきょうしき»). Сверять звук с
    исходным полем — значит ждать несуществующей части фразы: получаем
    ложные «модель потеряла кусок». Сверяем с тем, что произнесено.
    """
    try:
        return job[2]
    except Exception:
        return ""


def cmd_verify(args):
    """Проверить произношение уже озвученных карточек.

    Берём тексты ровно те, что синтезировались (тот же kanaize и та же
    фуригана), достаём звук из Anki и сверяем: покрытие ожидаемой речи и
    число расхождений. Печатаем таблицу и пишем отчёт рядом с браком.
    """
    fields = _fields_from_args(args, deck=args.deck)
    if args.deck:
        ids = ac("findNotes", query='deck:"%s"' % args.deck)
    elif args.tag:
        ids = ac("findNotes", query='tag:"%s"' % args.tag)
    else:
        raise SystemExit("Укажи --deck или --tag.")
    if not ids:
        print("Ничего не найдено.")
        return
    if args.limit:
        ids = ids[:args.limit]
    checker = _pron_verifier(force=True,
                             asr_model=getattr(args, "asr_model", None))
    if checker is None:
        raise SystemExit("Проверка произношения недоступна: нет faster-whisper "
                         "в питоне движка или модели в кэше.")
    ok, why = checker.available()
    if not ok:
        raise SystemExit("Проверка произношения недоступна: %s" % why)
    notes = notes_info(ids)
    by_id = {n["noteId"]: n for n in notes}
    jobs = build_jobs(notes, args.mode, True, fields=fields)
    print("Проверяю произношение: %d кусков" % len(jobs))
    report = []
    bad = 0
    for job in jobs:
        nid, field, text, src_text = job
        f = (by_id.get(nid) or {}).get("fields", {})
        raw = f.get(field, {}).get("value", "")
        m = re.search(r"\[sound:([^\]]+)\]", raw)
        if not m:
            continue
        try:
            data = base64.b64decode(ac("retrieveMediaFile", filename=m.group(1)) or "")
        except Exception:
            continue
        if not data:
            continue
        # сверяем с тем, что должно было быть произнесено, а не с
        # исходным текстом поля
        res = checker.check(data, "ogg", check_target(job))
        voice = ""
        m2 = re.search(r"tts_(.+?)_\d+_", m.group(1)) if m else None
        if m2:
            voice = m2.group(1)
        row = {"note": nid, "field": field, "coverage": res.get("coverage"),
               "cer": res.get("cer"), "verdict": res.get("verdict"),
               "expected": text, "heard": res.get("heard", ""),
               "src": src_text, "voice": voice, "span": res.get("span"),
               "avg_logprob": res.get("avg_logprob"),
               "file": m.group(1) if m else ""}
        report.append(row)
        if res.get("fail") or res.get("suspect"):
            bad += 1
            # метку не ставим: проверка совещательная
            print("  %-8s note=%-14d покрытие=%.2f ошибка=%.2f  %s"
                  % (field[:8], nid, res.get("coverage") or 0.0,
                     res.get("cer") or 0.0, res.get("verdict")))
            if res.get("heard"):
                print("     ждали: %s" % text[:60])
                print("     услышали: %s" % res["heard"][:60])
    # норму голоса пересчитываем по принятым кускам — на ней строим пороги
    by_voice = {}
    for row in report:
        v = row.get("voice") or ""
        if v and row.get("verdict") in ("ок", "подозрительно"):
            by_voice.setdefault(v, []).append(row.get("coverage") or 0.0)
    for v, covs in by_voice.items():
        info = update_baseline(v, covs)
        if info:
            print("Норма голоса '%s': покрытие p05=%.2f медиана=%.2f (кусков: %d)"
                  % (v, info["p05"], info["median"], info["n"]))
    # подозрительные кладём в папку брака: из неё собирается колода
    # «AnkiVoice_Брак» с полем «Вердикт» — послушать и решить
    if bad and not getattr(args, "no_review", False):
        added = 0
        for row in report:
            if not (row.get("verdict", "").startswith("пропущено")
                    or row.get("verdict", "").startswith("не то")
                    or row.get("verdict", "").startswith("подозрительно")):
                continue
            fn = row.get("file") or ""
            fp = os.path.join(QC_REJECT_DIR, fn)
            try:
                if fn and os.path.exists(fp):
                    with open(fp, "rb") as fh:
                        blob = fh.read()
                else:
                    blob = base64.b64decode(
                        ac("retrieveMediaFile", filename=fn) or "")
            except Exception:
                continue
            if not blob:
                continue
            if not os.path.isdir(QC_REJECT_DIR):
                os.makedirs(QC_REJECT_DIR, exist_ok=True)
            with open(fp, "wb") as fh:
                fh.write(blob)
            rec = {"file": fn, "text": row.get("expected", ""),
                   "reasons": ["%s (покрытие %.2f, ошибки %.2f)"
                               % (row.get("verdict"), row.get("coverage") or 0.0,
                                  row.get("cer") or 0.0)],
                   "attempt": 0, "strategy": "проверка содержания",
                   "coverage": row.get("coverage"), "cer": row.get("cer"),
                   "note": row.get("note"), "field": row.get("field"),
                   "span": row.get("span"), "voice": row.get("voice")}
            with open(os.path.join(QC_REJECT_DIR, "index.jsonl"), "a",
                      encoding="utf-8") as fh:
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            added += 1
        if added:
            print("Подозрительных в папке брака: %d — собери колоду: "
                  "pipeline.bat qc-deck" % added)

    # отчёт пишем сразу: даже если что-то пойдёт не так дальше, результат
    # проверки должен остаться на диске

    # отчёт пишем сразу: даже если дальше что-то пойдёт не так, результат
    # проверки должен остаться на диске

    # отчёт пишем сразу: даже если дальше что-то пойдёт не так, результат
    # проверки должен остаться на диске
    if report:
        try:
            os.makedirs(QC_REJECT_DIR, exist_ok=True)
            out = os.path.join(QC_REJECT_DIR, "verify_report.json")
            with open(out, "w", encoding="utf-8") as fh:
                json.dump(report, fh, ensure_ascii=False, indent=1)
            print("Отчёт: %s" % out)
        except Exception as e:
            print("Отчёт не записан: %r" % (e,))

    # варианты: переозвучиваем подозрительное несколькими сидами, чтобы
    # выбрать лучший на слух
    nvar = int(getattr(args, "variants", 0) or 0)
    if nvar and bad:
        print("\nДелаю по %d вариантов на каждое подозрительное..." % nvar)
        v = get_voice("narrator")
        for row in report:
            if not row.get("verdict", "").startswith(("пропущено", "не то",
                                                      "подозрительно")):
                continue
            voice = row.get("voice") or "narrator"
            try:
                vv = get_voice(voice)
            except Exception:
                vv = v
            text = row.get("expected") or ""
            if not text:
                continue
            # произнесённый текст — ровно то, что сверяли
            for k in range(1, nvar + 1):
                try:
                    blob, ext, _info = synth(vv, text, seed=42 + k * 17,
                                            src=row.get("src") or text)
                except SystemExit:
                    continue
                fn = "var_%d_%d_%d_%d.%s" % (row.get("note") or 0, k,
                                              int(time.time()) % 100000,
                                              k, ext)
                try:
                    if not os.path.isdir(QC_REJECT_DIR):
                        os.makedirs(QC_REJECT_DIR, exist_ok=True)
                    with open(os.path.join(QC_REJECT_DIR, fn), "wb") as fh:
                        fh.write(blob)
                    rec = {"file": fn, "text": text,
                           "reasons": ["вариант %d на слух" % k],
                           "attempt": k, "strategy": "вариант %d (сид %d)"
                                       % (k, 42 + k * 17),
                           "note": row.get("note"), "field": row.get("field"),
                           "coverage": row.get("coverage")}
                    with open(os.path.join(QC_REJECT_DIR, "index.jsonl"), "a",
                              encoding="utf-8") as fh:
                        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                except Exception as e:
                    print("  вариант не сохранился: %r" % (e,))

    print("\nПроверено %d кусков, сомнительных: %d" % (len(report), bad))
    if bad:
        print("\nПодозрительные можно переделать: pipeline.bat voice --tag "
              "av_suspect --voice <голос> --force")



def cmd_make_deck(args):
    fields = _fields_from_args(args)
    to_deck = args.to_deck or get_voice(args.voice).get("display") or args.voice
    ids = clone_cards(args.query, to_deck, limit=args.limit, tag=args.tag or args.voice,
                      force=args.force, fields=fields)
    voice_notes(ids, args.voice, mode=args.mode, force=args.force,
                seed=args.seed, speed=args.speed, fields=fields,
                verify=getattr(args, "verify", None),
                asr_model=getattr(args, "asr_model", None))
    print("\n=== Проверка ===")
    check_deck(to_deck, fields=fields)


def cmd_qc_deck(args):
    """Собрать отбракованный синтез в отдельную колоду Anki.

    Зачем: детектор отклоняет файл и выбрасывает его — а чтобы судить,
    правильно ли он отклонил, нужно ПОСЛУШАТЬ. Здесь каждая отбракованная
    попытка становится карточкой: сверху текст, под ним причины и стратегия,
    внизу само аудио.

    Карточки помечены тегом av_qc_reject и снабжены полем «Вердикт», куда
    вы пишете своё решение («верно» / «ложное срабатывание») — это и есть
    разметка для подстройки порогов.
    """
    d = QC_REJECT_DIR
    idx = os.path.join(d, "index.jsonl")
    if not os.path.exists(idx):
        raise SystemExit("Отбракованного звука нет: %s\n"
                         "Сначала прогони озвучку — брак складывается туда "
                         "автоматически." % idx)
    recs = []
    with open(idx, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    recs.append(json.loads(line))
                except Exception:
                    pass
    if not recs:
        raise SystemExit("index.jsonl пуст.")

    deck = args.deck or "AnkiVoice_Брак"
    ac("createDeck", deck=deck)

    # очистка колоды (по желанию): старые карточки без
    # пользы; в новом AnkiConnect удаление заметок новый имя
    # deleteNotes (раньше было removeNotes)
    if getattr(args, "clean", False):
        removed = 0
        try:
            cards = ac("findCards", query='deck:"%s"' % deck) or []
            if cards:
                infos = ac("cardsInfo", cards=cards) or []
                nids = sorted(set(c.get("note") for c in infos if c.get("note")))
                if nids:
                    try:
                        ac("deleteNotes", notes=nids)
                    except SystemExit:
                        ac("removeNotes", notes=nids)
                    removed = len(nids)
            print("Очищено старых карточек: %d" % removed)
        except SystemExit as e:
            print("  (не удалось очистить: %r)" % (e,))

    # Имя модели зависит от локали установки Anki: в русской сборке
    # «Basic» называется «Простая». Ищем не по имени, а по строению —
    # модель ровно с двумя полями Front/Back. Kiku (22 поля) брать нельзя:
    # карточка брака сломается на обязательных полях.
    models = ac("modelNames") or []
    model = None
    for m in models:
        try:
            flds_m = ac("modelFieldNames", modelName=m) or []
        except Exception:
            continue
        if [x.lower() for x in flds_m] == ["front", "back"]:
            model = m
            break
    if not model:
        raise SystemExit("Нет модели с полями Front/Back (обычно «Простая»). "
                         "Доступны: %s" % ", ".join(models[:12]))
    flds = ac("modelFieldNames", modelName=model) or ["Front", "Back"]
    front, back = flds[0], flds[-1]
    print("модель: %s (%s)" % (model, ", ".join(flds)))
    verdict_field = next((x for x in flds if x.lower() in
                          ("вердикт", "verdict", "comment", "комментарий")), None)

    # группируем записи: исходник и его варианты — одна карточка,
    # чтобы слушать не 162 отдельных, а по одной на проблемный кусок
    groups = {}
    order = []
    for r in recs:
        key = (r.get("note"), r.get("text") or "")
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(r)

    # уже созданные карточки: обновляем их на месте, а не плодим дубли
    # (новый AnkiConnect не умеет удалять заметки, поэтому «пересоздать»
    # колоду нельзя — только переписать)
    existing = {}
    try:
        ids = ac("findCards", query='deck:"%s"' % deck) or []
        for n in notes_info(ids):
            fld = (n.get("fields") or {})
            val = ((fld.get(front) or {}).get("value") or "").strip()
            if val:
                existing[val] = n["noteId"]
    except SystemExit:
        pass

    made = skipped = 0
    fresh_fronts = set()
    for key in order:
        items = sorted(groups[key], key=lambda x: x.get("attempt") or 0)
        sounds = []
        head = ""
        details = ""
        for r in items:
            fp = os.path.join(d, r["file"])
            if not os.path.exists(fp):
                skipped += 1
                continue
            with open(fp, "rb") as f:
                blob = f.read()
            stored = ac("storeMediaFile", filename=r["file"], overwrite=True,
                        data=base64.b64encode(blob).decode("ascii"))
            fname = stored or r["file"]
            att = r.get("attempt") or 0
            strat = (r.get("strategy") or "")
            if strat.startswith("вариант"):
                label = "Вариант %d" % att
            elif att:
                label = "Брак качества"
            else:
                label = "Как было"
            sounds.append("%s: [sound:%s]" % (label, fname))
            if head:
                continue
            head = r.get("text") or "(пусто)"
            extra = ""
            if r.get("coverage") is not None:
                extra = ("\nПокрытие: %.2f, ошибки: %.2f"
                         % (r.get("coverage") or 0.0, r.get("cer") or 0.0))
            if r.get("note"):
                extra += "\nКарточка: %d, поле: %s" % (r["note"], r.get("field", ""))
            if r.get("span"):
                sp = r["span"]
                extra += ("\nПроблемный участок: %.1f-%.1f c (услышали «%s»)"
                          % (sp.get("start") or 0.0, sp.get("end") or 0.0,
                             sp.get("heard", "")))
            details = ("Причина: %s\nСтратегия: %s%s"
                       % ("; ".join(r.get("reasons") or []) or "не указана",
                          r.get("strategy", "?"), extra))
            details += ("\nЧто делать: послушай звуки. Если все варианты плохие — "
                        "напиши «верно», если звук нормальный — «ложное срабатывание».")
        if not sounds:
            continue
        tail = "\n\nВердикт: " if not verdict_field else ""
        body = "%s\n\n%s%s" % (details, "\n".join(sounds), tail)
        fields = {front: head, back: body}
        if verdict_field:
            fields[verdict_field] = ""
        fresh_fronts.add(head.strip())
        note_id = existing.get(head.strip())
        try:
            if note_id:
                ac("updateNoteFields", note={"id": note_id, "fields": fields})
                try:
                    ac("addTags", notes=[note_id], tags=["av_qc_reject"])
                except SystemExit:
                    pass
            else:
                ac("addNote", note={
                    "deckName": deck, "modelName": model, "fields": fields,
                    "options": {"allowDuplicate": False, "duplicateScope": "deck"},
                    "tags": ["av_qc_reject"],
                })
            made += 1
        except SystemExit as e:
            # такая карточка уже есть — не повторяем
            skipped += 1
            if "duplicate" not in str(e).lower():
                print("  карточка не добавилась: %r" % (e,))
    # карточки прошлых проверок, которых больше нет в индексе:
    # помечаем «устарело» (удалить можно только руками)
    stale = 0
    for ftext, nid in existing.items():
        if ftext in fresh_fronts:
            continue
        try:
            keep = ""
            try:
                _n = notes_info([nid])[0]
                _b = (_n.get("fields") or {}).get(back, {}) or {}
                _v = _b.get("value") or ""
                if "Вердикт:" in _v:
                    keep = "  " + _v.split("Вердикт:")[1].strip()
            except Exception:
                pass
            ac("updateNoteFields", note={
                "id": nid,
                "fields": {front: "Устарело — эта карточка больше не в проверке",
                           back: "Можно удалить." + keep}})
            stale += 1
        except SystemExit:
            pass
    if stale:
        print("Помечено устаревшими: %d (удалить вручню)" % stale)
    print("Колода '%s': добавлено %d карточек, пропущено (нет файла): %d"
          % (deck, made, skipped))
    print("Послушай каждую и впиши в поле «Вердикт»: «верно» либо "
          "\"ложное срабатывание\" — по этим записям подстроятся пороги.")
    return made



def cmd_verdicts(args):
    """Прочитать твои вердикты из колоды «Брак» и посчитать статистику.

    Вердикт пишешь в поле «Вердикт» карточки: «верно» (звук действительно
    плохой) или «ложное срабатывание» (звук нормальный, детектор ошибся).
    По этим отметкам видно, где наши пороги стоит подвинуть.
    """
    deck = args.deck or "AnkiVoice_Брак"
    # istoriya verdiktov iz proshlyh raundov (koloda peresbiraetsya,
    # a otmetki ostayutsia zdes)
    history = []
    hist_path = os.path.join(os.environ.get("APPDATA") or "", "AnkiVoice",
                           "verdicts_history.json")
    try:
        with open(hist_path, encoding="utf-8") as f:
            history = json.load(f) or []
    except Exception:
        history = []
    ids = ac("findNotes", query='deck:"%s"' % deck)
    if not ids:
        print("Колода '%s' пуста — нечего читать." % deck)
        return
    notes = notes_info(ids)
    # индекс: имя файла -> запись (там лежит покрытие)
    index = {}
    idx_path = os.path.join(QC_REJECT_DIR, "index.jsonl")
    try:
        with open(idx_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                except Exception:
                    continue
                if r.get("file"):
                    index[r["file"]] = r
    except Exception:
        pass
    true_bad, false_alarm, unknown = [], [], []
    # из истории: front -> (покрытие, вердикт)
    hist_map = {}
    for h in history:
        f0 = (h.get("front") or "").strip()
        if f0:
            hist_map[f0] = (h.get("coverage"), h.get("verdict") or "")
    for n in notes:
        f = n.get("fields") or {}
        verdict = ""
        for k, v in f.items():
            val = (v.get("value") or "").strip()
            if k.lower() in ("вердикт", "verdict", "комментарий", "comment"):
                verdict = val
                break
            # в модели «Простая» отдельного поля нет — берём текст ПОСЛЕ
            # пометки «Вердикт:», иначе за ответ сойдёт сама подпись
            if not verdict:
                m = re.search(r"Вердикт[^:\n]*:(.*)$", val, re.S)
                if m:
                    got = m.group(1).strip().strip("_").strip()
                    verdict = got
                    break
        if not verdict:
            continue
        cov = None
        for k, v in f.items():
            m = re.search(r"Файл:\s*(\S+)", v.get("value") or "")
            if m:
                rec = index.get(m.group(1))
                if rec:
                    cov = rec.get("coverage")
        low = verdict.lower()
        item = (cov, n["noteId"])
        if "ложн" in low or "нет" in low or "ok" in low:
            false_alarm.append(item)
        elif "верно" in low or "да" in low or "плох" in low:
            true_bad.append(item)
        else:
            unknown.append(item)
    # добавляем вердикты из истории (тех карточек в колоде уже может не быть)
    deck_fronts = set()
    for n in notes:
        flds = n.get("fields") or {}
        vals = [((flds.get(k) or {}).get("value") or "").strip() for k in flds]
        deck_fronts.add(vals[0] if vals else "")
    for f0, (cov0, v0) in hist_map.items():
        if f0 in deck_fronts:
            continue
        low0 = v0.lower()
        item0 = (cov0, f0)
        if "ложн" in low0 or "нет" in low0 or "ok" in low0:
            false_alarm.append(item0)
        elif "верно" in low0 or "да" in low0 or "плох" in low0:
            true_bad.append(item0)
        else:
            unknown.append(item0)
    total = len(true_bad) + len(false_alarm) + len(unknown)
    print("Колода '%s': вердиктов %d из %d карточек" % (deck, total, len(notes)))
    print("  брак подтверждён: %d, ложных срабатываний: %d, без ответа: %d"
          % (len(true_bad), len(false_alarm), len(unknown)))
    def covs(lst):
        return sorted(c for c, _ in lst if c is not None)
    cb, cf = covs(true_bad), covs(false_alarm)
    if cb:
        print("  у брака покрытие: min=%.2f med=%.2f max=%.2f"
              % (cb[0], cb[len(cb)//2], cb[-1]))
    if cf:
        print("  у ложных срабатываний: min=%.2f med=%.2f max=%.2f"
              % (cf[0], cf[len(cf)//2], cf[-1]))
        print("  -> порог «подозрительно» стоит поднять до %.2f"
              % max(0.60, cf[-1] + 0.03))
    if cb:
        print("  -> порог «брак» можно поставить на %.2f"
              % max(0.45, min(cb) + 0.03))
    if unknown:
        print("  без ответа: %d карточек (послушай и допиши «верно»/«ложное»)"
              % len(unknown))
    return total



def cmd_check(args):
    return check_deck(args.deck, fields=_fields_from_args(args),
                      verify_files=not getattr(args, "fast", False))


def cmd_selftest(args):
    """Проверка всей цепочки без записи в Anki и без синтеза."""
    bad = 0

    def ok(msg):
        print("  OK   %s" % msg)

    def fail(msg):
        nonlocal bad
        bad += 1
        print("  FAIL %s" % msg)

    print("== Самопроверка пайплайна ==")
    print("  --   код (инструмент): %s" % CODE)
    if av_state.ENGINE:
        ok("папка GPT-SoVITS найдена: %s" % av_state.ENGINE)
    else:
        fail("папка GPT-SoVITS не найдена (env GPT_SOVITS_ROOT / gptsovits_path.txt / конфиг AnkiVoice.exe)")
    if av_state.PYTHON and os.path.exists(av_state.PYTHON):
        ok("runtime\\python.exe на месте")
    else:
        fail("нет runtime\\python.exe: %s" % av_state.PYTHON)

    cfg = load_voices()
    voices = cfg.get("voices", {})
    ok("voices.json: голосов %d" % len(voices)) if voices else fail("voices.json пуст")
    for name, v in sorted(voices.items()):
        for key in ("gpt", "sovits", "ref"):
            p = v.get(key, "")
            if key == "ref" and not p:
                # голос найден сканером, референс ещё не подобран — не ошибка
                print("  --   %s: референс не выбран (выбери вкладкой «Голос»)" % name)
                continue
            p = p if os.path.isabs(p) else os.path.join(av_state.ENGINE or CODE, p)
            if os.path.exists(p):
                d = ref_duration(p) if key == "ref" else None
                if key == "ref" and d is not None and not (3.0 <= d <= 10.0):
                    fail("%s: %s = %.1f с (API требует 3–10 с)" % (name, key, d))
                else:
                    ok("%s: %s %s" % (name, key, ("%.1f с" % d) if d else ""))
            else:
                fail("%s: %s не найден: %s" % (name, key, p))
    if _qc_v2_module() is not None:
        ok("QC v2: многосигнальная проверка качества звука")
    else:
        fail("QC v2 (lab/quality_v2.py) недоступен — работает простой "
             "критерий «есть звук»")
    try:
        import pyopenjtalk
        r = pyopenjtalk.g2p("合釘を打ち込む", kana=True)
        ok("pyopenjtalk (запасной ход): %s" % r)
    except Exception as e:
        fail("pyopenjtalk: %s" % e)
    client = sudachi_client()
    if client is not None:
        ok("Sudachi (встроенный, %s, словарь %s): %s"
           % (client.version, client.dictver, kanaize(u"高輪ゲートウェイ駅")))
    else:
        print("  --   Встроенный Sudachi недоступен — иероглифы читает "
              "pyopenjtalk;")
        print("       нужны pyruntime.zip и sudachidict.zip рядом со скриптом.")

    # текст -> хирагана: проверяем сложные случаи (полукатакана, полноразмерная
    # латиница, ヴ-серия, словарные замены, длинная глагольная форма)
    print("  --   текст -> хирагана (сложные случаи):")
    for src, want in ((u"ｶﾞｷｮｳ", u"がきょう"),
                      (u"ＩＥＣ規格", u"あいいーしーきかく"),
                      (u"食べさせられたくなかった", u"たべさせられたくなかった"),
                      (u"キョウト", u"きょうと"),
                      (u"bus", u"ばす"),
                      (u"community", u"こみゅにてぃー"),
                      (u"3D", u"すりーでぃー"),
                      (u"USB", u"ゆーえすびー"),
                      (u"Wi-Fi", u"わいふぁい")):
        got = kanaize(src)
        if got == want:
            ok("%s -> %s" % (src, got))
        else:
            fail("%s -> %s (ожидалось %s)" % (src, got, want))
    # 合折釘 — доменный термин: движку без поля не знать «あいおれくぎ»,
    # он читает по-своему. Проверяем обе ветки раздельно: авто-чтение
    # (просто обязано выдать хирагану) и чтение из фуриганы (строго эталон).
    src = u"合折釘"
    got = kanaize(src)
    if got and not KANJI_RE.search(got):
        ok("%s (авто, без поля): %s — движок читает сам" % (src, got))
    else:
        fail("%s (авто): %r — остались иероглифы" % (src, got))
    got = kanaize_card(src, expression=src, furigana=u"合折釘[あいおれくぎ]")
    if got == u"あいおれくぎ":
        ok("%s (из фуриганы): %s" % (src, got))
    else:
        fail("%s (из фуриганы): %s (ожидалось %s)" % (src, got, u"あいおれくぎ"))
    try:
        ac("version")
        ok("AnkiConnect отвечает")
    except SystemExit:
        fail("AnkiConnect недоступен — открой Anki")
    proxied = [k for k in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
                           "http_proxy", "https_proxy", "all_proxy")
               if os.environ.get(k)]
    if proxied:
        print("  --   в окружении задан прокси (%s) — локальные запросы идут "
              "мимо него, не мешает" % ", ".join(proxied))

    # подстановка чтения из фуриганного поля в предложение (см. inject_reading)
    print("  --   подстановка чтения из поля (фуригана слова):")
    for expr, efur, sent, want in (
            (u"相欠き", u"相欠[あいが]き",
             u"大工は交差部を相欠きにして高さを揃えた。",
             u"大工は交差部をあいがきにして高さを揃えた。"),
            (u"相欠き継ぎ", u"相欠[あいが]き継[つ]ぎ",
             u"大工は材の延長に相欠き継ぎを用いて固めた。",
             u"大工は材の延長にあいがきつぎを用いて固めた。"),
            (u"I形グルーブ", u"I形[アイがた]グルーブ",
             u"薄板の突合せ継手はI形グルーブで溶接した。",
             u"薄板の突合せ継手はあいがたぐるーぶで溶接した。"),
            (u"IEC規格", u"IEC規格[アイイーシーきかく]",
             u"特注の配電盤仕様にIEC規格を引用した。",
             u"特注の配電盤仕様にあいいーしーきかくを引用した。"),
            # слово в предложении НЕТ — предложение не трогаем
            (u"合折釘", u"合折釘[あいおれくぎ]",
             u"別の文には слова нет。", u"別の文には слова нет。")):
        note = {"fields": {
            "Expression": {"value": expr},
            "ExpressionFurigana": {"value": efur},
            "ExpressionReading": {"value": ""},
            "Sentence": {"value": sent},
            "SentenceFurigana": {"value": ""}}}
        got = inject_reading(sent, note, reading="ExpressionFurigana")
        if got == want:
            ok("подстановка: %s" % expr)
        else:
            fail("подстановка: %s -> %s (ожидалось %s)" % (expr, got, want))
        # чтение слова (для озвучки самого Expression) тоже должно быть верным
        w = word_text(note, "Expression", reading="ExpressionFurigana")
        if w and not KANJI_RE.search(w):
            ok("чтение слова %s: %s" % (expr, w))
        else:
            fail("чтение слова %s: %s (в чтении остались иероглифы)"
                 % (expr, w))
    # режимы источника чтения (параметр reading): авто, mix, asis и конкретное поле
    print("  --   режимы источника чтения:")
    if DEFAULT_FIELDS.get("reading", "") == "":
        ok("по умолчанию: авто (фуригана есть — по ней, нет — кандзи)")
    else:
        fail("по умолчанию: reading=%r (ожидалось '' — авто)"
             % DEFAULT_FIELDS.get("reading"))
    # авто: решение принимается по каждой карточке
    auto_f = {"fields": {"Expression": {"value": u"相欠き"},
                          "ExpressionFurigana": {"value": u"相欠[あいが]き"},
                          "Sentence": {"value": u"大工は相欠きにして高さを揃えた。"}}}
    auto_n = {"fields": {"Expression": {"value": u"相欠き"},
                          "ExpressionFurigana": {"value": ""},
                          "Sentence": {"value": u"大工は相欠きにして高さを揃えた。"}}}
    if reading_mode(DEFAULT_FIELDS, auto_f, "") == "mix":
        ok("авто: фуригана есть — термин по ней (mix)")
    else:
        fail("авто: с фуриганой ожидался mix")
    if reading_mode(DEFAULT_FIELDS, auto_n, "") == "asis":
        ok("авто: фуриганы нет — кандзи (asis)")
    else:
        fail("авто: без фуриганы ожидался asis")
    if reading_mode(DEFAULT_FIELDS, auto_f, "asis") == "asis":
        ok("asis: принудительно кандзи, даже когда фуригана есть")
    else:
        fail("asis: ожидался asis")
    note_r = {"fields": {
        "Expression": {"value": u"相欠き"},
        "ExpressionFurigana": {"value": u"相欠[あいが]き"},
        "ExpressionReading": {"value": ""},
        u"Кана": {"value": u"あいが"},
        u"КанаИероглифы": {"value": u"相欠き"},
        u"Пусто": {"value": ""},
        "Sentence": {"value": u"大工は相欠きにして高さを揃えた。"},
        "SentenceFurigana": {"value": ""}}}
    sent_r = note_r["fields"]["Sentence"]["value"]
    got = inject_reading(sent_r, note_r, reading="off")
    if got == sent_r:
        ok("reading=off: подстановки нет")
    else:
        fail("reading=off: ожидалась чистая строка, получено %r" % got)
    w = word_text(note_r, "Expression", reading="off")
    if w == u"相欠き":
        ok("reading=off: слово без фуриганы (движок читает само)")
    else:
        fail("reading=off: слово %r (ожидалось написание без разметки)" % w)
    got = inject_reading(sent_r, note_r, reading=u"Кана")
    if got == u"大工はあいがにして高さを揃えた。":
        ok("reading=поле: чтение подставилось из поля «Кана»")
    else:
        fail("reading=поле: %r" % got)
    w = word_text(note_r, "Expression", reading=u"Кана")
    if w == u"あいが":
        ok("reading=поле: слово озвучивается чтением из поля")
    else:
        fail("reading=поле: слово %r" % w)
    # поле может содержать фуриганную разметку — указывай готовое
    # ExpressionFurigana, карточку переписывать не нужно
    got = inject_reading(sent_r, note_r, reading="ExpressionFurigana")
    if got == u"大工はあいがきにして高さを揃えた。":
        ok("reading=фуриганное поле: разметка разобрана, чтение подставлено")
    else:
        fail("reading=фуриганное поле: %r" % got)
    w = word_text(note_r, "Expression", reading="ExpressionFurigana")
    if w == u"あいがき":
        ok("reading=фуриганное поле: слово озвучивается полным чтением")
    else:
        fail("reading=фуриганное поле: слово %r" % w)
    # пустое поле — подстановки нет, авто НЕ подхватывается
    got = inject_reading(sent_r, note_r, reading=u"Пусто")
    if got == sent_r:
        ok("reading=пустое поле: подстановки нет (авто не подхватывается)")
    else:
        fail("reading=пустое поле: %r" % got)
    w = word_text(note_r, "Expression", reading=u"Пусто")
    if w == u"相欠き":
        ok("reading=пустое поле: слово — написание без разметки (как off)")
    else:
        fail("reading=пустое поле: слово %r" % w)
    got = inject_reading(sent_r, note_r, reading=u"НетТакогоПоля")
    if got == sent_r:
        ok("reading=нет такого поля: подстановки нет")
    else:
        fail("reading=нет такого поля: %r" % got)
    # в «чтении» иероглифы — отказываемся: это не чтение
    got = inject_reading(sent_r, note_r, reading=u"КанаИероглифы")
    if got == sent_r:
        ok("reading=иероглифы в поле: подстановки нет (безопасность)")
    else:
        fail("reading=иероглифы в поле: %r" % got)

    ok("GPT-SoVITS запущен") if tts_ready() else \
        print("  --   GPT-SoVITS не запущен (поднимется сам при озвучке)")
    print("\n%s" % ("Всё в порядке." if not bad else "Проблем: %d — см. FAIL выше." % bad))
    sys.exit(1 if bad else 0)


def menu():
    cfg = load_voices()
    while True:
        print("\n======== Пайплайн озвучки Anki (GPT-SoVITS) ========")
        print("  1. Список голосов")
        print("  2. Добавить голос")
        print("  3. Создать колоду и озвучить её")
        print("  4. Озвучить существующую колоду")
        print("  5. Проверить колоду")
        print("  6. Тест синтеза (файл test_<голос>.ogg)")
        print("  7. Поднять сервер с голосом")
        print("  0. Выход")
        c = input("Выбор: ").strip()
        try:
            if c == "1":
                cmd_list()
            elif c == "2":
                cmd_add(argparse.Namespace(
                    name=ask("имя голоса латиницей (напр. sakura)"),
                    display=ask("как показывать (напр. Сакура)", ""),
                    gpt=ask("путь к GPT .ckpt"),
                    sovits=ask("путь к SoVITS .pth"),
                    ref=ask("путь к референсу 3–10 с"),
                    aux=[], prompt_text=ask("текст, говорится в референсе"),
                    prompt_lang="ja", force=True))
            elif c == "3":
                voice = ask("голос", cfg.get("default_voice") or "")
                cmd_make_deck(argparse.Namespace(
                    voice=voice, to_deck=None,
                    query=ask("откуда клонировать (запрос Anki)", "deck:Архитектура"),
                    limit=int(ask("сколько карточек", "20") or 20),
                    mode=ask("mode (both/sentence/expression)", "both"),
                    tag=None, force=False, seed=42, speed=1.0))
            elif c == "4":
                voice = ask("голос", cfg.get("default_voice") or "")
                cmd_voice(argparse.Namespace(
                    voice=voice, deck=ask("имя колоды"),
                    ids=None, limit=None,
                    mode=ask("mode (both/sentence/expression)", "both"),
                    force=False, seed=42, speed=1.0))
            elif c == "5":
                cmd_check(argparse.Namespace(deck=ask("имя колоды")))
            elif c == "6":
                cmd_test(argparse.Namespace(
                    voice=ask("голос", cfg.get("default_voice") or ""),
                    text=ask("текст для проверки", "こんにちは"),
                    seed=42, speed=1.0))
            elif c == "7":
                cmd_serve(argparse.Namespace(voice=ask("голос"), force=False))
            elif c == "0":
                return
        except SystemExit as e:
            if e.code not in (0, None):
                print("—", e)
        except Exception as e:
            print("Ошибка:", repr(e))


def main():
    ap = argparse.ArgumentParser(description="Пайплайн озвучки колод Anki голосами GPT-SoVITS")
    sub = ap.add_subparsers(dest="cmd")

    sub.add_parser("list", help="показать голоса")

    p = sub.add_parser("add", help="добавить голос в voices.json")
    p.add_argument("--name", required=True)
    p.add_argument("--display", default=None)
    p.add_argument("--gpt", required=True)
    p.add_argument("--sovits", required=True)
    p.add_argument("--ref", required=True)
    p.add_argument("--aux", nargs="*", default=[])
    p.add_argument("--prompt-text", required=True)
    p.add_argument("--prompt-lang", default="ja")
    p.add_argument("--force", action="store_true")

    p = sub.add_parser("server", help="поднять api_v2 без загрузки голоса")
    p.add_argument("--wait", type=int, default=600)

    p = sub.add_parser("indextts-server",
                       help="поднять сервис IndexTTS (модель в памяти)")
    p.add_argument("--wait", type=int, default=900)

    p = sub.add_parser("serve", help="поднять сервер/переключить голос")
    p.add_argument("--voice")
    p.add_argument("--force", action="store_true")

    p = sub.add_parser("test", help="синтез одного текста в файл")
    p.add_argument("--voice")
    p.add_argument("--text", required=True)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--speed", type=float, default=1.0)

    p = sub.add_parser("clone", help="клонировать карточки в новую колоду")
    p.add_argument("--voice", required=True)
    p.add_argument("--query", default="deck:Архитектура")
    p.add_argument("--to-deck", default=None)
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--tag", default=None)
    p.add_argument("--force", action="store_true")

    p = sub.add_parser("voice", help="озвучить колоду/карточки")
    p.add_argument("--voice")
    p.add_argument("--voices", default="",
                   help="ансамбль: «голос1,голос2,…» — карточки случайно "
                        "распределяются между голосами и озвучиваются "
                        "партиями (веса переключаются один раз на голос)")
    p.add_argument("--new", action="store_true",
                   help="только карточки без тега av_voiced (ежедневный "
                        "сценарий: добавил карточки — нажал одну кнопку)")
    p.add_argument("--changed", action="store_true",
                   help="«Пересобрать только изменённые»: перезаписать звук "
                        "лишь там, где текст или голос изменились с прошлой "
                        "озвучки (сверка с voiced_manifest.json)")
    p.add_argument("--retry", action="store_true",
                   help="перезапустить неудавшиеся операции прошлого "
                        "прогона (из last_run.json)")
    p.add_argument("--deck", default=None)
    p.add_argument("--ids", nargs="*", default=None)
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--mode", choices=["sentence", "expression", "both"], default="both")
    p.add_argument("--sentence-src", default=None, help="поле с текстом предложения")
    p.add_argument("--sentence-audio", default=None, help="поле для звука предложения")
    p.add_argument("--word-src", default=None, help="поле со словом")
    p.add_argument("--word-audio", default=None, help="поле для звука слова")
    p.add_argument("--furigana-src", default=None,
                   help="поле с фуриганой основного слова (по умолчанию "
                        "ExpressionFurigana); основное слово читается строго "
                        "по нему, всё остальное — автоматически")
    p.add_argument("--reading", default="",
                   help="режим чтения: \"\" — авто (есть фуригана — термин "
                        "читается по ней, нет — кандзи), mix — всегда по "
                        "фуригане, asis — только кандзи")
    p.add_argument("--force", action="store_true")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--speed", type=float, default=1.0)
    p.add_argument("--tag", default=None,
                   help="озвучить только карточки с этим тегом (например "
                        "av_suspect — те, где мы не уверены в произношении)")
    p.add_argument("--verify", action="store_true",
                   help="проверять произношение (faster-whisper в движке): "
                        "распознаём свой звук и сверяем с текстом")
    p.add_argument("--asr-model", default=None,
                   help="модель faster-whisper (по умолчанию — лучшая из кэша)")

    p = sub.add_parser("verify", help="проверить произношение уже озвученных карточек")
    p.add_argument("--deck", default=None)
    p.add_argument("--tag", default=None, help="проверить карточки с тегом")
    p.add_argument("--mode", choices=["sentence", "expression", "both"],
                   default="sentence",
                   help="что проверять: по умолчанию "
                        "(слово проверяется ненадежно)")
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--sentence-src", default=None)
    p.add_argument("--sentence-audio", default=None)
    p.add_argument("--word-src", default=None)
    p.add_argument("--word-audio", default=None)
    p.add_argument("--furigana-src", default=None)
    p.add_argument("--reading", default=None,
                   help="режим чтения: \"\" — авто (фуригана есть — термин по "
                        "ней, нет — кандзи), mix, asis; если не указано — "
                        "берётся из профиля колоды")
    p.add_argument("--asr-model", default=None)
    p.add_argument("--variants", type=int, default=0,
                   help="сколько вариантов синтеза сделать на каждое "
                        "подозрительное (для выбора на слух)")
    p.add_argument("--no-review", action="store_true",
                   help="не складывать подозрительное в папку брака")

    p = sub.add_parser("verdicts", help="прочитать твои вердикты из колоды «Брак»")
    p.add_argument("--deck", default="AnkiVoice_Брак")

    p = sub.add_parser("make-deck", help="клонировать + озвучить + проверить")
    p.add_argument("--voice", required=True)
    p.add_argument("--query", default="deck:Архитектура")
    p.add_argument("--to-deck", default=None)
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--mode", choices=["sentence", "expression", "both"], default="both")
    p.add_argument("--sentence-src", default=None, help="поле с текстом предложения")
    p.add_argument("--sentence-audio", default=None, help="поле для звука предложения")
    p.add_argument("--word-src", default=None, help="поле со словом")
    p.add_argument("--word-audio", default=None, help="поле для звука слова")
    p.add_argument("--furigana-src", default=None,
                   help="поле с фуриганой основного слова (по умолчанию "
                        "ExpressionFurigana)")
    p.add_argument("--reading", default="",
                   help="режим чтения: \"\" — авто (есть фуригана — термин "
                        "читается по ней, нет — кандзи), mix — всегда по "
                        "фуригане, asis — только кандзи")
    p.add_argument("--tag", default=None)
    p.add_argument("--force", action="store_true")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--speed", type=float, default=1.0)

    p = sub.add_parser("check", help="проверить колоду")
    p.add_argument("--deck", required=True)
    p.add_argument("--sentence-audio", default=None, help="поле для звука предложения")
    p.add_argument("--word-audio", default=None, help="поле для звука слова")
    p.add_argument("--fast", action="store_true",
                   help="не качать аудиофайлы из Anki — только проверить поля")

    p = sub.add_parser("scan", help="найти голоса в папке движка и добавить в voices.json")
    p.add_argument("--apply", action="store_true",
                   help="записать новые голоса в voices.json (без флага — только показать)")
    p.add_argument("--json", action="store_true", help="машинночитаемый вывод (для GUI)")

    sub.add_parser("selftest", help="проверить файлы/референсы/Anki/сервер")

    p = sub.add_parser("qc-deck", help="собрать отбракованный синтез в колоду Anki "
                                       "(чтобы послушать и оценить детектор)")
    p.add_argument("--clean", action="store_true",
                   help="сначала убрать старые карточки колоды")
    p.add_argument("--deck", default="AnkiVoice_Брак",
                   help="имя колоды (по умолчанию AnkiVoice_Брак)")

    p = sub.add_parser("cleanup-media",
                       help="найти (и с --apply удалить) осиротевшие "
                            "tts_*.ogg/wav в медиа Anki")
    p.add_argument("--deck", default=None,
                   help="сверять ссылки только с этой колодой (по умолчанию "
                        "— со всей коллекцией)")
    p.add_argument("--apply", action="store_true",
                   help="удалить найденный мусор (без флага — только отчёт)")

    p = sub.add_parser("preview",
                       help="предпросмотр озвучки без синтеза: что уйдёт в "
                            "TTS, режим каждой карточки и результат "
                            "подстановки фуриганы")
    p.add_argument("--voice")
    p.add_argument("--voices", default="",
                   help="показать раскладку ансамбля «a,b,c» — как её "
                        "сделает реальный прогон")
    p.add_argument("--deck", default=None)
    p.add_argument("--ids", nargs="*", default=None)
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--mode", choices=["sentence", "expression", "both"],
                   default="both")
    p.add_argument("--new", action="store_true",
                   help="предпросмотреть только карточки без av_voiced")
    p.add_argument("--sentence-src", default=None)
    p.add_argument("--sentence-audio", default=None)
    p.add_argument("--word-src", default=None)
    p.add_argument("--word-audio", default=None)
    p.add_argument("--furigana-src", default=None)
    p.add_argument("--reading", default="")
    p.add_argument("--force", action="store_true")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--tag", default=None)

    args = ap.parse_args()
    if not args.cmd:
        menu()
        return
    # команды, которым нужен один работающий экземпляр (гонка за веса/сервер)
    if args.cmd in ("server", "serve", "test", "clone", "voice", "make-deck"):
        acquire_lock()
    result = {"list": cmd_list, "add": cmd_add, "server": cmd_server,
              "indextts-server": cmd_indextts_server,
              "serve": cmd_serve, "test": cmd_test,
              "clone": cmd_clone, "voice": cmd_voice, "make-deck": cmd_make_deck,
              "check": cmd_check, "scan": cmd_scan, "qc-deck": cmd_qc_deck,
              "verify": cmd_verify, "verdicts": cmd_verdicts,
              "selftest": cmd_selftest,
              "cleanup-media": cmd_cleanup_media,
              "preview": cmd_preview}[args.cmd](args)
    if args.cmd == "check" and result is False:
        sys.exit(1)


if __name__ == "__main__":
    main()
