# -*- coding: utf-8 -*-
"""Тесты v1.2: версия, парсинг релиза, SHA256 и логика мастера.

Ничего не требует от машины: сеть и GPT-SoVITS подменяются заглушками.
"""
import hashlib
import json
import os
import sys
import tempfile
import time
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
LAB = os.path.join(ROOT, "lab")
if LAB not in sys.path:
    sys.path.insert(0, LAB)

import anki_gui as ag
import anki_web as aw
import voice_pipeline as vp


def check(cond, msg):
    if not cond:
        raise AssertionError(msg)


def test_version_tuple():
    check(ag.version_tuple("v1.4.1") == (1, 4, 1), "v1.4.1")
    check(ag.version_tuple("1.10") > ag.version_tuple("1.9"), "1.10 > 1.9")
    check(ag.version_tuple("") == (0,), "empty")


class _Resp:
    def __init__(self, blob):
        self.blob = blob
        self.pos = 0
        self.headers = {"Content-Length": str(len(blob))}

    def read(self, n=-1):
        if n is None or n < 0:
            n = len(self.blob) - self.pos
        chunk = self.blob[self.pos:self.pos + n]
        self.pos += len(chunk)
        return chunk

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_release_parse():
    body = "## Что нового\n- мастер\n\nSHA256: " + "a" * 64
    fake = {
        "tag_name": "v9.9",
        "name": "AnkiVoice 9.9",
        "body": body,
        "html_url": "https://github.com/Daii1414/AnkiVoice/releases/tag/v9.9",
        "published_at": "2026-01-01T00:00:00Z",
        "assets": [{
            "name": "AnkiVoice-Setup-9.9.exe",
            "size": 123,
            "browser_download_url": "https://example.test/AnkiVoice-Setup-9.9.exe",
            "digest": None,
        }],
    }
    old = aw._github_json
    old_cache = dict(aw.UPDATE_CACHE)
    aw._github_json = lambda url, timeout=30: fake
    try:
        aw.UPDATE_CACHE.update({"at": 0.0, "data": None})
        info = aw.release_info(force=True)
        check(info["available"] is True, "v9.9 must be newer")
        check(info["asset"]["name"] == "AnkiVoice-Setup-9.9.exe", "asset")
        check(info["asset"]["sha256"] == "a" * 64, "sha from body")
    finally:
        aw._github_json = old
        aw.UPDATE_CACHE.update(old_cache)


def test_download_sha():
    data = b"installer" * 2048
    expected = hashlib.sha256(data).hexdigest()
    old_open = aw.urllib.request.urlopen
    aw.urllib.request.urlopen = lambda req, timeout=0: _Resp(data)
    try:
        d = tempfile.mkdtemp(prefix="anki_voice_v12_")
        good = os.path.join(d, "good.exe")
        aw._download_update("https://example.test/good.exe", good, expected, len(data))
        check(aw.UPDATE["phase"] == "done", "download phase")
        check(os.path.isfile(good), "good file")
        with open(good, "rb") as f:
            check(hashlib.sha256(f.read()).hexdigest() == expected, "good sha")

        bad = os.path.join(d, "bad.exe")
        aw._download_update("https://example.test/bad.exe", bad, "0" * 64, len(data))
        check(aw.UPDATE["phase"] == "error", "bad phase")
        check(not os.path.exists(bad), "bad file removed")
        check(not os.path.exists(bad + ".part"), "part removed")
        check("SHA256" in aw.UPDATE["error"], "bad error text")
    finally:
        aw.urllib.request.urlopen = old_open
        aw._update_set(phase="idle", received=0, total=0, error="", path="",
                       expected="", actual="", tag="", asset="")


def test_busy_download_no_deadlock():
    with aw.UPDATE_LOCK:
        old = dict(aw.UPDATE)
        aw.UPDATE.update(phase="downloading", received=5, total=10)
    try:
        t0 = time.time()
        snap, err = aw.start_update_download()
        check(time.time() - t0 < 1.0, "start_update_download deadlocked")
        check(err is None, "busy re-entry error")
        check(snap["phase"] == "downloading", "busy phase")
        check(snap["percent"] == 50, "busy percent")

        with aw.UPDATE_LOCK:
            aw.UPDATE.update(phase="checking", received=0, total=0)
        snap2, err2 = aw.start_update_download()
        check(err2 is None and snap2["phase"] == "checking", "checking re-entry")
    finally:
        with aw.UPDATE_LOCK:
            aw.UPDATE.clear()
            aw.UPDATE.update(old)


