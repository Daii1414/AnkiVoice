# -*- coding: utf-8 -*-
"""Версии библиотек для Python-окружения GPT-SoVITS на Linux.

Windows-пакет движка везёт проверенное окружение (runtime/Lib/site-packages).
На Linux его не запустить, но его версии — лучший ориентир: с самыми
свежими transformers/pytorch_lightning/fast_langdetect api_v2.py падает
ещё на импорте. Скрипт печатает файл ограничений (pip/uv -c):

  * общие рамки (setuptools<81 и т.п.) — всегда;
  * версии из runtime/ пакета — для пакетов из requirements.txt движка и
    их известных «капризных» зависимостей. torch/CUDA, onnxruntime,
    faster-whisper и pyopenjtalk не фиксируются: на Linux у них свои
    сборки (CUDA 12, свежий ctranslate2, сборка pyopenjtalk из исходников).

Запуск: python engine_constraints.py <папка GPT-SoVITS>  > constraints.txt
"""
import os
import re
import sys

# всегда: без них движок не импортируется на свежем pip
COMMON = [
    "setuptools<81",          # pkg_resources (его зовёт librosa 0.9) убран в 81
    "transformers<4.51",      # 5.x сломал импорт Wav2Vec2FeatureExtractor
    "numpy<2",
]

# Движок из git (без Windows-рантайма): рамки эпохи релиза 20250606v2pro.
# requirements.txt движка почти без верхних границ, и свежий pip берёт
# версии на год новее кода — проверка `uv pip install --dry-run` давала
# gradio 3.36 при gradio_client 2.7, fast-langdetect 1.x (другое API),
# peft 0.21 и т.п.
GIT_ENGINE = [
    "gradio==4.44.1",
    "gradio-client==1.3.0",
    "fast-langdetect>=0.3.1,<0.4",
    "peft<0.16",
    "pytorch-lightning<2.6",
    "fastapi<0.116",
    "huggingface-hub<0.33",
    "x-transformers<2.4",
    "rotary-embedding-torch<0.9",
    "numba<0.62",
    "ctranslate2<4.7",
]

# версии этих пакетов берём из Windows-рантайма, если он есть
PIN_FROM_RUNTIME = {
    "transformers", "tokenizers", "peft", "accelerate", "huggingface-hub",
    "pytorch-lightning", "torchmetrics", "lightning-utilities",
    "fastapi", "pydantic", "pydantic-core", "starlette",
    "gradio", "gradio-client",
    "fast-langdetect", "fasttext-predict", "split-lang",
    "librosa", "numba", "llvmlite", "numpy", "scipy",
    "g2pk2", "g2p-en", "inflect", "pypinyin", "cn2an", "jieba",
    "rotary-embedding-torch", "x-transformers", "einops",
    "wordsegment", "tojyutping", "ko-pron", "sentencepiece", "chardet",
    "funasr", "modelscope", "nltk", "attrdict",
}

# никогда не фиксируем: на Linux свои сборки
NEVER = {"torch", "torchaudio", "torchvision", "torch-directml",
         "onnxruntime", "onnxruntime-gpu", "faster-whisper", "ctranslate2",
         "pyopenjtalk", "triton", "av", "opencc"}


def _canon(name):
    return re.sub(r"[-_.]+", "-", name).lower()


def runtime_versions(engine):
    site = os.path.join(engine, "runtime", "Lib", "site-packages")
    out = {}
    try:
        names = os.listdir(site)
    except OSError:
        return out
    for n in names:
        m = re.match(r"^(.+?)-([^-]+)\.dist-info$", n)
        if m:
            out[_canon(m.group(1))] = m.group(2)
    return out


def requirement_names(engine):
    names = set()
    try:
        with open(os.path.join(engine, "requirements.txt"),
                  encoding="utf-8") as f:
            for line in f:
                line = line.split("#", 1)[0].strip()
                m = re.match(r"^([A-Za-z0-9_.\-]+)", line)
                if m:
                    names.add(_canon(m.group(1)))
    except OSError:
        pass
    return names


def build(engine):
    lines = list(COMMON)
    have = runtime_versions(engine)
    if not have:
        return lines + GIT_ENGINE
    want = (requirement_names(engine) | PIN_FROM_RUNTIME) - NEVER
    pinned = sorted(n for n in want if n in have)
    if pinned:
        lines = [c for c in lines
                 if _canon(re.split(r"[<>=!]", c)[0]) not in pinned]
        lines += ["%s==%s" % (n, have[n]) for n in pinned]
    return lines


def main():
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        sys.exit(2)
    for line in build(sys.argv[1]):
        print(line)


if __name__ == "__main__":
    main()
