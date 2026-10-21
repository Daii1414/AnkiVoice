# -*- coding: utf-8 -*-
"""Сервис IndexTTS 2.5 для AnkiVoice: держит модель в памяти и отдаёт звук.

У IndexTTS нет HTTP-API, а грузить веса на каждую карточку — десятки секунд.
Поэтому маленький сервис: модель загружается один раз, синтез идёт по HTTP.

Запуск (в окружении IndexTTS, через uv):

    uv run --project D:\\DOWNLOAD\\index-tts python indextts_service.py \\
        --model-dir D:\\DOWNLOAD\\index-tts\\checkpoints --port 9881

API:
    GET  /health -> {"ok": true, "model": "IndexTTS-2.5", "device": "cuda"}
    POST /tts    -> WAV-байты (Content-Type: audio/wav)
         {"text": "...", "spk_audio_prompt": "C:/ref.wav", "lang": "JA",
          "duration_factor": 1.0, "emo_alpha": 1.0, "emo_audio_prompt": null}
"""
import argparse
import json
import os
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

TTS = None          # модель
TTS_LOCK = threading.Lock()
STATE = {"model": "", "device": "", "loaded_at": 0, "error": ""}


def log(msg):
    sys.stderr.write("[indextts] %s\n" % msg)
    sys.stderr.flush()


def load_model(model_dir, cfg, use_bf16=True, device=None):
    global TTS
    from indextts.infer_v2_5 import IndexTTS2
    t0 = time.time()
    TTS = IndexTTS2(cfg_path=cfg, model_dir=model_dir,
                    use_bf16=use_bf16, device=device)
    STATE["model"] = os.path.basename(os.path.normpath(model_dir))
    STATE["device"] = str(getattr(TTS, "device", device or "?"))
    STATE["loaded_at"] = time.time()
    log("модель загружена за %.1f c (%s)" % (time.time() - t0, STATE["device"]))


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        pass                       # тише: лог и так есть

    def do_GET(self):
        if self.path.split("?")[0] == "/health":
            self._json({"ok": TTS is not None, "model": STATE["model"],
                        "device": STATE["device"],
                        "uptime": round(time.time() - STATE["loaded_at"], 1),
                        "error": STATE["error"]})
        else:
            self._json({"error": "unknown path"}, 404)

    def do_POST(self):
        if self.path.split("?")[0] != "/tts":
            self._json({"error": "unknown path"}, 404)
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
        except Exception as e:
            self._json({"error": "bad request: %r" % e}, 400)
            return
        if TTS is None:
            self._json({"error": "модель не загружена"}, 503)
            return
        text = (body.get("text") or "").strip()
        ref = body.get("spk_audio_prompt") or ""
        if not text or not ref:
            self._json({"error": "нужны text и spk_audio_prompt"}, 400)
            return
        if not os.path.isfile(ref):
            self._json({"error": "нет файла референса: %s" % ref}, 400)
            return
        lang = (body.get("lang") or "JA")
        out_path = None
        try:
            with TTS_LOCK:
                fd, out_path = tempfile.mkstemp(suffix=".wav")
                os.close(fd)
                TTS.infer(
                    spk_audio_prompt=ref,
                    text=text,
                    output_path=out_path,
                    lang=lang,
                    emo_audio_prompt=body.get("emo_audio_prompt") or None,
                    emo_alpha=float(body.get("emo_alpha") or 1.0),
                    duration_factor=float(body.get("duration_factor") or 1.0),
                    verbose=False,
                )
            with open(out_path, "rb") as f:
                blob = f.read()
        except Exception as e:
            import traceback
            log("ошибка синтеза: %s" % traceback.format_exc()[-800:])
            self._json({"error": str(e)}, 500)
            return
        finally:
            if out_path and os.path.exists(out_path):
                try:
                    os.remove(out_path)
                except OSError:
                    pass
        self.send_response(200)
        self.send_header("Content-Type", "audio/wav")
        self.send_header("Content-Length", str(len(blob)))
        self.end_headers()
        self.wfile.write(blob)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model-dir", required=True)
    ap.add_argument("--cfg", default=None)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=9881)
    ap.add_argument("--no-bf16", action="store_true")
    ap.add_argument("--device", default=None)
    args = ap.parse_args()

    model_dir = os.path.abspath(args.model_dir)
    cfg = args.cfg or os.path.join(model_dir, "config.yaml")
    if not os.path.isdir(model_dir):
        raise SystemExit("нет папки с весами: %s" % model_dir)
    if not os.path.isfile(cfg):
        raise SystemExit("нет конфига: %s" % cfg)
    log("папка: %s" % model_dir)
    load_model(model_dir, cfg, use_bf16=not args.no_bf16, device=args.device)
    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    log("слушаю http://%s:%d" % (args.host, args.port))
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