def test_pronunciation_compare():
    """Проверка содержания: пропущенный кусок — брак, неверное слово — подозрительно."""
    import pron_check as pc
    kana = lambda s: s

    exp, wild = pc.expected_kana_masked("Aさんに行った", kana)
    check(exp == "\ue000さんに行った"
          and wild == [True, False, False, False, False, False, False],
          "маска латиницы: %r %r" % (exp, wild))

    ok = pc.compare("きょうはあめです", [False] * 8, "きょうはあめです")
    check(ok["verdict"] == "ок" and not ok["fail"], "совпадение: %r" % ok)

    lost = pc.compare("せこうけいかくでは、いちぶのどこうさぎょうに、じどうせこうをためした",
                       [False] * 34,
                       "じんこうそんしをつづけるほうがにっこうしをだいひょうに")
    check(lost["verdict"] == "пропущено" and lost["fail"], "потерян кусок: %r" % lost)

    mis = pc.compare("びぇにゃくどのです", [False] * 10, "めにあどのです")
    check(mis["verdict"] == "подозрительно" and not mis["fail"],
          "слово прочитано не так: %r" % mis)

    # короткие фразы не судим: ASR на них ненадёжен
    short = pc.compare("はい", [False] * 2, "いいえ")
    check(short["verdict"] == "коротко" and not short["fail"], "короткое: %r" % short)


def test_split_method_is_japanese_safe():
    """Для японского не режем текст по китайским правилам (cut5 ломает фразу)."""
    check(vp.split_method_for("せこうけいかくでは、じどうせこうをためした。") == "cut0",
          "короткая фраза — целиком")
    check(vp.split_method_for("あ" * 60) == "cut2", "длинная фраза — по «。」")
    check("cut5" not in (vp.split_method_for("あ" * 10),), "cut5 не используется по умолчанию")


def test_installer_ships_runtime_modules():
    """Установщик обязан везти модули чтения и QC v2.

    Без них в установленном приложении молча отключаются доменный словарь
    и многосигнальная проверка качества (voice_pipeline.py грузит их из lab/).
    """
    with open(os.path.join(ROOT, "AnkiVoice.iss"), encoding="utf-8") as f:
        iss = f.read()
    for name in ("g2p_provenance.py", "domain_dict.py", "g2p_candidates.py",
                 "g2p_resolver.py", "quality_v2.py", "pron_check.py"):
        check(("lab\\" + name) in iss, "installer must ship lab/" + name)
    with open(os.path.join(ROOT, "lab", "g2p_candidates.py"), encoding="utf-8") as f:
        src = f.read()
    check('sys.path.append(r"' not in src, "hardcoded dev path in g2p_candidates")
    check("del _h" not in src, "del _h raises NameError and breaks the import")


def test_pending_notes_limit():
    """Лимит карточек = «сколько работы», а не «первые N в колоде».

    Карточка без звука ищется поиском Anki: в поле звука лежит [sound:...].
    """
    check(vp._qfield("Sentence Audio") == '"Sentence Audio"', "поле с пробелом в кавычках")
    check(vp._qfield("") == "SentenceAudio", "пустое имя поля")
    captured = {}

    def fake_ac(action, **kw):
        captured["action"] = action
        captured.update(kw)
        return [11, 12, 13]

    old_ac = vp.ac
    vp.ac = fake_ac
    try:
        ids = vp._pending_notes([11, 12, 13, 14], 2, vp.resolve_fields(),
                                mode="both")
        check(ids == [11, 12], "берём первые limit незаписанных")
        check(captured["action"] == "findNotes", "ищем через findNotes")
        check("-SentenceAudio:*sound*" in captured["query"], "фильтр по звуку предложения")
        check("-ExpressionAudio:*sound*" in captured["query"], "фильтр по звуку слова")
    finally:
        vp.ac = old_ac


def test_voice_args_guess_fallback():
    """Пустые поля карточки → автоподбор по полям колоды, а не пустые флаги."""
    guess = {"sentence_src": "Sentence", "sentence_audio": "SentenceAudio",
             "word_src": "Expression", "word_audio": "ExpressionAudio",
             "furigana_src": "ExpressionFurigana"}
    old = aw.deck_fields
    aw.deck_fields = lambda deck: (list(guess.values()), dict(guess))
    try:
        handler = aw.Handler.__new__(aw.Handler)
        args, _title = handler._args_voice({"voice": "narrator", "deck": "D",
                                           "mode": "both", "limit": "0"})
        check(args[args.index("--sentence-src") + 1] == "Sentence", "автоподбор текста")
        check(args[args.index("--word-audio") + 1] == "ExpressionAudio", "автоподбор звука")
        check(args[args.index("--furigana-src") + 1] == "ExpressionFurigana", "автоподбор фуриганы")
        # то, что прислал клиент, главнее автоподбора
        args2, _t2 = handler._args_voice({"voice": "narrator", "deck": "D",
                                          "mode": "both", "limit": "0",
                                          "sentence_src": "MyText"})
        check(args2[args2.index("--sentence-src") + 1] == "MyText", "выбор клиента главнее")
    finally:
        aw.deck_fields = old


