# How text becomes hiragana

The sentence goes to the engine **in kanji**: GPT-SoVITS reads the kanji
itself, in the context of the sentence - that is what makes the sound connected
instead of a set of separate pieces.

The `kanaize()` pipeline prepares hiragana - but only where it is needed:

* **the main term** - in the mode with a furigana the reading is taken from the
  card's furigana; if the furigana does not fit (the word is not found in the
  text, the reading still has kanji in it) the word is converted to kana by our
  own pipeline;
* **in the "kanji only" mode** nothing is prepared: both the word and the
  sentence go to the engine as they are, it reads them itself.

The steps of `kanaize()`:

1. **NFKC normalization** — full-width letters/digits and half-width katakana
   are folded into normal forms (punctuation is left alone);
2. **Latin → katakana by letters** (`IEC` → アイイーシー);
3. **katakana → hiragana** (greetings コンニチハ/コンバンハ stay katakana —
   otherwise MeCab reads them as a particle; the repetition marks ヽゝゞヾ are
   expanded contextually — repeat of the previous syllable);
4. **g2p only for the kanji that are left**: Haqumei reads every word in the
   context of the sentence (sandhi, neighbouring katakana), with Sudachi over
   the UniDic dictionary and pyopenjtalk (MeCab) as fallbacks; digits always go
   through MeCab, because Sudachi reads numbers as dates (2024 → 二月二日);
5. **one more katakana → hiragana pass** — and the API receives pure hiragana.

What the pipeline **does not touch**: the note in Anki itself (a copy of the
text is processed) and the card's furigana (it is only used as a reading
source).

Reading is covered by tests: `pipeline.bat selftest` (10 substitution checks
and 11 reading-mode checks) and the extended battery
`python app/kana_stress.py` (63 difficult words). Detailed measurements live in
[doc/reports/](reports); every number quoted on this page is collected in
[doc/reports/MEASUREMENTS.en.md](reports/MEASUREMENTS.en.md).

---

← [Back to the project page](../README.en.md) · [Русский](reading.md)
