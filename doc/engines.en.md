# IndexTTS 2.5: installation, bridge and limits

The README section explains how this engine differs from GPT-SoVITS. This file
covers how to install it and how it is wired in.

Install IndexTTS 2.5:

```
git clone https://github.com/index-tts/index-tts.git D:\DOWNLOAD\index-tts
cd D:\DOWNLOAD\index-tts
uv sync --extra webui
uv tool install "huggingface-hub"
hf download IndexTeam/IndexTTS-2.5 --local-dir checkpoints
```

Point AnkiVoice at that folder in “App” (or press “Check” - it finds the
folder by itself). `uv` has to be in PATH and the NVIDIA driver needs CUDA
12.8 or newer.

**Why a bridge.** IndexTTS has no HTTP API - only a Python API and a web UI.
AnkiVoice starts a small service next to itself
(`lab/indextts_service.py`, shipped with the installer) that loads the model
**once** and answers `POST /tts`. Without it every card would reload the
weights.

What stays the same: the acoustic QC, the reading mode (auto / kanji only),
the rules for substituting the furigana reading, writing the audio into the
card, the review deck and the verdicts.

What is missing in the IndexTTS mode:

* the **content check** (recognising our own voice) - it lives in the
  GPT-SoVITS environment (faster-whisper). Without GPT-SoVITS the acoustic
  check remains and the recognition is off;
* the manual sampling settings (seed, temperature, top_p, top_k) - IndexTTS
  has none, the interface hides them.

---

← [Back to the project page](../README.en.md) · [Русский](engines.md)