def test_baseline_relative_limits():
    """Пороги считаются от своей нормы голоса, но не ниже пола."""
    import tempfile as _tf
    old_appdata = os.environ.get("APPDATA")
    tmp = _tf.mkdtemp(prefix="av_baseline_")
    os.environ["APPDATA"] = tmp
    try:
        os.makedirs(os.path.join(tmp, "AnkiVoice"), exist_ok=True)
        with open(os.path.join(tmp, "AnkiVoice", "pron_baseline.json"), "w",
                  encoding="utf-8") as f:
            json.dump({"narrator": {"median": 0.95, "p05": 0.9, "n": 100}},
                      f, ensure_ascii=False)
        lim = vp.baseline_limits("narrator")
        # своих порогов никогда не делаем мягче абсолютных
        check(abs(lim["COVER_FAIL"] - 0.55) < 0.001,
              "порог брака не мягче абсолютного: %r" % lim)
        check(abs(lim["COVER_SUSPECT"] - 0.80) < 0.001,
              "порог подозрительного не мягче абсолютного: %r" % lim)
        # другого голоса — абсолютные пороги
        check(vp.baseline_limits("kakuzu") == {}, "без базы — абсолютные пороги")
        # пол: норма не должна опустить порог ниже пола
        with open(os.path.join(tmp, "AnkiVoice", "pron_baseline.json"), "w",
                  encoding="utf-8") as f:
            json.dump({"narrator": {"median": 0.70, "n": 100}}, f, ensure_ascii=False)
        lim2 = vp.baseline_limits("narrator")
        check(abs(lim2["COVER_FAIL"] - 0.50) < 0.001,
              "слабый голос -> строже: %r" % lim2)
        check(lim2["COVER_FAIL"] >= vp.COVER_FLOOR, "порог не ниже пола: %r" % lim2)
        check(lim2["COVER_SUSPECT"] >= vp.COVER_SUSPECT_FLOOR,
              "порог подозрительного не ниже пола: %r" % lim2)
        # сильный голос (норма 1.0) — остаются абсолютные пороги
        with open(os.path.join(tmp, "AnkiVoice", "pron_baseline.json"), "w",
                  encoding="utf-8") as f:
            json.dump({"narrator": {"median": 1.0, "n": 100}}, f, ensure_ascii=False)
        lim3 = vp.baseline_limits("narrator")
        check(abs(lim3["COVER_FAIL"] - 0.55) < 0.001,
              "норма 1.0 -> абсолютный порог: %r" % lim3)
    finally:
        if old_appdata is None:
            os.environ.pop("APPDATA", None)
        else:
            os.environ["APPDATA"] = old_appdata


def test_profile_fields_per_deck():
    """У каждой колоды — свои настройки полей."""
    import tempfile as _tf
    old_appdata = os.environ.get("APPDATA")
    tmp = _tf.mkdtemp(prefix="av_profile_")
    os.environ["APPDATA"] = tmp
    try:
        os.makedirs(os.path.join(tmp, "AnkiVoice"), exist_ok=True)
        with open(os.path.join(tmp, "AnkiVoice", "config.json"), "w",
                  encoding="utf-8") as f:
            json.dump({"profiles": {"Колода A": {"sentence_src": "Text",
                                                "word_src": "Term"}}},
                      f, ensure_ascii=False)
        prof = vp.profile_for("Колода A")
        check(prof.get("sentence_src") == "Text", "профиль колоды: %r" % prof)

        class _A:
            deck = "Колода A"
            sentence_src = None
            sentence_audio = None
            word_src = None
            word_audio = None
            furigana_src = None
            reading = None
        f = vp._fields_from_args(_A(), deck="Колода A")
        check(f["sentence_src"] == "Text", "поля из профиля: %r" % f)
        check(f["word_src"] == "Term", "слово из профиля: %r" % f)
        # колода без профиля — дефолты пайплайна
        f2 = vp._fields_from_args(_A(), deck="Колода B")
        check(f2["sentence_src"] == "Sentence", "дефолт без профиля: %r" % f2)
    finally:
        if old_appdata is None:
            os.environ.pop("APPDATA", None)
        else:
            os.environ["APPDATA"] = old_appdata


def test_check_targets_spoken_text():
    """Проверка звука идёт по произнесённому, а не по исходному полю."""
    note = {"noteId": 1, "fields": {
        "Expression": {"value": "\u30a2\u30a4\u30ea\u30f3\u30b0\u30fb\u30cc\u30fc\u30c8\u30bb\u30f3\u306e\u6b8b\u97ff\u5f0f"},
        "ExpressionFurigana": {"value": "\u30a2\u30a4\u30ea\u30f3\u30b0[\u3056\u3093\u304d\u3087\u3046\u3057\u304d]\u306e\u6b8b\u97ff\u5f0f"},
        "ExpressionAudio": {"value": ""}}}
    fields = {"sentence_src": "Sentence", "sentence_audio": "SentenceAudio",
              "word_src": "Expression", "word_audio": "ExpressionAudio",
              "furigana_src": "ExpressionFurigana", "reading": "off"}
    jobs = vp.build_jobs([note], "expression", True, fields=fields)
    check(len(jobs) == 1, "одна работа: %r" % (jobs,))
    job = jobs[0]
    spoken = job[2]
    src_text = job[3]
    check(len(spoken) < len(src_text),
          "произнесённое короче исходного: %r vs %r" % (spoken, src_text))
    check(vp.check_target(job) == spoken,
          "сверяем с произнесённым: %r" % vp.check_target(job))


