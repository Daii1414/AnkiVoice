# -*- coding: utf-8 -*-
"""AnkiConnect: единственная точка общения с Anki.

ac() — вызов действия, notes_info() — информация по заметкам чанками,
plain() — чистка HTML-поля карточки до текста. Этим пользуется весь
пайплайн; сами запросы идут мимо системного прокси.
"""
import html
import json
import re
import time
import urllib.error
import urllib.request

ANKI_CONNECT = "http://127.0.0.1:8765"

# ------------------------------------------------------------ AnkiConnect
# Все локальные запросы (AnkiConnect и GPT-SoVITS) идут МИМО системного
# прокси: 127.0.0.1 — это localhost, а прокси-обвязка (корпоративный VPN,
# PAC-скрипт, настройки «Интернет-свойства») только ломает такие запросы.
_NO_PROXY = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def ac(action, **params):
    payload = {"action": action, "version": 6, "params": params}
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    for attempt in (1, 2):
        req = urllib.request.Request(
            ANKI_CONNECT, data=data,
            headers={"Content-Type": "application/json", "Origin": "http://localhost"},
        )
        try:
            with _NO_PROXY.open(req, timeout=120) as resp:
                out = json.loads(resp.read().decode("utf-8"))
            break
        except urllib.error.URLError as e:
            if attempt == 1:
                time.sleep(1.0)      # Anki мог перезаписывать коллекцию — повтор разок
                continue
            raise SystemExit("AnkiConnect недоступен (%s). Открой Anki и повтори." % e)
    if out.get("error"):
        raise SystemExit("AnkiConnect: %s" % out["error"])
    return out["result"]


def notes_info(ids, chunk=400):
    """notesInfo по частям: AnkiConnect на десятках тысяч id отвечает
    одним огромным JSON — режем на куски, стабильно и быстрее."""
    out = []
    for i in range(0, len(ids), chunk):
        out.extend(ac("notesInfo", notes=ids[i:i + chunk]))
    return out


TAG_RE = re.compile(r"<[^>]+>")
SOUND_TAG_RE = re.compile(r"\[(?:sound|audio):[^\]]*\]", re.IGNORECASE)


def plain(v, strip_media=False):
    """Поле карточки -> чистый текст.

    strip_media=True — для ТЕКСТОВ, которые уходят на синтез: [sound:...]
    вырезается, иначе API прочитает «звук двоеточие...» вслух. Для проверки
    «озвучено ли поле» (check_deck, build_jobs) strip_media=False — тег должен
    остаться видимым."""
    s = TAG_RE.sub("", v or "")
    if strip_media:
        s = SOUND_TAG_RE.sub(" ", s)
    s = html.unescape(s).replace("\xa0", " ")
    return s.strip()


def _chunks(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]
