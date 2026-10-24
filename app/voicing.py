# -*- coding: utf-8 -*-
"""Прогон озвучки: voice_notes() и всё, что его обслуживает.

Ансамбль (assign_voices — случайное распределение карточек по голосам),
теги av_voiced/av_voice, итог прогона (last_run.json), манифест
озвученного для «Пересобрать только изменённые» (voiced_manifest.json),
человекочитаемые отчёты run_*.md, блокировка второго экземпляра.
"""
import base64
import hashlib
import json
import os
import random
import re
import re
import time

import av_state
from anki_api import _chunks, ac, notes_info, plain
from engines import ensure_voice, require_engine
from fields_config import DEFAULT_FIELDS, audio_fields
from jobs import _human_dur, _plural, build_jobs
from tts import (_PRON_STATE, media_name, synth)
from voices import get_voice

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


def parse_ensemble(spec):
    """Разобрать спецификацию ансамбля: "a,b" или "a:60,b:40".

    Возвращает пул имён, сохраняющий пропорции в минимальном объёме:
    60/40 -> 3 и 2 вхождения (сокращение через НОД), a:2,b -> 2 и 1,
    без веса -> 1. Пул передаётся в assign_voices: rng.choice(pool)
    даёт нужные пропорции. Вес 0 (или мусор вместо числа с ":" пустым)
    исключает голос; мусорные части игнорируются.
    """
    import math
    pairs = []
    for part in (spec or "").split(","):
        part = part.strip()
        if not part:
            continue
        name, _, w = part.partition(":")
        name = name.strip()
        if not name or not re.fullmatch(r"[\w\- ]+", name):
            continue                        # мусор вместо имени голоса
        if w.strip():
            try:
                weight = int(w)
            except ValueError:
                weight = 1                  # вес не число — берём голос
        else:
            weight = 1                      # вес не указан
        if weight > 0:
            pairs.append((name, weight))
    if not pairs:
        return []
    g = 0
    for _n, w in pairs:
        g = math.gcd(g, w)
    g = g or 1
    pool = []
    for name, w in pairs:
        pool.extend([name] * (w // g))
    return pool


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
    # extra_voices — ПУЛ (с повторами по весу из parse_ensemble):
    # ["sakura", "sakura", "madara"] = пропорция 2:1
    names = []
    for n in [voice_name] + list(extra_voices or []):
        n = (n or "").strip()
        if n and n not in names:
            names.append(n)
    voices = {n: get_voice(n) for n in names}
    pool = [n.strip() for n in ([voice_name] + list(extra_voices or []))
            if (n or "").strip()]
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
        assign = assign_voices({j[0] for j in jobs}, pool, seed=seed,
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
    lockp = os.path.join(av_state.av_state.ENGINE, "logs", "pipeline.lock")
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