def test_reading_mode_auto():
    """Авто-режим: есть фуригана — чтение по ней, нет — кандзи."""
    fields = {"sentence_src": "Sentence", "sentence_audio": "SentenceAudio",
              "word_src": "Expression", "word_audio": "ExpressionAudio",
              "furigana_src": "ExpressionFurigana", "reading": ""}
    with_f = {"fields": {"ExpressionFurigana": {"value": "\u65e2\u5b58\u5254\u4f53[\u3056\u3093\u304d\u3087\u3046\u3057\u304d]"}}}
    without_f = {"fields": {"ExpressionFurigana": {"value": ""}}}
    check(vp.reading_mode(fields, with_f, "") == "mix", "\u0441 \u0444\u0443\u0440\u0438\u0433\u0430\u043d\u043e\u0439 -> mix")
    check(vp.reading_mode(fields, without_f, "") == "asis", "\u0431\u0435\u0437 \u0444\u0443\u0440\u0438\u0433\u0430\u043d\u044b -> asis")
    check(vp.reading_mode(fields, with_f, "asis") == "asis", "\u044f\u0432\u043d\u044b\u0439 asis \u0432\u044b\u0438\u0433\u0440\u0430\u044f\u0435\u0442")
    check(vp.reading_mode(fields, without_f, "mix") == "mix", "\u044f\u0432\u043d\u044b\u0439 mix \u0432\u044b\u0438\u0433\u0440\u0430\u044f\u0435\u0442")

    # \u043a\u0430\u043a \u0443\u0445\u043e\u0434\u0438\u0442 \u0432 \u0440\u0435\u0436\u0438\u043c\u0435 \u043a\u0430\u043d\u0434\u0437\u0438 \u0434\u043b\u044f \u0444\u0440\u0430\u0437\u044b
    note = {"noteId": 1, "fields": {
        "Sentence": {"value": "\u65e2\u5b58\u5254\u4f53\u306f\u8010\u706b\u6027\u80fd\u3092\u78ba\u8a8d\u3059\u308b\u3002"},
        "Expression": {"value": "\u65e2\u5b58\u5254\u4f53"},
        "ExpressionFurigana": {"value": "\u65e2\u5b58\u5254\u4f53[\u3056\u3093\u304d\u3087\u3046\u3057\u304d]"}}}
    jobs = vp.build_jobs([note], "both", True, fields=fields)
    sent = [j for j in jobs if j[1] == "SentenceAudio"][0][2]
    word = [j for j in jobs if j[1] == "ExpressionAudio"][0][2]
    check("\u3056\u3093\u304d\u3087\u3046\u3057\u304d" in sent, "\u0447\u0442\u0435\u043d\u0438\u0435 \u0442\u0435\u0440\u043c\u0438\u043d\u0430 \u0438\u0437 \u0444\u0443\u0440\u0438\u0433\u0430\u043d\u044b: %r" % sent)
    check("\u8010\u706b\u6027\u80fd" in sent, "\u043e\u0441\u0442\u0430\u043b\u044c\u043d\u043e\u0435 \u0442\u0435\u043a\u0441\u0442\u0430 \u043a\u0430\u043d\u0434\u0437\u0438: %r" % sent)
    check(word == "\u3056\u3093\u304d\u3087\u3046\u3057\u304d", "\u0441\u043b\u043e\u0432\u043e \u0447\u0442\u0435\u043d\u0438\u0435 \u043f\u043e \u0444\u0443\u0440\u0438\u0433\u0430\u043d\u0435: %r" % word)

    # \u0431\u0435\u0437 \u0444\u0443\u0440\u0438\u0433\u0430\u043d\u044b \u2014 \u0447\u0438\u0441\u0442\u044b\u0439 \u043a\u0430\u043d\u0434\u0437\u0438
    note2 = {"noteId": 2, "fields": {
        "Sentence": {"value": "\u8010\u706b\u6027\u80fd\u3092\u78ba\u8a8d\u3059\u308b\u3002"},
        "Expression": {"value": "\u8010\u706b\u6027\u80fd"},
        "ExpressionFurigana": {"value": ""}}}
    jobs2 = vp.build_jobs([note2], "both", True, fields=fields)
    sent2 = [j for j in jobs2 if j[1] == "SentenceAudio"][0][2]
    word2 = [j for j in jobs2 if j[1] == "ExpressionAudio"][0][2]
    check(sent2 == "\u8010\u706b\u6027\u80fd\u3092\u78ba\u8a8d\u3059\u308b\u3002", "\u0431\u0435\u0437 \u0444\u0443\u0440\u0438\u0433\u0430\u043d\u044b: %r" % sent2)
    check(word2 == "\u8010\u706b\u6027\u80fd", "\u0441\u043b\u043e\u0432\u043e \u0431\u0435\u0437 \u0444\u0443\u0440\u0438\u0433\u0430\u043d\u044b: %r" % word2)


