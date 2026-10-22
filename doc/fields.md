# Поля карточек

У разных колод поля называются по-разному — откуда брать текст и куда писать
звук настраивается (GUI: вкладка «Поля колоды»; консоль: флаги `voice` /
`make-deck` / `check`):

```
--sentence-src "Sentence"             поле с текстом предложения
--sentence-audio "SentenceAudio"      поле, куда кладётся звук предложения
--word-src "Expression"               поле со словом (для Expression работает разбор фуриганы)
--word-audio "ExpressionAudio"        поле, куда кладётся звук слова
--furigana-src "ExpressionFurigana"   поле с фуриганой основного слова
    --reading ""|mix|asis         режим чтения (см. выше; пусто — авто)
```

---

← [На главную страницу проекта](../README.md) · [English](fields.en.md)
