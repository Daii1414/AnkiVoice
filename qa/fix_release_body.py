# -*- coding: utf-8 -*-
"""Переписать тело релиза v1.6 без кракозябр (через Python, не PowerShell)."""
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
     "X-GitHub-Api-Version": "2022-11-28"}


def api(method, url, payload=None):
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, headers=dict(H), method=method)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


rel = api("GET", "https://api.github.com/repos/Daii1414/AnkiVoice/releases/tags/v1.6")
size = 131394904
sha = "385481551c6404ec8927a37d6c234630c87ee71660aa5c689eab9654da0dbc28"

body = """## AnkiVoice v1.6

Installer: **AnkiVoice-Setup-1.6.exe**

- size: %d bytes
- sha256: %s

### Fixed after three new users walked through the interface

An impatient user, a skeptic and a stress tester each went from the main screen
to a first finished card. Twenty-three problems were found; the report and the
screenshots are in the repository (`qa/REPORT.md`). The dangerous ones:

- **The card limit could voice the whole deck.** "0", "-5" or "abc" silently
  became "no limit", so one click started all 18 375 cards of the big deck. The
  limit is now a whole number (20 by default) and an empty field asks for a
  confirmation with the card count.
- **"Rebuild everything" did not work together with a limit** - the app answered
  "everything is already voiced" while the banner suggested exactly that.
- **With IndexTTS the app started GPT-SoVITS** and hung for ten minutes
  talking about the wrong engine. It also tried to "switch voice weights",
  a thing IndexTTS does not have.
- **The default voice did not work with IndexTTS** - its reference was a
  relative path and IndexTTS looked for it only in its own folder. The
  ready-voices counter is now counted for the selected engine.
- **Two buttons did nothing at all** - "Build the «Брак» deck" and "Verdict
  summary" were not known to the web layer.
- **A junk engine folder corrupted the config**, and "Check" wrote to it too.

### Also

- Feedback while dubbing: a stage line in the log, and the progress shows how
  much has passed and how much is left roughly.
- Honest labels: everything runs on this computer and your cards are never sent
  anywhere; the audio goes straight into the Anki fields and an existing sound is
  overwritten; which buttons go online.
- The wizard's test player plays, the wizard shows the voice name, the card
  counter follows the selected deck, the diagnostics name the selected engine and
  show the Anki media folder.
- The layout fits a narrow window: the sidebar becomes a strip, the cards stack.

Everything is local and offline.
""" % (size, sha)

api("PATCH", "https://api.github.com/repos/Daii1414/AnkiVoice/releases/%s" % rel["id"],
    {"tag_name": "v1.6", "target_commitish": "main", "name": "AnkiVoice v1.6",
     "body": body, "draft": False, "prerelease": False})
check = api("GET", "https://api.github.com/repos/Daii1414/AnkiVoice/releases/tags/v1.6")
b = check["body"]
print("«Брак» на месте:", "Брак" in b)
print("«sha256:» с хэшем:", sha in b)
print("мусорных символов:", sum(1 for ch in b if 0xC0 <= ord(ch) <= 0xFF and ch not in "é"))
