# Консоль

`pipeline.bat` — то же самое в консоли, сам находит папку движка.

## Озвучка

```
pipeline.bat voice --voice madara --deck "Архитектура" --mode both
```

* `--mode both|sentence|expression` — слово + предложение / только
  предложение / только слово;
* `--limit N` — сколько карточек (без лимита — вся колода);
* `--force` — «Пересобрать всё заново» (перезапись звука);
* `--new` — только карточки **без** тега `av_voiced`: добавил карточки —
  одна команда;
* `--changed` — «Пересобрать **только изменённые**»: текст и голос
  совпадают с прошлой озвучкой — карточка пропускается (сверка по
  `voiced_manifest.json`); взаимоисключается с `--force`;
* `--retry` — перезапустить **неудавшиеся** операции прошлого прогона
  (из `last_run.json`); уже озвученные поля пропускаются;
* `--voices "sakura,madara"` — **ансамбль**: карточки случайно
  распределяются между голосами и озвучиваются партиями (веса
  переключаются один раз на голос); пропорции — весом:
  `"sakura:60,madara:40"`;
* `--ids 17001 17002` — озвучить конкретные карточки;
* `--tag av_suspect` — только карточки с этим тегом;
* `--seed 42 --speed 1.0` — сэмпл и скорость.

Полезно знать: успешным карточкам ставится тег `av_voiced`, а голос
карточки — тег `av_voice::имя` (ансамбль при перезапусках сохраняет
раскладку). Итог каждого прогона пишется в `last_run.json`, отчёт —
в `%APPDATA%\AnkiVoice\reports\run_*.md`.

## Предпросмотр (без синтеза и без движка)

```
pipeline.bat preview --deck "Архитектура"
pipeline.bat preview --deck "Архитектура" --new      # что озвучит --new
pipeline.bat preview --deck "Архитектура" --voices "sakura,madara"
```

Показывает: какой текст уйдёт в синтез, режим каждой карточки
(mix/asis), сработала ли подстановка фуриганы (промахи помечены ⚠)
и раскладку ансамбля.

## Проверки и обслуживание

```
pipeline.bat check --deck "Архитектура"          полная проверка колоды
pipeline.bat check --deck "Архитектура" --fast   то же без скачивания аудио
pipeline.bat verify --deck "Архитектура"    проверить произношение озвученного
pipeline.bat qc-deck                         собрать колоду «Брак» с вариантами
pipeline.bat verdicts                        сводка по твоим вердиктам
pipeline.bat cleanup-media                   файлы tts_*.ogg без ссылок (отчёт)
pipeline.bat cleanup-media --apply           то же с удалением (необратимо)
pipeline.bat cleanup-media --deck "Архитектура"   сверять ссылки с одной колодой
```

## Голоса и сервер

```
pipeline.bat list              список голосов
pipeline.bat selftest          проверка окружения (запускать и при беде)
pipeline.bat test --voice madara --text "こんにちは"
pipeline.bat scan --apply     найти голоса в движке и дописать в voices.json
pipeline.bat serve --voice madara     поднять сервер и загрузить голос
pipeline.bat server                   поднять сервер без голоса
pipeline.bat indextts-server          сервис IndexTTS 2.5
```

Диагностика есть и у exe: `AnkiVoice.exe doctor`.

---

← [На главную страницу проекта](../README.md) · [English](cli.en.md)
