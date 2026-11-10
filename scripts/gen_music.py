"""【可选】用 ElevenLabs Eleven Music 按 lyrics.md 生成带人声的说唱歌曲。
音频本来由用户或客户自己准备（见 references/audio.md）；只有用户明确要求代为生成、并提供自己的 API Key 时才用本脚本。
每版都会消耗用户的额度（约 70 秒的歌 ≈ 1000 额度），运行前先告诉用户。

用法:
    python gen_music.py <作品目录> [--bpm 90] [--preset chant|boombap] [--takes 2] [--seed N] [--intro-bars 2]

按段落给时长（每句一小节），所以生成结果比较容易做到一句一小节。
API Key：环境变量 ELEVENLABS_API_KEY；或环境变量 ELEVENLABS_API_KEY_FILE 指向存 Key 的文件；或 ~/.elevenlabs_api_key。不会打印。
输出：生成_NN.mp3 + 生成请求_NN.json。生成后照常用 prepare_audio.py 处理。
"""
import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

for _s in (sys.stdout, sys.stderr):  # 系统编码不支持中文时也不要崩
    try:
        _s.reconfigure(errors="replace")
    except Exception:  # noqa: BLE001
        pass

ap = argparse.ArgumentParser()
ap.add_argument("work")
ap.add_argument("--bpm", type=float, default=90)
ap.add_argument("--preset", default="chant", choices=["chant", "boombap"])
ap.add_argument("--takes", type=int, default=1)
ap.add_argument("--seed", type=int, default=None)
ap.add_argument("--intro-bars", type=int, default=2)
ap.add_argument("--lyrics", default=None)
args = ap.parse_args()

work = Path(args.work)
bpm = args.bpm
bar_ms = round(4 * 60000 / bpm)


def api_key():
    if os.environ.get("ELEVENLABS_API_KEY"):
        return os.environ["ELEVENLABS_API_KEY"].strip()
    cands = [os.environ.get("ELEVENLABS_API_KEY_FILE"), str(Path.home() / ".elevenlabs_api_key")]
    for p in cands:
        if p and Path(p).exists():
            return Path(p).read_text().strip()
    sys.exit("找不到 ElevenLabs API Key：设置环境变量 ELEVENLABS_API_KEY（或 ELEVENLABS_API_KEY_FILE 指向存 Key 的文件）")


sections = []
lyr = work / args.lyrics if args.lyrics else next(
    (work / n for n in ("lyrics.md", "歌词.md") if (work / n).exists()), work / "lyrics.md")
for line in lyr.read_text(encoding="utf-8-sig").splitlines():
    m = re.match(r"##\s*\[(.+?)\]", line)
    if m:
        sections.append({"name": m.group(1), "lines": []})
        continue
    m = re.match(r"\d+\.\s*(.+)", line)
    if m and sections:
        sections[-1]["lines"].append(m.group(1).strip())
if not sections:
    sys.exit("歌词文件里没有找到 '## [段名]' 段落")

PRESETS = {
    # 念唱：两个音来回、句尾回主音，最接近"Rap&科学"那种口诀说唱
    "chant": [
        "Chinese melodic rap", "Mandarin sing-song chant", "melodic rap on two notes",
        "each line ends falling to the tonic", "mid-high bright male voice", "light autotune",
        "tight quantized sixteenth-note flow", "on-beat delivery", "one lyric line per bar",
        f"{int(bpm)} BPM", "E minor", "simple trap hi-hats", "soft piano loop",
        "clear diction", "catchy nursery-rhyme cadence", "great production quality",
    ],
    # 低沉说唱：吐字最清楚，但没有念唱感
    "boombap": [
        "Chinese hip hop", "Mandarin rap", "male rap vocal", "melodic chant flow",
        "steady sixteenth-note flow", "one lyric line per bar", "boom bap drums",
        f"{int(bpm)} BPM", "E minor", "dark cinematic piano", "clear diction",
        "educational", "punchy", "great production quality",
    ],
}
global_styles = PRESETS[args.preset]
neg = (["female vocal", "deep low voice", "gritty spoken rap", "English lyrics", "long instrumental gaps"]
       if args.preset == "chant" else ["female vocal", "sung chorus", "English lyrics", "autotune warble"])

chunks = []
if args.intro_bars > 0:
    chunks.append({"text": "[Intro]\n{instrumental beat, no vocals}", "duration_ms": bar_ms * max(2, args.intro_bars),
                   "positive_styles": global_styles, "negative_styles": ["vocals", "singing"]})
for i, s in enumerate(sections):
    if i == 0:
        styles = global_styles
    elif "hook" in s["name"].lower():
        styles = ["same voice and beat as before", "clear spoken hook", "every word slow and clear",
                  "emphasized chant", "drums drop out briefly", f"{int(bpm)} BPM"]
    else:
        styles = ["same voice and flow as before", "same beat", "relaxed clear delivery",
                  "explaining tone", "leave breathing space", f"{int(bpm)} BPM"]
    dur = bar_ms * len(s["lines"])
    if dur < 3000:
        sys.exit(f"段落 [{s['name']}] 只有 {len(s['lines'])} 句，时长不足 3 秒（API 下限），至少 2 句")
    chunks.append({"text": f"[{s['name']}]\n" + "\n".join(s["lines"]), "duration_ms": dur,
                   "positive_styles": styles, "negative_styles": neg})

body = {"model_id": "music_v2_5", "composition_plan": {"chunks": chunks}}
if args.seed is not None:
    body["seed"] = args.seed
total = sum(c["duration_ms"] for c in chunks)
print("段落", [(c["text"].splitlines()[0], c["duration_ms"]) for c in chunks], "总长", total / 1000, "秒")
key = api_key()

for _ in range(args.takes):
    n = len(list(work.glob("生成_*.mp3"))) + 1
    (work / f"生成请求_{n:02d}.json").write_text(json.dumps(body, ensure_ascii=False, indent=1), encoding="utf-8")
    req = urllib.request.Request(
        "https://api.elevenlabs.io/v1/music?output_format=mp3_44100_192",
        data=json.dumps(body).encode("utf-8"),
        headers={"xi-api-key": key, "Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            data = r.read()
            song_id = r.headers.get("song-id")
    except urllib.error.HTTPError as e:
        sys.exit(f"HTTP {e.code} {e.read().decode('utf-8', 'replace')[:1500]}")
    out = work / f"生成_{n:02d}.mp3"
    out.write_bytes(data)
    print("已保存", out, f"{len(data)} 字节", "song-id", song_id)
