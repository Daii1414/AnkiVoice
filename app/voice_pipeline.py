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
import json
import os
import re
import sys
import time

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

# ------------------------------------------------- sys.path для пакетного Python
# Python из пакета GPT-SoVITS жёстко задаёт sys.path через python39._pth:
# папка этого скрипта туда не попадает, и «from paths import ...» падает с
# ModuleNotFoundError. Гарантируем свою папку первым элементом sys.path.
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

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
import oscompat
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

from voicing import (  # noqa: F401 — фасад
    LAST_RUN_FILE,
    VOICED_MANIFEST_FILE,
    _LOCK_HANDLE,
    _audio_hash,
    _field_title,
    _filter_changed_jobs,
    _mode_title,
    _write_last_run,
    acquire_lock,
    assign_voices,
    check_deck,
    clone_cards,
    load_voiced_manifest,
    read_last_run,
    save_voiced_manifest,
    voice_notes,
)

from tts import (  # noqa: F401 — фасад
    BASELINE_FILE,
    BASE_DROP_FAIL,
    BASE_DROP_SUSPECT,
    COVER_FAIL_ABS,
    COVER_FLOOR,
    COVER_SUSPECT_ABS,
    COVER_SUSPECT_FLOOR,
    QC_REJECT_DIR,
    SUSPECT_TAG,
    _PRON,
    _PRON_STATE,
    _QC_ATTEMPTS,
    _QC_ATTEMPTS_INDEX,
    _QC_BLIND,
    _QC_V2,
    _RESURRECT,
    _check_audio,
    _ffmpeg_exe,
    _pron_verifier,
    _qc_v2_module,
    _resurrect,
    _synth_is_sane,
    _synth_once,
    _synth_once_indextts,
    _tts_start_config,
    audio_stats,
    baseline_limits,
    baseline_path,
    keep_rejected,
    load_baselines,
    mark_suspect,
    media_name,
    pron_status,
    save_baselines,
    split_method_for,
    synth,
    update_baseline,
)
from jobs import (  # noqa: F401 — фасад
    _human_dur,
    _plural,
    _speakable,
    build_jobs,
    reading_mode,
    term_has_latin,
    word_text,
)

