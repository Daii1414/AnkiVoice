# -*- coding: utf-8 -*-
"""Обновить описание репозитория и темы (по разбору страницы новым посетителем)."""
import json
import os
import subprocess
import urllib.request

ROOT = os.environ["AV_ROOT"]


def token():
    p = subprocess.run(["git", "credential", "fill"],
                       input=b"protocol=https\nhost=github.com\n\n", capture_output=True)
    for line in p.stdout.decode("utf-8", "replace").split("\n"):
        if line.startswith("password="):
            return line[9:].strip()
    return ""


H = {"Authorization": "token " + token(), "Accept": "application/vnd.github+json",
     "X-GitHub-Api-Version": "2022-11-28",
     "Content-Type": "application/json"}


def api(method, url, payload=None):
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, headers=H, method=method)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


repo = api("GET", "https://api.github.com/repos/Daii1414/AnkiVoice")
print("было:", repo["description"])
print("темы:", ", ".join(repo.get("topics") or []))

desc = ("Local Japanese voice for Anki decks (Windows, free, offline): reads kanji in "
        "context, takes the word's reading from the card's furigana, and checks the "
        "result. Works with GPT-SoVITS or IndexTTS 2.5.")
topics = sorted(set((repo.get("topics") or []) + ["indextts", "tts", "japanese", "anki"]))

api("PATCH", "https://api.github.com/repos/Daii1414/AnkiVoice",
    {"description": desc, "topics": topics})
check = api("GET", "https://api.github.com/repos/Daii1414/AnkiVoice")
print("стало:", check["description"])
print("темы:", ", ".join(check.get("topics") or []))
