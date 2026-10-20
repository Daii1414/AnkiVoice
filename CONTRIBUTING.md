# Как contributing в AnkiVoice

[English](CONTRIBUTING.en.md)

Спасибо, что хочешь помочь. Ниже — короткие правила, чтобы правка не
превратилась в вечер отладки.

## Быстрый старт

```bash
git clone https://github.com/Daii1414/AnkiVoice.git
cd AnkiVoice
git checkout -b feature/short-description
```

Правь, проверяй, открывай pull request в `main`.

## Что нужно знать об архитектуре

| Слой | Файлы | Правило |
|---|---|---|
| Ядро | `voice_pipeline.py` | Вся логика синтеза, чтения и записи в Anki. Запускается с диска — изменения действуют сразу, exe пересобирать не нужно. |
| Интерфейс | `anki_gui.py`, `anki_web.py`, `anki_web_page.py` | Вшиты в exe. После правок нужен пересборка exe и установщика. |
| Система чтения | `lab/g2p_*.py`, `lab/domain_dict.py` | Модули чтения. Пять файлов из `lab/` едут в установщик — не ломай их импорты. |
| Качество | `lab/quality_v2.py` | Многосигнальная проверка звука. Тоже едет в установщик. |

Полное техническое описание — в [PROJECT.md](PROJECT.md).

## Правила кода

* Python 3.9+ (движок) и 3.12+ (CI). Только стандартная библиотека в
  `voice_pipeline.py`, `anki_web.py`, `anki_web_page.py` — внешних зависимостей
  в приложении нет.
* Комментарии и сообщения об ошибках — по-русски, без сленга.
* Никаких сетевых запросов, кроме проверки обновлений (GitHub API) и
  обращений к локальному AnkiConnect.
* Не трогай `pyruntime.zip` и `sudachidict.zip` — они собираются отдельно и
  едут в установщик как есть.
* Пути к файлам собираются через `code_dir()` / `resolve_path()`, а не
  жёстко: приложение работает и из `E:\`, и из `%LOCALAPPDATA%\Programs`.

## Проверки перед pull request

```bash
python -m pip install numpy haqumei
python lab/qc_unit.py
python lab/quality_unit.py
python lab/test_g2p_infrastructure.py
python lab/test_v12_features.py
python lab/web_js_check.py
python lab/integration_check.py
```

Все шесть должны закончиться с кодом 0. `lab/robust_tests.py` (10 проверок
устойчивости) требует запущенного Anki — его стоит прогнать, если правки
касаются пайплайна.

Если менялся интерфейс — приложи скриншот вкладки в описание PR.

## Сборка

```bat
set ENGINE=C:\Путь\К\GPT-SoVITS
%ENGINE%\runtime\python.exe -m pip install pyinstaller
%ENGINE%\runtime\python.exe -m PyInstaller --noconfirm --onefile --windowed ^
    --name AnkiVoice --distpath . --workpath %TEMP%\pyi_build --specpath %TEMP% anki_gui.py
ISCC.exe AnkiVoice.iss
```

Установщик собирается из корня репозитория и кладётся в `dist/`.

## Оформление коммитов

```
<тип>(<область>): <что сделано в императиве>

Зачем это нужно — в теле коммита, строками по 72 символа.
```

Типы: `feat`, `fix`, `refactor`, `perf`, `test`, `docs`, `build`, `ci`,
`chore`. Пример: `fix(reading): не ронять импорт модулей без haqumei`.

## Чего не просим

* Тяжёлые модели, фреймворки и новые зависимости в приложении.
* Автоматические коммиты с копирайтом из чужих репозиториев.
* Изменения, ломающие формат `voices.json` без миграции.

## Куда задавать вопросы

* Баги и идеи — <https://github.com/Daii1414/AnkiVoice/issues>.
* Вопросы по безопасности — по инструкции из [SECURITY.md](SECURITY.md).
