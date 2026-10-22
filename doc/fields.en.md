# Card fields

Decks name their fields differently — where to take the text from and where to
write the audio is configurable (GUI: the “Поля колоды” tab; console: the
`voice` / `make-deck` / `check` commands):

```
--sentence-src "Sentence"             field with the sentence text
--sentence-audio "SentenceAudio"      field the sentence audio goes to
--word-src "Expression"               field with the word (furigana parsing works for Expression)
--word-audio "ExpressionAudio"        field the word audio goes to
--furigana-src "ExpressionFurigana"   field with the furigana of the main word
    --reading ""|mix|asis         reading mode (see above; empty = auto)
```

---

← [Back to the project page](../README.en.md) · [Русский](fields.md)
