# Console

`pipeline.bat` is the same thing in the console; it finds the engine folder
on its own.

## Dubbing

```
pipeline.bat voice --voice madara --deck "Architecture" --mode both
```

* `--mode both|sentence|expression` — word + sentence / sentence only /
  word only;
* `--limit N` — how many cards (no limit — the whole deck);
* `--force` — "Rebuild everything" (overwrites the audio);
* `--new` — only cards **without** the `av_voiced` tag: added cards -
  one command;
* `--changed` — "Rebuild **only changed**": text and voice match the last
  run - the card is skipped (checked against `voiced_manifest.json`);
  mutually exclusive with `--force`;
* `--retry` — re-run the **failed** operations of the previous run
  (from `last_run.json`); already voiced fields are skipped;
* `--voices "sakura,madara"` — **ensemble**: cards are split between the
  voices at random and voiced in parts (weights switch once per voice);
  proportions via weights: `"sakura:60,madara:40"`;
* `--ids 17001 17002` — voice specific cards;
* `--tag av_suspect` — only cards with this tag;
* `--seed 42 --speed 1.0` — sample and speed.

Good to know: successfully voiced cards get the `av_voiced` tag, and the
card's voice is tagged `av_voice::<name>` (the ensemble keeps its layout
across re-runs). Every run writes `last_run.json` and a report to
`%APPDATA%\AnkiVoice\reports\run_*.md`.

## Preview (no synthesis, no engine)

```
pipeline.bat preview --deck "Architecture"
pipeline.bat preview --deck "Architecture" --new      # what --new would voice
pipeline.bat preview --deck "Architecture" --voices "sakura,madara"
```

Shows: the exact text that would go to synthesis, each card's reading mode
(mix/asis), whether the furigana substitution worked (misses flagged ⚠)
and the ensemble split.

## Checks and maintenance

```
pipeline.bat check --deck "Architecture"          full check of a deck
pipeline.bat check --deck "Architecture" --fast   the same without downloading audio
pipeline.bat verify --deck "Architecture"    check the pronunciation of what is voiced
pipeline.bat qc-deck                         build the "Брак" deck with variants
pipeline.bat verdicts                        summary of your verdicts
pipeline.bat cleanup-media                   tts_*.ogg files with no references (report)
pipeline.bat cleanup-media --apply           the same with deletion (irreversible)
pipeline.bat cleanup-media --deck "Architecture"   check links against one deck
```

## Voices and server

```
pipeline.bat list              list of voices
pipeline.bat selftest          check the environment (run it when in trouble)
pipeline.bat test --voice madara --text "こんにちは"
pipeline.bat scan --apply     find voices in the engine and add them to voices.json
pipeline.bat serve --voice madara     start the server and load the voice
pipeline.bat server                   start the server without a voice
pipeline.bat indextts-server          IndexTTS 2.5 service
```

Diagnostics are available in the exe as well: `AnkiVoice.exe doctor`.

---

← [Back to the project page](../README.en.md) · [Русский](cli.md)
