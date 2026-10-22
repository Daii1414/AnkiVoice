# IndexTTS 2.5: установка, мост и ограничения

Раздел README описывает, чем движок отличается от GPT-SoVITS. Здесь — как его поставить и как он подключён.

Поставить IndexTTS 2.5:

```
git clone https://github.com/index-tts/index-tts.git D:\DOWNLOAD\index-tts
cd D:\DOWNLOAD\index-tts
uv sync --extra webui
uv tool install "huggingface-hub"
hf download IndexTeam/IndexTTS-2.5 --local-dir checkpoints
```

Папку укажи в «Приложении» (или нажми «Проверить» — AnkiVoice найдёт её
сам). Нужен `uv` в PATH и драйвер NVIDIA с CUDA 12.8 или новее.

**Зачем мост.** У IndexTTS нет HTTP-API: есть только Python-API и вебморда.
AnkiVoice поднимает рядом с собой небольшой сервис
(`lab/indextts_service.py` — едет в установщике), который **один раз**
загружает модель и отвечает на `POST /tts`. Без него на каждую карточку
пришлось бы грузить веса заново.

Что работает одинаково: QC акустический, режим чтения (авто/только кандзи),
правила подстановки чтения из фуриганы, запись звука в карточку, колода
«Брак» и вердикты.

Чего нет в режиме IndexTTS:

* **проверки содержания** (распознавание своим голосом) — она живёт в
  окружении GPT-SoVITS (faster-whisper). Если GPT-SoVITS не установлен,
  остаётся акустическая проверка, а распознавание отключается;
* ручных настроек сэмплирования (seed, temperature, top_p, top_k) — у
  IndexTTS их нет, интерфейс их прячет.

---

← [На главную страницу проекта](../README.md) · [English](engines.en.md)