def test_broken_config_not_wiped():
    """Битый конфиг (BOM, обрыв записи) не должен стирать настройки.

    Раньше load_config() молча отдавала пустой словарь, и следующая же
    запись затирала файл — путь движка, голос и колода пропадали.
    """
    tmp = tempfile.mkdtemp(prefix="av_cfg_")
    cf = os.path.join(tmp, "config.json")
    with open(cf, "wb") as f:
        f.write(b"\xef\xbb\xbf" + json.dumps({"voice": "madara"}).encode("utf-8"))
    old = ag.CONFIG_FILE
    try:
        ag.CONFIG_FILE = cf
        cfg = ag.load_config()
        check(cfg == {}, "битый конфиг: настройки не читаются")
        check(os.path.exists(cf + ".broken"), "битый конфиг: файл отложен в сторону")
        # и запись после этого не уничтожает прочие настройки
        keep = ag.load_config()
        keep["voice"] = "narrator"
        ag.save_config(keep)
        back = ag.load_config()
        check(back.get("voice") == "narrator", "после битого конфига настройки пишутся")
    finally:
        ag.CONFIG_FILE = old
        try:
            os.remove(cf)
        except OSError:
            pass


def test_furigana_not_doubled():
    """Окуригана не должна попадать в чтение второй раз.

    «点群データ[てんぐんでーта]» — чтение на всё слово: если добавить
    окуригану «データ» ещё раз, получится «データてんぐんでーта» и модель
    читает «データ» дважды.
    """
    check(vp.furiga_pair("\u70b9\u7fa4\u30c7\u30fc\u30bf[\u3066\u3093\u3050\u3093\u3067\u30fc\u305f]")
          == ("\u70b9\u7fa4\u30c7\u30fc\u30bf", "\u3066\u3093\u3050\u3093\u3067\u30fc\u305f"),
          "\u70b9\u7fa4\u30c7\u30fc\u30bf: \u0447\u0442\u0435\u043d\u0438\u0435 \u043d\u0430 \u0432\u0441\u0435 \u0441\u043b\u043e\u0432\u043e")
    check(vp.furiga_pair("\u30d3\u30e5\u30fc\u5be9\u67fb[\u3073\u30e5\u30fc\u3057\u3093\u3055]")[1]
          == "\u3073\u30e5\u30fc\u3057\u3093\u3055", "\u30d3\u30e5\u30fc\u5be9\u67fb: \u0431\u0435\u0437 \u0443\u0434\u0432\u043e\u0435\u043d\u0438\u044f")
    check(vp.furiga_pair("\u30c7\u30fc\u30bf\u9023\u643a\u306e\u30aa\u30fc\u30c8\u30e1\u30fc\u30b7\u30e7\u30f3\u5316[\u3067\u30fc\u305f\u308c\u3093\u3051\u3044\u306e\u304a\u30fc\u30c8\u30e1\u30fc\u30b7\u30e7\u30f3\u304b]")[1]
          == "\u3067\u30fc\u305f\u308c\u3093\u3051\u3044\u306e\u304a\u30fc\u30c8\u30e1\u30fc\u30b7\u30e7\u30f3\u304b",
          "\u30c7\u30fc\u30bf\u9023\u643a\u306e\u30aa\u30fc\u30c8\u30e1\u30fc\u30b7\u30e7\u30f3\u5316: \u0431\u0435\u0437 \u0443\u0434\u0432\u043e\u0435\u043d\u0438\u044f")
    # многочастная разметка: окуригана и «・» по-прежнему обрабатываются
    check(vp.furiga_pair("\u9060\u96a3[\u3048\u3093\u304b\u304f]\u76e3\u7763[\u304b\u3093\u3068\u304f]\u30fb\u691c\u67fb[\u3051\u3093\u3055]")
          == ("\u9060\u96a3\u76e3\u7763\u30fb\u691c\u67fb", "\u3048\u3093\u304b\u304f\u304b\u3093\u3068\u304f\u3051\u3093\u3055"),
          "\u9060\u96a3\u76e3\u7763\u30fb\u691c\u67fb: \u0447\u0430\u0441\u0442\u0438\u0447\u043d\u0430\u044f \u0440\u0430\u0437\u043c\u0435\u0442\u043a\u0430")

    # и в синтез уходит текст без удвоения
    fields = {"sentence_src": "Sentence", "sentence_audio": "SentenceAudio",
              "word_src": "Expression", "word_audio": "ExpressionAudio",
              "furigana_src": "ExpressionFurigana", "reading": "mix"}
    note = {"noteId": 1, "fields": {
        "Sentence": {"value": "\u73fe\u5834\u78ba\u8a8d\u3067\u306f\u3001\u5efa\u7269\u73fe\u6cc1\u306e\u8a18\u9332\u306b\u3001\u70b9\u7fa4\u30c7\u30fc\u30bf\u3092\u7528\u3044\u305f\u3002"},
        "Expression": {"value": "\u70b9\u7fa4\u30c7\u30fc\u30bf"},
        "ExpressionFurigana": {"value": "\u70b9\u7fa4\u30c7\u30fc\u30bf[\u3066\u3093\u3050\u3093\u3067\u30fc\u305f]"}}}
    jobs = vp.build_jobs([note], "sentence", True, fields=fields)
    check(jobs and jobs[0][2] == "\u73fe\u5834\u78ba\u8a8d\u3067\u306f\u3001\u5efa\u7269\u73fe\u6cc1\u306e\u8a18\u9332\u306b\u3001\u3066\u3093\u3050\u3093\u3067\u30fc\u305f\u3092\u7528\u3044\u305f\u3002",
          "\u0442\u0435\u043a\u0441\u0442 \u0431\u0435\u0437 \u0443\u0434\u0432\u043e\u0435\u043d\u0438\u044f")


