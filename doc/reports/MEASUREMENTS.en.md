# Measurements: every number quoted on the project page

One list. For each number: what was measured, on which sample, and why it has
that value. The detailed reports sit next to it: [G2P core comparison](REPORT-g2p-benchmark.md),
[quality control](REPORT-quality-v2.md). The history of the runs is in
[CHANGELOG](../../CHANGELOG.md).

All measurements were taken on one machine (Windows, RTX 2060, 6 GB VRAM) and
one deck - "New in digital construction". Other hardware gives other numbers,
the method stays the same.

## 1. How the engine reads kanji

**What was measured.** A blind comparison of two ways to hand the text to the
engine: kanji (the engine reads the kanji itself, in the context of the
sentence) and kana (everything converted to hiragana in advance). Judged blind
over 10 phrases.

| | kanji voice | kana voice | tie |
|---|---|---|---|
| voices out of 10 | 7 | 2 | 1 |

**Wrong terms.** In 12 phrases out of 150 the model read a term differently from
the card (`麻院[あさすさ]` -> "Asain"). In the mixed mode - 2 out of 150.

**Conclusion.** Kanji is the better input: the model reads connected speech and
handles particles itself. A term is read from the card furigana instead.

## 2. Reading kanji on the ROHAN4600 corpus

**What was measured.** 4600 sentences with reference readings. Metric - KER
(Character Error Rate): the share of characters that differ.

| variant | KER (kana as is) | KER (after long-vowel normalization) |
|---|---|---|
| product path `kanaize -> g2p_kana` | 2.74% | 2.90% |
| Haqumei core with the corpus options | 0.73% | 0.75% |

The product path trails not because of wrong readings but because of the
decision to leave kana alone: particles and signs stay as they are and the
frontend applies the particle rules. Full breakdown - in the
[benchmark report](REPORT-g2p-benchmark.md).

## 3. The reading dictionary: 63 difficult words

**What was measured.** The `app/kana_stress.py` battery: 63 words the core
stumbles on (half-katakana, latin, greetings, long vowels, domain terms).

- **49 of 63 pass** (48 on the old core, 46 before that);
- the 14 failures are domain terms of the construction domain (`合折釘`,
  `合印`, `相決リ`, `板矧ギ` and others): the card furigana covers them, not a
  general dictionary.

## 4. The pronunciation check

**What was measured.** 27 marked cards: the sound is recognized by the app's own
engine and compared with the text it was asked to say.

| | |
|---|---|
| confirmed defects | 2 |
| false alarms | 25 |

**Conclusion.** The check cannot decide for a human: the recognizer flips
domain terms (`だいくはこうさぶ` -> "ないくはこうさぶん"), and by text alone they
cannot be told apart from a real error. So the check only advises - it marks
suspicious chunks and collects them into a "Reject" deck.

## 5. Latin letters and digits

**What was measured.** A phrase with the term "3D": our own transliteration
into kana versus handing the term to the engine as is.

| | time | coverage |
|---|---|---|
| own transliteration ("3D" -> "surīī") | 96 s | 0.89 |
| term handed to the engine as is | 4 s | 1.00 |

**Conclusion.** Latin and digits are not converted to kana: the engine reads
them better and there is no risk of a repetition loop.

## 6. IndexTTS 2.5 speed

**What was measured.** The same phrase on an RTX 2060 (6 GB) before and after
the speedup: 12 diffusion steps instead of 25 and fp16 instead of fp32.

| | time per phrase |
|---|---|
| stock | 186-229 s |
| sped up | 30-60 s |

## 7. The project's own checks

| command | what it checks |
|---|---|
| `pipeline.bat selftest` | 10 reading substitution checks and 11 reading-mode checks |
| `python app/kana_stress.py` | 63 difficult words (section 3) |
| `python lab/bench_rohan.py` | the kanji reading benchmark on ROHAN4600 (section 2) |
