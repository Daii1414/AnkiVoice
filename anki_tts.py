# -*- coding: utf-8 -*-
"""
anki_tts.py — озвучка карточек Anki голосом ShoHayami через GPT-SoVITS.

Что делает:
  1. берёт японский текст из карточки (Sentence или Expression/чтение);
  2. синтезирует речь через локальный API GPT-SoVITS (модель v2ProPlus ShoHayami);
  3. кладёт файл в медиа-библиотеку Anki (AnkiConnect storeMediaFile);
  4. прописывает [sound:...] в поле SentenceAudio / ExpressionAudio —
     шаблон карточки Kiku Personal рендерит оба этих поля, так что
     звук будет играть прямо в карточке.

Если сервер GPT-SoVITS не запущен — скрипт поднимает его сам и дожидается.

Запуск (из папки GPT-SoVITS, там же лежит скрипт):
    runtime\\python.exe anki_tts.py                      # 1 карточка (первая без звука)
    runtime\\python.exe anki_tts.py --mode both          # слово + предложение
    runtime\\python.exe anki_tts.py --limit 20           # 20 карточек подряд
    runtime\\python.exe anki_tts.py --ids 1787850678199  # конкретная карточка
    runtime\\python.exe anki_tts.py --query "deck:Архитектура 溶接"
    runtime\\python.exe anki_tts.py --limit 5 --dry-run  # только показать, что будет

Требования: запущен Anki с AnkiConnect.
"""

import argparse
import base64
import hashlib
import json
import os
import re
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

# ---------------------------------------------------------------- пути/адреса
HERE = os.path.dirname(os.path.abspath(__file__))
ANKI_CONNECT = "http://localhost:8765"
TTS_HOST, TTS_PORT = "127.0.0.1", 9880
TTS_URL = "http://%s:%d" % (TTS_HOST, TTS_PORT)

REF_AUDIO = os.path.join(HERE, "ref_main_6s.wav")           # основной референс (3~10 с)
AUX_REF_AUDIO = os.path.join(HERE, "ref_aux_60s.wav")       # длинный, для смешения тона
REF_PROMPT_TEXT = "無力な仲間の存在はただ足をへし折るための重りにしかなりはしないのだ"
REF_PROMPT_LANG = "ja"
TTS_CONFIG = os.path.join(HERE, "GPT_SoVITS", "configs", "tts_infer_shohayami.yaml")

# ------------------------------------------------------------------ голоса
# Каждый голос = свои веса GPT+SoVITS, свой основной референс (3~10 с),
# свой текст к нему (prompt_text) и свой aux-клип для смешения тона.
VOICES = {
    "shohayami": {
        "config": os.path.join(HERE, "GPT_SoVITS", "configs", "tts_infer_shohayami.yaml"),
        "ref": os.path.join(HERE, "ref_main_6s.wav"),
        "aux": os.path.join(HERE, "ref_aux_60s.wav"),
        "prompt_text": "無力な仲間の存在はただ足をへし折るための重りにしかなりはしないのだ",
        "prompt_lang": "ja",
    },
    "madara": {
        "config": os.path.join(HERE, "GPT_SoVITS", "configs", "tts_infer_madara.yaml"),
        "ref": os.path.join(HERE, "ref_main_madara.wav"),
        "aux": os.path.join(HERE, "ref_aux_madara_60s.wav"),
        "prompt_text": "この戦力さ、貴様ら二人がどうにかできるものではないぞ。おかしな奴だ。",
        "prompt_lang": "ja",
    },
}
DEFAULT_VOICE = "shohayami"
ACTIVE_VOICE_FILE = os.path.join(HERE, "logs", "active_voice.txt")
PYTHON = os.path.join(HERE, "runtime", "python.exe")
SERVER_LOG = os.path.join(HERE, "logs", "api_v2_anki.log")


# ------------------------------------------------------------- AnkiConnect
def ac(action, **params):
    payload = {"action": action, "version": 6, "params": params}
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        ANKI_CONNECT, data=data,
        headers={"Content-Type": "application/json", "Origin": "http://localhost"},
    )
    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
            out = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as e:
        raise SystemExit("AnkiConnect недоступен (%s). Открой Anki и повтори." % e)
    if out.get("error"):
        raise SystemExit("AnkiConnect: %s" % out["error"])
    return out["result"]


# ------------------------------------------------------------ GPT-SoVITS API
def tts_ready():
    try:
        s = socket.create_connection((TTS_HOST, TTS_PORT), timeout=2)
        s.close()
        return True
    except OSError:
        return False