def test_latin_term_kept_as_is():
    """Термины с латиницей или цифрами оставляем как есть.

    Замер на карточках «3D\u90fd\u5e02\u30e2\u30c7\u30eb» и «PLATEAU»:
    своя транслитерация («\u3059\u308a\u30fc\u3067\u3044\u30fc») читается хуже
    (покрытие 0.89) и вводит модель в цикл (96 \u0441 \u0432\u043c\u0435\u0441\u0442\u043e
    \u0432\u043c\u0435\u0441\u0442\u043e \u043f\u0440\u043e\u0442\u0438\u0432 \u0447\u0442\u043e \u0431\u044b\u0441\u0442\u043e\u0433\u043e \u0441\u0443\u043c\u043a\u0430).
    """
    fields = {"sentence_src": "Sentence", "sentence_audio": "SentenceAudio",
              "word_src": "Expression", "word_audio": "ExpressionAudio",
              "furigana_src": "ExpressionFurigana", "reading": "mix"}
    note = {"noteId": 1, "fields": {
        "Sentence": {"value": "\u90fd\u5e02\u306e\u666f\u89b3\u691c\u8a0e\u306b\u30013D\u90fd\u5e02\u30e2\u30c7\u30eb\u3092\u7528\u3044\u305f\u3002"},
        "Expression": {"value": "3D\u90fd\u5e02\u30e2\u30c7\u30eb"},
        "ExpressionFurigana": {"value": "3D\u90fd\u5e02\u30e2\u30c7\u30eb[\u3059\u308a\u30fc\u3067\u3044\u30fc\u3068\u3057\u3082\u3067\u308b]"}}}
    check(vp.term_has_latin(note, fields) is True, "3D: \u0435\u0441\u0442\u044c \u043b\u0430\u0442\u0438\u043d\u0438\u0446\u0430")
    jobs = vp.build_jobs([note], "sentence", True, fields=fields)
    check(jobs and jobs[0][2] == "\u90fd\u5e02\u306e\u666f\u89b3\u691c\u8a0e\u306b\u30013D\u90fd\u5e02\u30e2\u30c7\u30eb\u3092\u7528\u3044\u305f\u3002",
          "3D: \u0442\u0435\u043a\u0441\u0442 \u0431\u0435\u0437 \u043f\u043e\u0434\u0441\u0442\u0430\u043d\u043e\u0432\u043a\u0438")
    # обычный термин с фуриганой остаётся с подстановкой
    note2 = {"noteId": 2, "fields": {
        "Sentence": {"value": "\u65b0\u305f\u306a\u5be9\u67fb\u65b9\u6cd5\u3068\u3057\u3066\u3001\u30d3\u30e5\u30fc\u5be9\u67fb\u3092\u78ba\u8a8d\u3057\u305f\u3002"},
        "Expression": {"value": "\u30d3\u30e5\u30fc\u5be9\u67fb"},
        "ExpressionFurigana": {"value": "\u30d3\u30e5\u30fc\u5be9\u67fb[\u3073\u30e5\u30fc\u3057\u3093\u3055]"}}}
    check(vp.term_has_latin(note2, fields) is False, "\u30d3\u30e5\u30fc\u5be9\u67fb: \u043b\u0430\u0442\u0438\u043d\u0438\u0446\u044b \u043d\u0435\u0442")
    jobs2 = vp.build_jobs([note2], "sentence", True, fields=fields)
    check(jobs2 and jobs2[0][2].endswith("\u3057\u3093\u3055\u3092\u78ba\u8a8d\u3057\u305f\u3002"),
          "\u30d3\u30e5\u30fc\u5be9\u67fb: \u0447\u0442\u0435\u043d\u0438\u0435 \u043f\u043e \u0444\u0443\u0440\u0438\u0433\u0430\u043d\u0435")


