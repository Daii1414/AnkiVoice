# Консоль

`pipeline.bat` — то же самое в консоли, сам находит папку движка:

```
pipeline.bat list              список голосов
pipeline.bat selftest          проверка окружения (запускать и при беде)
pipeline.bat test --voice madara --text "こんにちは"
pipeline.bat voice --voice madara --deck "Архитектура" --mode both
pipeline.bat verify --deck "Архитектура"    проверить произношение озвученного
pipeline.bat qc-deck                         собрать колоду «Брак» с вариантами
pipeline.bat verdicts                        сводка по твоим вердиктам
pipeline.bat check --deck "Архитектура"          полная проверка колоды
pipeline.bat check --deck "Архитектура" --fast   то же без скачивания аудио
pipeline.bat scan --apply     найти голоса в движке и дописать в voices.json
```

Диагностика есть и у exe: `AnkiVoice.exe doctor`.

---

← [На главную страницу проекта](../README.md) · [English](cli.en.md)
