# Console

`pipeline.bat` is the same thing in the console; it finds the engine folder on
its own:

```
pipeline.bat list              list of voices
pipeline.bat selftest          check the environment (run it when in trouble)
pipeline.bat test --voice madara --text "こんにちは"
pipeline.bat voice --voice madara --deck "Архитектура" --mode both
pipeline.bat verify --deck "Архитектура"    check the pronunciation of what is voiced
pipeline.bat qc-deck                         build the "Брак" deck with variants
pipeline.bat verdicts                        summary of your verdicts
pipeline.bat check --deck "Архитектура"          full check of a deck
pipeline.bat check --deck "Архитектура" --fast   the same without downloading audio
pipeline.bat scan --apply     find voices in the engine and add them to voices.json
```

Diagnostics are available in the exe as well: `AnkiVoice.exe doctor`.

---

← [Back to the project page](../README.en.md) · [Русский](cli.md)