# реальные форматы фуриганы из колод: (поле, где взяли)
REAL_FURIGANA = [
    # колода «Новое в цифровом строительстве» — чтение на всё слово
    ("点群データ[てんぐんでーた]", "новое строительство"),
    ("ビュー審査[びゅーしんさ]", "новое строительство"),
    ("デジタル審査[でじたるしんさ]", "новое строительство"),
    ("施工のオートメーション化[せこうのおーとめーしょんか]", "новое строительство"),
    ("データ連携のオートメーション化[でーたれんけいのおーとめーしょんか]",
     "новое строительство"),
    ("3D都市モデル[すりーでぃーとしもでる]", "новое строительство"),
    ("PLATEAU[ぷらとー]", "новое строительство"),
    ("i-Construction 2.0[あいこんすとらくしょんにてんぜろ]", "новое строительство"),
    # колода «Архитектура» — чтение только на иероглифы
    ("アイススケート場[じょう]", "архитектура"),
    ("アーク溶接棒[ようせつぼう]", "архитектура"),
    ("アイソメ画法[がほう]", "архитектура"),
    ("腮欠き[あごかき]", "архитектура"),
    ("蟻掛け[ありがけ]", "архитектура"),
    ("安全ガラス[あんぜんガラス]", "архитектура"),
    ("アイリング・ヌートセンの残響式[アイリングヌートセンのざんきょうしき]",
     "архитектура"),
    ("IEC規格[アイイーシーきかく]", "архитектура"),
    ("IIW[アイアイダブリュー]", "архитектура"),
    ("遠隔[えんかく]監督[かんとく]・検査[けんさ]", "архитектура"),
    ("き継[つ]ぎ", "архитектура"),
    ("食品[しょくひん]を使う", "архитектура"),
    ("生花[いけばな]", "архитектура"),
    ("食[た]べる", "архитектура"),
]


def test_real_furigana_never_doubled():
    """Ни один реальный формат не должен удваивать окуригану.

    Проверяем и разбор, и страховку: даже если разбор ошибся, удвоение
    не дойдёт до синтеза — термин останется как есть.
    """
    for text, where in REAL_FURIGANA:
        surf, read = vp.furiga_pair(text)
        check(surf is not None, "%s: разметка разобрана (%s)" % (where, text))
        # 1. в разборе окуригана не должна звучать дважды
        check(not vp._doubled_okurigana(surf or "", read or ""),
              "%s: разбор без удвоения (%s -> %r)" % (where, text, read))
        # 2. и страховка на готовом тексте
        note = {"noteId": 1, "fields": {
            "Sentence": {"value": "現場では、%sを用いた。" % surf},
            "Expression": {"value": surf},
            "ExpressionFurigana": {"value": text}}}
        fields = {"sentence_src": "Sentence", "sentence_audio": "SentenceAudio",
                  "word_src": "Expression", "word_audio": "ExpressionAudio",
                  "furigana_src": "ExpressionFurigana", "reading": "mix"}
        jobs = vp.build_jobs([note], "sentence", True, fields=fields)
        check(bool(jobs), "%s: есть работа (%s)" % (where, text))
        out = jobs[0][2]
        # термин в тексте на синтез встречается ровно один раз: либо как есть
        # (страховка сработала), либо в виде своего чтения
        read_h = vp.kata2hira(read or "")   # в текст подставляется кана
        as_is = out.count(surf or "") == 1
        as_read = out.count(surf or "") == 0 and out.count(read_h) == 1
        check(as_is or as_read,
              "%s: термин в тексте на синтез без удвоения (%s)" % (where, text))


def test_engine_choice():
    """Движок выбирается переключателем в интерфейсе (в конфиге)."""
    check(ag.engine_kind({}) == "gpt-sovits", "по умолчанию GPT-SoVITS")
    check(ag.engine_kind({"engine": "gpt-sovits"}) == "gpt-sovits", "явно GPT-SoVITS")
    check(ag.engine_kind({"engine": "indextts"}) == "indextts", "явно IndexTTS")
    check(ag.engine_kind({"engine": "IndexTTS2.5"}) == "indextts", "IndexTTS 2.5")
    check(vp.engine_kind({"engine": "indextts"}) == "indextts", "пайплайн видит выбор")
    check(vp.indextts_url({}) == "http://127.0.0.1:9881", "адрес сервиса по умолчанию")
    check(vp.indextts_url({"indextts_url": "http://127.0.0.1:9999/"})
          == "http://127.0.0.1:9999", "адрес сервиса из конфига")


