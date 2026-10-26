# Карта кода AnkiVoice (для людей и агентов)

Точка входа пользователя — `anki_gui.py` (exe-оболочка) → локальный веб-
интерфейс (`anki_web.py` + `anki_web_page.py`). Вся озвучка — в пайплайне.

## Пайплайн (озвучка)

| Модуль | Ответственность | Ключевые входы |
|---|---|---|
| `voice_pipeline.py` | фасад + CLI (`pipeline.bat voice ...`), cmd_*, selftest, menu | всё ниже через реэкспорт |
| `paths.py` | CODE/ROOT/lab_dir/bundled — где код, где словари | — |
| `av_state.py` | общее состояние движка (ENGINE/PYTHON/...), заполняется `engines.apply_engine()` | — |
| `oscompat.py` | всё, что зависит от ОС (Windows/Linux): папка настроек, Python движка, ffmpeg, PID на порту, блокировка, открытие файлов, автопоиск | — |
| `fields_config.py` | имена полей карточки по умолчанию, профили | — |
| `anki_api.py` | AnkiConnect: `ac()`, `notes_info()`, `plain()` | — |
| `engines.py` | выбор GPT-SoVITS/IndexTTS, поиск папки, сервер, веса, indextts-сервис | `voices` (лениво) |
| `voices.py` | реестр голосов (voices.json), пути весов/референсов | `engines` |
| `kana_reading.py` | чтение иероглифов: `kanaize()`, Haqumei-помощник (`g2p_core.py`), Sudachi/pyopenjtalk запас, разбор фуриганы, `inject_reading*`, `replace_term` | `anki_api`, `paths`, `av_state` |
| `tts.py` | `synth()` со спасением брака, QC v2, проверка произношения, базы порогов | `engines`, `voices`, `kana_reading` |
| `jobs.py` | `build_jobs()`: режим чтения карточки, подстановка фуриганы, plural | `kana_reading`, `tts`, `anki_api` |
| `voicing.py` | `voice_notes()`: ансамбль, теги av_voiced/av_voice, манифест, отчёты | всё выше |
| `g2p_core.py` | помощник Haqumei (отдельный процесс, JSON-протокол) | — |
| `sudachi_g2p.py` | помощник SudachiPy (запасной ход) | — |
| `en_translit.py` | e2k: английские слова → катакана | — |

## Правила для агентов

- Внешние потребители импортируют только `voice_pipeline` (фасад): все имена
  доступны как `from voice_pipeline import kanaize` и т.д.
- Изменяемое состояние движка — только через `av_state` (никаких копий).
- Кэш/манифесты/итоги пишутся в `oscompat.app_dir()`: `%APPDATA%/AnkiVoice/`
  на Windows, `~/.config/AnkiVoice/` на Linux. Проверки `os.name`, пути
  `python.exe`, `msvcrt`/`taskkill`/`os.startfile` — только в `oscompat.py`.
- После любого рефакторинга: `ruff check app lab linux --select E9,F63,F7,F82,F401`,
  `python lab/test_v12_features.py`, `python lab/test_oscompat.py`, `python app/kana_stress.py`, golden-набор.
