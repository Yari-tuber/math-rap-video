"""逐字强制对齐：已知歌词，在人声里找出每个字从哪一刻开始唱。mrv.py song 会自动调用，一般不用手动跑。

用法:
    python align_lyrics.py --audio 人声.wav --text 歌词.txt --out 对齐.words.json [--lang Chinese]

模型：Qwen3-ForcedAligner-0.6B（阿里通义，Apache-2.0，Hugging Face：Qwen/Qwen3-ForcedAligner-0.6B-hf），一次最多 5 分钟音频。
需要：torch、transformers（5.x）、numpy、ffmpeg。有 NVIDIA 显卡更快，没有也能用 CPU（慢一些）。
模型第一次会自动从 Hugging Face 下载约 1.8 GB；国内先设环境变量 HF_ENDPOINT=https://hf-mirror.com，
或者自己下好，在 ~/.math-rap-video/config.json 写 "aligner_model": "<模型文件夹>"（mrv.py doctor --model 帮你写）。
输出：{"words": [{"text": 字, "start_time": 秒, "end_time": 秒}, ...]}，和 prepare_audio.py 的 --words / --refine 格式一样。
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import unicodedata
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(errors="replace")
    except Exception:  # noqa: BLE001
        pass

MODEL_ID = "Qwen/Qwen3-ForcedAligner-0.6B-hf"


def kept(ch):
    return ch == "'" or unicodedata.category(ch)[0] in ("L", "N")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--audio", required=True)
    ap.add_argument("--text", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--lang", default="Chinese")
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from mrv_config import get as cfg
    ap.add_argument("--model", default=os.environ.get("MRV_ALIGNER_MODEL") or cfg("aligner_model") or MODEL_ID)
    a = ap.parse_args()
    import numpy as np
    ff = shutil.which("ffmpeg") or sys.exit("找不到 ffmpeg")
    wav = np.frombuffer(subprocess.run([ff, "-v", "error", "-i", a.audio, "-f", "f32le", "-ar", "16000", "-ac", "1", "-"],
                                       capture_output=True, check=True).stdout, "<f4").copy()
    dur = len(wav) / 16000
    if dur > 300:
        sys.exit(f"音频 {dur:.0f} 秒，对齐模型一次最多 5 分钟")
    text = Path(a.text).read_text(encoding="utf-8-sig")
    n_chars = sum(1 for c in text if kept(c))
    import torch
    from transformers import AutoModelForTokenClassification, AutoProcessor
    cuda = torch.cuda.is_available()
    dtype = torch.bfloat16 if cuda and torch.cuda.is_bf16_supported() else torch.float32
    dev = "cuda" if cuda else "cpu"
    print(f"加载对齐模型（{a.model}，{dev}）…", flush=True)
    proc = AutoProcessor.from_pretrained(a.model)
    model = AutoModelForTokenClassification.from_pretrained(a.model, dtype=dtype).to(dev).eval()
    inputs, words = proc.prepare_forced_aligner_inputs(audio=wav, transcript=text, language=a.lang)
    inputs = inputs.to(dev, dtype)
    with torch.inference_mode():
        out = model(**inputs)
    items = proc.decode_forced_alignment(logits=out.logits, input_ids=inputs["input_ids"], word_lists=words,
                                         timestamp_token_id=model.config.timestamp_token_id)[0]
    res = [{"text": str(it.get("text", "")), "start_time": round(float(it["start_time"]), 3), "end_time": round(float(it["end_time"]), 3)} for it in items]
    got = sum(sum(1 for c in r["text"] if kept(c)) for r in res)
    if got != n_chars:
        print(f"⚠ 对齐出 {got} 个字，歌词里 {n_chars} 个字：歌词和唱的可能不完全一样", flush=True)
    Path(a.out).write_text(json.dumps({"model": a.model, "device": dev, "words": res}, ensure_ascii=False), encoding="utf-8")
    print(f"对齐了 {len(res)} 个字，{dur:.1f} 秒 → {a.out}", flush=True)


if __name__ == "__main__":
    main()