# движок резолвим сразу (не бросает исключений: нет движка — av_state.ENGINE
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
    eng = av_state.ENGINE or ""

    def _locate(path, what):
        """Путь к файлу: как указан, иначе — от папки движка.

        В voices.json относительные пути считаются от движка, поэтому и
        здесь «GPT_weights_v2/x.ckpt» ищем там, а не в текущей папке.
        """
        p = os.path.expanduser(path)
        if not os.path.exists(p) and eng and not os.path.isabs(p):
            p = os.path.join(eng, p)
        if not os.path.exists(p):
            raise SystemExit("Не найден файл %s: %s" % (what, path))
        return os.path.abspath(p)

    def _store(p):
        """Внутри движка — относительный путь (переносимо), иначе абсолютный."""
        if eng and os.path.commonpath([p, os.path.abspath(eng)]) == os.path.abspath(eng):
            return os.path.relpath(p, eng)
        return p

    gpt = _locate(args.gpt, "GPT-веса")
    sovits = _locate(args.sovits, "SoVITS-веса")
    ref = _locate(args.ref, "референс")
    dur = ref_duration(ref)
    if dur is not None and not (3.0 <= dur <= 10.0):
        raise SystemExit("Референс %.1f с — API требует 3–10 с. Вырежи другой кусок." % dur)
    cfg["voices"][args.name] = {
        "display": args.display or args.name,
        "gpt": _store(gpt),
        "sovits": _store(sovits),
        "ref": _store(ref),
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
    print("Текст: %s\nКана: %s" % (args.text, text))
    from voicing import _voice_params
    vseed, vspeed = _voice_params(v, args.seed, args.speed)
    blob, ext, _sinfo = synth(v, text, seed=vseed, speed=vspeed)
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
            if args.force or getattr(args, "changed", False):
                # «Пересобрать всё заново» + лимит: берём первые N карточек
                # колоды и переозвучиваем их. Раньше лимит отбрасывал уже
                # озвученные карточки, и пересборка не работала вовсе.
                # То же для «только изменённых»: изменённая карточка уже
                # озвучена, среди «ждущих звука» её нет.
                ids = ids[:args.limit]
            else:
                ids = _pending_notes(ids, args.limit, fields, mode=args.mode)
    elif tag:
        ids = ac("findNotes", query='tag:"%s"' % tag)
        if args.limit:
            if args.force or getattr(args, "changed", False):
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
    from voicing import parse_ensemble
    # «sakura:60,madara:40» -> пул с повторами по весу (пропорции ансамбля)
    extra = parse_ensemble(getattr(args, "voices", "") or "")
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


def cmd_compress_media(args):
    """Пережать уже записанный звук tts_*.wav в .ogg и поправить ссылки.

    Новые движки отдают только WAV, и до 1.10 он шёл в колоду как есть —
    в 10 раз тяжелее ogg. Для каждой карточки с [sound:tts_*.wav]: файл
    сжимается в OGG Vorbis (имя то же, расширение .ogg), ссылки в полях
    заменяются, старый WAV удаляется из медиа (Anki кладёт удалённое в
    корзину медиа; --keep — оставить).
    """
    from tts import to_ogg
    query = 'deck:"%s"' % args.deck if args.deck else ""
    ids = ac("findNotes", query=query)
    inner = re.compile(r"\[(?:sound|audio):(tts_[^\]]+\.wav)\]", re.IGNORECASE)
    uses = {}                      # wav -> [(nid, поле)]
    for chunk in _chunks(ids, 400):
        for n in notes_info(chunk):
            for fname, f in (n.get("fields") or {}).items():
                for m in inner.finditer(f.get("value", "") or ""):
                    uses.setdefault(m.group(1), []).append((n["noteId"], fname))
    if not uses:
        print("WAV-озвучек в карточках нет — сжимать нечего.")
        return
    print("WAV-озвучек: %d — сжимаю в ogg..." % len(uses))
    renamed, before, after, failed = {}, 0, 0, 0
    for i, wav in enumerate(sorted(uses), 1):
        try:
            data = ac("retrieveMediaFile", filename=wav)
            if not data:
                print("  нет файла в медиа: %s" % wav)
                failed += 1
                continue
            blob = base64.b64decode(data)
            ogg_blob, ext = to_ogg(blob, "wav")
            if ext != "ogg":
                raise RuntimeError("ffmpeg не сжал файл")
            new = wav[:-4] + ".ogg"
            ac("storeMediaFile", filename=new, overwrite=True,
               data=base64.b64encode(ogg_blob).decode("ascii"))
            renamed[wav] = new
            before += len(blob)
            after += len(ogg_blob)
        except Exception as e:
            print("  не удалось: %s — %s" % (wav, e))
            failed += 1
        if i % 20 == 0:
            print("  %d / %d" % (i, len(uses)))
    # ссылки: одна правка на поле, даже если в нём несколько файлов
    edits = {}
    for wav, new in renamed.items():
        for nid, fname in uses[wav]:
            edits.setdefault(nid, set()).add(fname)
    fixed = 0
    for chunk in _chunks(sorted(edits), 400):
        for n in notes_info(chunk):
            upd = {}
            for fname in edits[n["noteId"]]:
                val = n["fields"][fname]["value"]
                for wav, new in renamed.items():
                    val = val.replace(wav, new)
                upd[fname] = val
            try:
                ac("updateNoteFields", note={"id": n["noteId"], "fields": upd})
                fixed += 1
            except Exception as e:
                print("  карточка %s не обновлена: %s" % (n["noteId"], e))
                # ссылка осталась на wav — его не трогаем
                for wav in list(renamed):
                    if any(nid == n["noteId"] for nid, _f in uses[wav]):
                        renamed.pop(wav)
    removed = 0
    if not args.keep:
        for wav in renamed:
            try:
                ac("deleteMediaFile", filename=wav)
                removed += 1
            except Exception as e:
                print("  не удалось удалить %s: %s" % (wav, e))
    print("Готово: %d файлов сжато, карточек обновлено: %d, ошибок: %d."
          % (len(renamed), fixed, failed))
    if before:
        print("Размер: %.1f МБ -> %.1f МБ (в %.0f раз меньше)."
              % (before / 1048576.0, after / 1048576.0, before / max(after, 1)))
    if removed:
        print("Старые WAV удалены из медиа (%d) — Anki держит их в корзине "
              "медиа до «Проверки медиа»." % removed)


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
    jobs = build_jobs(notes, args.mode,
                      args.force or getattr(args, "changed", False),
                      fields=fields)
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
    from voicing import parse_ensemble
    extra = parse_ensemble(getattr(args, "voices", "") or "")
    names = []
    for n in ([args.voice] if args.voice else []) + extra:
        if n and n not in names:
            names.append(n)
    # тот же пул с весами, что и в voice_notes
    if args.voice and args.voice not in extra:
        pool = [args.voice] + extra
    else:
        pool = extra or names
    if len(names) > 1:
        prior = {}
        for n in names:
            try:
                for i in ac("findNotes", query='tag:"av_voice::%s"' % n):
                    prior[i] = n
            except Exception:
                pass
        voice_by_nid = assign_voices({j[0] for j in jobs}, pool,
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
        try:
            v = get_voice(None)          # голос по умолчанию из voices.json
        except SystemExit:
            v = None
        for row in report:
            if not row.get("verdict", "").startswith(("пропущено", "не то",
                                                      "подозрительно")):
                continue
            voice = row.get("voice") or (v["name"] if v else None)
            try:
                vv = get_voice(voice)
            except (Exception, SystemExit):   # get_voice бросает SystemExit
                vv = v
            text = row.get("expected") or ""
            if not text or vv is None:
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
        # notesInfo ждёт id ЗАМЕТОК: findCards давал id карточек, и уже
        # созданные карточки брака не находились никогда
        ids = ac("findNotes", query='deck:"%s"' % deck) or []
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
    hist_path = os.path.join(oscompat.app_dir(), "verdicts_history.json")
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
            # qc-deck пишет звук как [sound:имя]; «Файл:» — старый формат
            m = re.search(r"\[sound:([^\]]+)\]|Файл:\s*(\S+)",
                          v.get("value") or "")
            if m:
                rec = index.get(m.group(1) or m.group(2))
                if rec:
                    cov = rec.get("coverage")
        low = verdict.lower()
        item = (cov, n["noteId"])
        if any(w in low for w in ("хорош", "норм", "ложн", "нет", "ok")):
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
        if any(w in low0 for w in ("хорош", "норм", "ложн", "нет", "ok")):
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


def cmd_fetch_asr(args):
    """Скачать модель faster-whisper для проверки произношения (один раз).

    Качает в общий кэш HuggingFace — там её и ищет pron_check. Работает в
    Python движка: huggingface_hub там уже стоит (его тянет transformers).
    """
    model = args.model or "Systran/faster-whisper-medium"
    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        raise SystemExit("В Python движка нет huggingface_hub — модель скачать нечем.")
    print("Скачиваю %s (около 1,5 ГБ, один раз)..." % model)
    path = snapshot_download(repo_id=model)
    print("Готово: %s" % path)
    print("Проверка произношения теперь доступна — включи её в «Дополнительных настройках».")


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
        ok("%s на месте: %s" % (oscompat.engine_python_label(), av_state.PYTHON))
    else:
        fail("нет %s: %s" % (oscompat.engine_python_label(), av_state.PYTHON))

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
    # Защита от UnicodeEncodeError в консоли Windows (cp1252) при выводе
    # путей с кириллицей/японскими символами (путь к проекту содержит
    # русские символы, а текст содержит японские иероглифы).
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    if hasattr(sys.stderr, "reconfigure"):
        try:
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
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
    p.add_argument("--seed", type=int, default=None,
                   help="по умолчанию — seed голоса из voices.json (иначе 42)")
    p.add_argument("--speed", type=float, default=None,
                   help="по умолчанию — скорость голоса (иначе 1.0)")

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
    p.add_argument("--seed", type=int, default=None,
                   help="по умолчанию — seed каждого голоса из voices.json")
    p.add_argument("--speed", type=float, default=None,
                   help="по умолчанию — скорость каждого голоса из voices.json")
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
    p.add_argument("--seed", type=int, default=None,
                   help="по умолчанию — seed каждого голоса из voices.json")
    p.add_argument("--speed", type=float, default=None,
                   help="по умолчанию — скорость каждого голоса из voices.json")

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
    p = sub.add_parser("fetch-asr", help="скачать модель faster-whisper для проверки произношения")
    p.add_argument("--model", default=None,
                   help="репозиторий HuggingFace (по умолчанию Systran/faster-whisper-medium)")

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

    p = sub.add_parser("compress-media",
                       help="пережать записанный звук tts_*.wav в .ogg "
                            "и поправить ссылки в карточках")
    p.add_argument("--deck", default=None,
                   help="только эта колода (по умолчанию — вся коллекция)")
    p.add_argument("--keep", action="store_true",
                   help="не удалять старые WAV из медиа")

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
    p.add_argument("--changed", action="store_true",
                   help="как у voice: смотреть и уже озвученные карточки")
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
              "fetch-asr": cmd_fetch_asr,
              "cleanup-media": cmd_cleanup_media,
              "compress-media": cmd_compress_media,
              "preview": cmd_preview}[args.cmd](args)
    if args.cmd == "check" and result is False:
        sys.exit(1)


if __name__ == "__main__":
    main()