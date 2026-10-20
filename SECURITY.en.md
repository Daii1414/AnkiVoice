# Security policy

[Русский](SECURITY.md)

## Supported versions

| Version | Support |
|---|---|
| 1.2.x | ✅ current |
| 1.1.x | ⚠️ security fixes only |
| < 1.1 | ❌ |

## How to report a vulnerability

Do not open a public issue. Use
<https://github.com/Daii1414/AnkiVoice/security/advisories/new>
(**Security** → **Report a vulnerability**) or send a private message to the
repository owner.

Please describe:

* what is wrong and how to reproduce it;
* the installer version and the GPT-SoVITS version;
* the impact: local only, does it need administrator rights, does it affect
  other decks or files.

Expect an answer within 7 days. The fix ships in the next release, and the
issue will link to it. If the vulnerability is dangerous and the fix takes
longer, we will ask you to keep the details private and will publish a build
as a private release.

## What the app already does

* It listens on **127.0.0.1 only** — it is not reachable from outside.
* No telemetry, no accounts, no cloud services.
* The only outbound request is the update check against `api.github.com`; the
  response is used locally and never sent anywhere.
* The installer does not ask for administrator rights and installs into the
  user profile.
* The installer's SHA256 is checked after the download and once more right
  before it is started.

## What we do not do

* We do not collect or send your cards, voices or logs.
* We do not write anything into `%APPDATA%` except `config.json` and `logs/`.
* We do not run code fetched from the internet: only the installer published
  in a release is downloaded, and its hash is verified.

## Caveat

AnkiVoice runs GPT-SoVITS locally and writes into your Anki collection. The
security of the engine itself and of Anki is the responsibility of their
maintainers: <https://github.com/RVC-Boss/GPT-SoVITS> and
<https://github.com/ankitects/anki>.