def active_voice():
    try:
        with open(ACTIVE_VOICE_FILE, encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return None


def set_active_voice(name):
    os.makedirs(os.path.dirname(ACTIVE_VOICE_FILE), exist_ok=True)
    with open(ACTIVE_VOICE_FILE, "w", encoding="utf-8") as f:
        f.write(name)


def tts_stop_server():
    """Убить API-сервер, если он запущен (по PID из /control info)."""
    if not tts_ready():
        return
    try:
        req = urllib.request.Request(TTS_URL + "/control?command=help")
        urllib.request.urlopen(req, timeout=5).read()
    except Exception:
        pass
    # pid слушателя порта
    try:
        out = subprocess.run(
            ["netstat", "-ano"], capture_output=True, text=True, timeout=20)
        pid = None
        for line in out.stdout.splitlines():
            if (":%d" % TTS_PORT) in line and "LISTENING" in line:
                pid = line.split()[-1]
                break
        if pid:
            subprocess.run(["taskkill", "/PID", pid, "/F"],
                           capture_output=True, timeout=20)
            time.sleep(2)
    except Exception as e:
        print("не удалось остановить сервер:", e)


def tts_start_server(voice=DEFAULT_VOICE, wait=600):
    """Поднять API-сервер GPT-SoVITS с нужными весами и дождаться порт.

    Если сервер уже работает с другим голосом — перезапускаем.
    """
    v = VOICES[voice]
    if tts_ready():
        if active_voice() == voice:
            return                          # уже работает с этим голосом
        print("Сервер работает с голосом '%s', перезапускаю на '%s'..."
              % (active_voice(), voice))
        tts_stop_server()
    os.makedirs(os.path.dirname(SERVER_LOG), exist_ok=True)
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    log = open(SERVER_LOG, "a", encoding="utf-8")
    subprocess.Popen(
        [PYTHON, "-u", "api_v2.py", "-a", TTS_HOST, "-p", str(TTS_PORT),
         "-c", os.path.relpath(v["config"], HERE)],
        cwd=HERE, env=env, stdout=log, stderr=subprocess.STDOUT,
    )
    set_active_voice(voice)
    print("Запускаю GPT-SoVITS (голос '%s')... ждём до %d с" % (voice, wait))
    t0 = time.time()
    while time.time() - t0 < wait:
        if tts_ready():
            time.sleep(1)
            print("GPT-SoVITS готов (%.0f с)" % (time.time() - t0))
            return
        time.sleep(2)
    raise SystemExit("Сервер GPT-SoVITS не поднялся за %d с, см. %s" % (wait, SERVER_LOG))


def tts(text, text_lang="ja", prompt_text=None, prompt_lang="ja",
        media_type="ogg", seed=42, speed=1.0, voice=DEFAULT_VOICE,
        ref=None, aux_ref=None):
    """Синтез. Возвращает байты аудио."""
    v = VOICES[voice]
    if prompt_text is None:
        prompt_text = v["prompt_text"]
    if prompt_lang is None:
        prompt_lang = v["prompt_lang"]
    if ref is None:
        ref = v["ref"]
    if aux_ref is None:
        aux_ref = v["aux"]
    payload = {
        "text": text,
        "text_lang": text_lang,
        "ref_audio_path": ref,
        "aux_ref_audio_paths": [aux_ref] if aux_ref else [],
        "prompt_text": prompt_text,
        "prompt_lang": prompt_lang,
        "text_split_method": "cut5",
        "batch_size": 1,
        "speed_factor": speed,
        "media_type": media_type,
        "streaming_mode": False,
        "seed": seed,
    }
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(TTS_URL + "/tts", data=data,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
            return resp.read()
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        if media_type == "ogg":      # ogg не всегда доступен — откат на wav
            return tts(text, text_lang, prompt_text, prompt_lang,
                       media_type="wav", seed=seed, speed=speed, voice=voice,
                       ref=ref, aux_ref=aux_ref)
        raise SystemExit("GPT-SoVITS вернул %d: %s" % (e.code, body[:300]))


# ---------------------------------------------------------------- утилиты
TAG_RE = re.compile(r"<[^>]+>")
BRACKET_RE = re.compile(r"\[([^\[\]]*)\]")


def plain(v):
    return TAG_RE.sub("", v or "").strip()


def reading_of(note):
    """Чтение слова: ExpressionReading → фуригана в квадратных скобках → сам Expression."""
    f = note["fields"]
    r = plain(f.get("ExpressionReading", {}).get("value", ""))
    if r:
        return r
    furi = plain(f.get("ExpressionFurigana", {}).get("value", ""))
    if "[" in furi:
        r = BRACKET_RE.search(furi)
        if r and r.group(1).strip():
            return r.group(1).strip()
    return plain(f.get("Expression", {}).get("value", ""))


def safe_name(s, limit=40):
    s = re.sub(r"[^\w\-]", "_", s, flags=re.UNICODE)[:limit]
    return s.strip("_") or "x"


def build_plan(note, mode, force):
    """Вернуть список (поле-источник, поле-цель, текст) для этой карточки."""
    f = note["fields"]
    plan = []

    def tgt(field):
        return plain(f.get(field, {}).get("value", ""))

    if mode in ("sentence", "both"):
        text = plain(f.get("Sentence", {}).get("value", ""))
        if text and (force or not tgt("SentenceAudio")):
            plan.append(("Sentence", "SentenceAudio", text))

    if mode in ("expression", "both"):
        text = reading_of(note)
        if text and (force or not tgt("ExpressionAudio")):
            plan.append(("Expression(чтение)", "ExpressionAudio", text))

    return plan


def media_name(nid, field, text, ext, voice=DEFAULT_VOICE):
    h = hashlib.sha1(("v1|%d|%s|%s|%s" % (nid, field, text, voice)).encode("utf-8")).hexdigest()[:10]
    return "tts_%s_%d_%s_%s.%s" % (safe_name(voice), nid, safe_name(field), h, ext)


# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser(description="Озвучка карточек Anki голосом GPT-SoVITS")
    ap.add_argument("--voice", choices=sorted(VOICES), default=DEFAULT_VOICE,
                    help="голос (по умолчанию %s)" % DEFAULT_VOICE)
    ap.add_argument("--mode", choices=["sentence", "expression", "both"],
                    default="sentence",
                    help="sentence = предложение, expression = слово, both = и то и другое")
    ap.add_argument("--query", default="deck:Архитектура", help="поиск карточек Anki")
    ap.add_argument("--ids", nargs="*", type=int, help="конкретные note id")
    ap.add_argument("--limit", type=int, default=1, help="сколько карточек озвучить")
    ap.add_argument("--force", action="store_true",
                    help="перегенерировать, даже если поле уже со звуком")
    ap.add_argument("--dry-run", action="store_true", help="ничего не писать, только показать план")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--speed", type=float, default=1.0)
    ap.add_argument("--no-start-server", action="store_true",
                    help="не поднимать GPT-SoVITS автоматически")
    args = ap.parse_args()

    if args.ids:
        ids = list(args.ids)
    else:
        # берём пул карточек и останавливаемся после limit тех, что реально требуют озвучки
        pool = ac("findNotes", query=args.query)
        ids = pool[: max(args.limit * 10, 50)]
    if not ids:
        raise SystemExit("По запросу ничего не найдено: %s" % args.query)

    notes = ac("notesInfo", notes=ids)

    # собираем план, не больше limit карточек
    jobs = []
    used_notes = set()
    for n in notes:
        plan = build_plan(n, args.mode, args.force)
        if not plan:
            continue
        if n["noteId"] not in used_notes:
            if len(used_notes) >= args.limit:
                break
            used_notes.add(n["noteId"])
        for src_field, tgt_field, text in plan:
            jobs.append((n["noteId"], n, src_field, tgt_field, text))

    if not jobs:
        print("Всё уже озвучено (или пустой текст). Use --force, чтобы переделать.")
        return

    print("К озвучке: %d операций в %d карточках (mode=%s)" %
          (len(jobs), len({j[0] for j in jobs}), args.mode))
    for nid, n, src, tgt, text in jobs:
        print("  [%d] %-20s -> %-16s %s" % (nid, src, tgt, text[:60]))

    if args.dry_run:
        print("\n--dry-run: ничего не записано.")
        return

    if not args.no_start_server:
        tts_start_server(args.voice)
    if not tts_ready():
        raise SystemExit("GPT-SoVITS не запущен на %s" % TTS_URL)

    print("Голос: %s" % args.voice)

    done, failed = 0, 0
    cache = {}          # (text, seed, speed) -> (blob, ext), чтобы не синтезировать дважды
    for nid, n, src_field, tgt_field, text in jobs:
        try:
            key = (text, args.seed, args.speed)
            if key not in cache:
                blob = tts(text, media_type="ogg", seed=args.seed,
                           speed=args.speed, voice=args.voice)
                ext = "ogg"
                if len(blob) < 1000:
                    blob = tts(text, media_type="wav", seed=args.seed,
                               speed=args.speed, voice=args.voice)
                    ext = "wav"
                cache[key] = (blob, ext)
                time.sleep(0.3)
            blob, ext = cache[key]
            fname = media_name(nid, tgt_field, text, ext, args.voice)
            stored = ac("storeMediaFile", filename=fname,
                        data=base64.b64encode(blob).decode("ascii"))
            if stored != fname:
                fname = stored
            tag = "[sound:%s]" % fname
            ac("updateNoteFields", note={"id": nid, "fields": {tgt_field: tag}})
            done += 1
            print("OK   [%d] %-16s %s (%s, %.0f КБ)" %
                  (nid, tgt_field, tag, ext, len(blob) / 1024))
        except SystemExit as e:
            failed += 1
            print("FAIL [%d] %s: %s" % (nid, tgt_field, e))
        except Exception as e:
            failed += 1
            print("FAIL [%d] %s: %r" % (nid, tgt_field, e))

    print("\nГотово: %d, ошибок: %d" % (done, failed))


if __name__ == "__main__":
    main()