def test_indextts_folder_check():
    """Папка IndexTTS: нужны веса (checkpoints) и окружение (.venv)."""
    import tempfile
    tmp = tempfile.mkdtemp(prefix="av_idx_")
    check(ag.validate_indextts("") != [], "пустая папка — есть замечания")
    check(ag.validate_indextts(os.path.join(tmp, "нет")) != [], "нет папки — замечания")
    os.makedirs(os.path.join(tmp, "checkpoints"), exist_ok=True)
    for rel in (os.path.join("checkpoints", "config.yaml"),
                 os.path.join("checkpoints", "gpt.pth")):
        with open(os.path.join(tmp, rel), "wb") as f:
            f.write(b"x")
    problems = ag.validate_indextts(tmp)
    check(any(".venv" in p for p in problems),
          "без .venv — замечание про окружение")
    os.makedirs(os.path.join(tmp, ".venv", "Scripts"), exist_ok=True)
    with open(os.path.join(tmp, ".venv", "Scripts", "python.exe"), "wb") as f:
        f.write(b"x")
    check(ag.validate_indextts(tmp) == [], "полная папка — замечаний нет")


def test_indextts_synth_needs_ref():
    """Без референса IndexTTS должен сказать об этом, а не молчать."""
    old = vp.engine_kind
    vp.engine_kind = lambda cfg=None: "indextts"
    try:
        try:
            vp._synth_once_indextts({"name": "v", "ref": ""}, "テスト")
            raise AssertionError("ожидалась ошибка из-за пустого референса")
        except SystemExit as e:
            check("референс" in str(e), "внятная ошибка про референс")
    finally:
        vp.engine_kind = old


def test_setup_status():
    eng = tempfile.mkdtemp(prefix="anki_voice_engine_")
    for name in ("g.ckpt", "s.pth", "r.wav"):
        with open(os.path.join(eng, name), "wb") as f:
            f.write(b"x")
    cfg = {"gptsovits_path": eng, "last_test_voice": "alice",
           "setup_done": True}
    voices = {"alice": {"display": "Alice", "gpt": "g.ckpt",
                        "sovits": "s.pth", "ref": "r.wav"}}
    old = (ag.load_config, ag.validate_gptsovits, ag.anki_status, ag.tts_status,
           aw.read_voices_file, aw._test_audio)
    ag.load_config = lambda: dict(cfg)
    ag.validate_gptsovits = lambda path: []
    ag.anki_status = lambda: True
    ag.tts_status = lambda: False
    aw.read_voices_file = lambda: {"default_voice": "alice", "voices": voices}
    aw._test_audio = lambda voice: "C:\\tmp\\test_alice.ogg" if voice == "alice" else ""
    try:
        st = aw.setup_status()
        check(st["engine"]["ok"] is True, "engine ok")
        check(st["anki"]["ok"] is True, "anki ok")
        check(st["voices"]["ok"] is True, "voices ok")
        check(st["test"]["ok"] is True, "test ok")
        check(st["complete"] is True, "complete")
        check(st["test"]["voice"] == "alice", "test voice")

        # сброс флага (например, после смены папки движка) не должен
        # подтверждаться старым test_alice.ogg
        cfg["setup_done"] = False
        reset = aw.setup_status()
        check(reset["done"] is False, "reset done")
        check(reset["complete"] is False, "reset complete")
        check(reset["test"]["ok"] is True, "old test still shown")
        cfg["setup_done"] = True

        cfg["gptsovits_path"] = "C:\\nope"
        ag.validate_gptsovits = lambda path: ["Папка не существует: " + path]
        aw._test_audio = lambda voice: ""
        bad = aw.setup_status()
        check(bad["engine"]["ok"] is False, "bad engine")
        check(bad["complete"] is False, "bad complete")
        check("Папка не существует" in bad["engine"]["problems"][0], "bad problem")
    finally:
        (ag.load_config, ag.validate_gptsovits, ag.anki_status, ag.tts_status,
         aw.read_voices_file, aw._test_audio) = old


def main():
    tests = [test_version_tuple, test_release_parse, test_download_sha,
             test_busy_download_no_deadlock, test_installer_ships_runtime_modules,
             test_pronunciation_compare, test_split_method_is_japanese_safe,
             test_pending_notes_limit, test_voice_args_guess_fallback,
             test_baseline_relative_limits, test_profile_fields_per_deck,
             test_check_targets_spoken_text, test_reading_mode_auto,
             test_broken_config_not_wiped, test_furigana_not_doubled,
             test_latin_term_kept_as_is, test_real_furigana_never_doubled,
             test_engine_choice, test_indextts_folder_check,
             test_indextts_synth_needs_ref,
             test_setup_status]
    failed = 0
    for t in tests:
        try:
            t()
            print("OK  ", t.__name__)
        except Exception:
            failed += 1
            print("FAIL", t.__name__)
            traceback.print_exc()
    print("\nv1.4 features: %d/%d" % (len(tests) - failed, len(tests)))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
