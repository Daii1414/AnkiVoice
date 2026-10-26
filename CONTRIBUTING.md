# Как contributing в AnkiVoice

[English](CONTRIBUTING.en.md)

Спасибо, что хочешь помочь. Ниже — короткие правила, чтобы правка не
превратилась в вечер отладки.

## Быстрый старт

```bash
git clone https://github.com/Daii1414/AnkiVoice.git
cd AnkiVoice
```

Пересборка нужна только после правок `app/anki_gui.py`, `app/anki_web.py` или
`app/anki_web_page.py` — `voice_pipeline.py` запускается с диска и применяется
сразу.

## Что нужно знать об архитектуре

| Слой | Файлы | Правило |
|---|---|---|
| Ядро | `voice_pipeline.py` | Вся логика синтеза, чтения и записи в Anki. Запускается с диска — изменения действуют сразу, exe пересобирать не нужно. |
| Интерфейс | `anki_gui.py`, `anki_web.py`, `anki_web_page.py` | Вшиты в exe. После правок нужна пересборка exe и установщика. |
| Качество звука и произношения | `lab/quality_v2.py`, `lab/pron_check.py`, `lab/align_ja.py`, `lab/indextts_*.py` | Шесть файлов из `lab/` едут в установщик — не ломай их импорты. |

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

**тесты** (Python 3.12+, без GPU и без сети):

```bash
python -m pip install numpy haqumei
python lab/qc_unit.py
python lab/quality_unit.py
python lab/test_g2p_infrastructure.py
python lab/test_v12_features.py
python lab/web_js_check.py
python lab/integration_check.py
python lab/readme_check.py
python lab/fmt_check.py
```

`lab/readme_check.py` сверяет README с кодом: файлы из таблицы структуры,
картинки, якоря оглавления, команды консоли, число режимов чтения и модулей
в установщике. Расходится — падает.

`lab/fmt_check.py` проверяет, что в каждой формат-строке столько плейсхолдеров, сколько аргументов - такая ошибка падает из записа
на конце работы, а не в конце длинной войны.

`lab/robust_tests.py` — 10 проверок устойчивости пайплайна, требует
запущенного Anki. CI гоняет всё остальное на каждом пуше
([checks.yml](.github/workflows/checks.yml)) и собирает установщик на
windows-latest.

## Сборка

**exe** (нужен Python из движка GPT-SoVITS с PyInstaller):

```bat
set ENGINE=C:\Путь\К\GPT-SoVITS
%ENGINE%\runtime\python.exe -m pip install pyinstaller
%ENGINE%\runtime\python.exe -m PyInstaller --noconfirm --onefile --windowed ^
    --name AnkiVoice --distpath . --workpath %TEMP%\pyi_build --specpath %TEMP% app\anki_gui.py
```

**установщик** (Inno Setup 6, запускать из корня репозитория):

```bat
ISCC.exe AnkiVoice.iss
```

→ получится `dist\AnkiVoice-Setup-x.y.exe`.


## Структура репозитория

| Файл | Что это |
|---|---|
| `AnkiVoice.exe` | Программа с интерфейсом (двойной клик) |
| `AnkiVoice.iss` | Скрипт сборки установщика (Inno Setup 6) |
| `app/voice_pipeline.py` | Вся логика: синтез, чтение иероглифов, подстановка, CLI |
| `app/anki_gui.py` | Точка входа exe: веб-интерфейс по умолчанию, `--classic` — старое окно |
| `app/anki_web.py` | Локальный HTTP-сервер интерфейса (только 127.0.0.1) |
| `app/anki_web_page.py` | HTML/CSS/JS страницы (офлайн, без CDN) |
| `pipeline.bat` | Консольная точка входа |
| `app/sudachi_g2p.py` | Запасной помощник-«читатель»: SudachiPy 0.7 + словарь UniDic |
| `app/g2p_core.py` | Ядро чтения Haqumei: слово в контексте предложения, форма pron |
| `app/kana_stress.py` | Батарея из 63 сложных слов для проверки чтения |
| `app/i18n_en.py` | Словарь английского интерфейса (RU/EN) |
| `lab/pron_check.py` | Проверка произношения: распознавание, покрытие, карантин, локализация расхождения |
| `lab/align_ja.py` | Экспериментальное акустическое выравнивание по японской CTC-модели (выключается переменной) |
| `bundled/pyruntime.zip` | Встроенный Python + Haqumei 0.12.2 + SudachiPy 0.7 (~44 МБ, разворачивается сам) |
| `bundled/sudachidict.zip` | Словарь Sudachi core 20261015 (~73 МБ, распаковывает помощник) |
| `app/voices.json` | Реестр голосов: веса, референсы, промпт, sampling |
| `lab/` | QC v2, проверка произношения и сервис IndexTTS (6 модулей едут в установщик) + тесты и dev-инструменты |
| `doc/` | Скриншоты интерфейса, логотип, медиа движка, отчёты по замерам |
| `CHANGELOG.md`, `CONTRIBUTING.md`, `SECURITY.md` | История, правила разработки, политика безопасности |
| `.github/` | CI, шаблоны issue и pull request |
| `LICENSE` | AGPL-3.0 |

В git не попадают: `gptsovits_path.txt`, `pyruntime/` (разворачивается из zip),
`test_*.ogg`, `logs/`, `dist/`.

## Переводы интерфейса

Ключ перевода — русский текст разметки; английский словарь — `app/i18n_en.py`,
остальные 22 языка — модули `app/locales/*.py`, их **не правят руками**:

1. новая строка интерфейса — добавь её английский перевод в `app/i18n_en.py`;
2. переводы на другие языки — в `lab/i18n_src/late.json`
   (`{"русский текст": {"zh-CN": "…", "ja": "…", …}}`); основная выгрузка
   строк для переводчиков — `lab/i18n_src/source.json` и `<код>.json`;
3. собери модули и тексты установщика Windows:
   `python lab/build_locales.py build lab/i18n_src`;
4. проверь: `python lab/i18n_check.py` (полнота всех языков).

Числа и данные в строках — отдельными узлами (`replaceChildren("Голосов:",
" " + n)`), иначе фраза не найдётся в словаре.

## Linux-установщик

`install.sh` проверяется без установки: `./install.sh --check` и
`./install.sh --dry-run --yes`; в контейнерах дистрибутивов — тем же
`--dry-run` от обычного пользователя.

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
