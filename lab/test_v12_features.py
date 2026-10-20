# -*- coding: utf-8 -*-
"""Тесты v1.2: версия, парсинг релиза, SHA256 и логика мастера.

Ничего не требует от машины: сеть и GPT-SoVITS подменяются заглушками.
"""
import hashlib
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
    check(ag.version_tuple("v1.2.1") == (1, 2, 1), "v1.2.1")
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
    print("\nv1.2 features: %d/%d" % (len(tests) - failed, len(tests)))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
