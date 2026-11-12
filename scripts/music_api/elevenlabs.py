"""ElevenLabs Eleven Music（模型 music_v2_5）。

按段落给时长（每句一小节），所以生成出来的歌比较容易做到「一句一小节」，人声也基本准时进。
实测（2026-11）：一首 70 秒左右的歌约 1000 额度；5 版里有 2 版人声晚进两小节，所以一次出 2–3 版再挑。
接口只开放给付费档（Starter 起）；Creator 档起生成的音乐可以商用、上流媒体（以官方 Music Terms 为准）。
"""
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

NAME = "elevenlabs"
TITLE = "ElevenLabs Music"
KEY_HELP = "登录 elevenlabs.io → 左下角头像 → API Keys → Create（要付费档，Starter 起）"
COST_HELP = "约 1 分钟 ≈ 900 额度；一首 70 秒的歌约 1000 额度"

PRESETS = {
    # 念唱：两个音来回、句尾回主音，最接近抖音上那种口诀说唱（实测吐字比 boombap 差一点，但更像「唱」）
    "chant": [
        "Chinese melodic rap", "Mandarin sing-song chant", "melodic rap on two notes",
        "each line ends falling to the tonic", "mid-high bright male voice", "light autotune",
        "tight quantized sixteenth-note flow", "on-beat delivery", "one lyric line per bar",
        "{bpm} BPM", "E minor", "simple trap hi-hats", "soft piano loop",
        "clear diction", "catchy nursery-rhyme cadence", "great production quality",
    ],
    # 低沉说唱：吐字最清楚（实测 24 句全对），但没有念唱感
    "boombap": [
        "Chinese hip hop", "Mandarin rap", "male rap vocal", "melodic chant flow",
        "steady sixteenth-note flow", "one lyric line per bar", "boom bap drums",
        "{bpm} BPM", "E minor", "dark cinematic piano", "clear diction",
        "educational", "punchy", "great production quality",
    ],
}
NEG = {
    "chant": ["female vocal", "deep low voice", "gritty spoken rap", "English lyrics", "long instrumental gaps"],
    "boombap": ["female vocal", "sung chorus", "English lyrics", "autotune warble"],
}


def generate(work, sections, bpm=90, takes=2, key=None, preset="chant", dry=False, intro_bars=2):
    work = Path(work)
    out_dir = work / "歌"
    out_dir.mkdir(exist_ok=True)
    bar_ms = round(4 * 60000 / bpm)
    if preset not in PRESETS:
        raise SystemExit(f"错误：preset 只能是 {list(PRESETS)}")
    styles = [s.format(bpm=int(round(bpm))) for s in PRESETS[preset]]
    chunks = []
    if intro_bars > 0:
        chunks.append({"text": "[Intro]\n{instrumental beat, no vocals}", "duration_ms": bar_ms * max(2, intro_bars),
                       "positive_styles": styles, "negative_styles": ["vocals", "singing"]})
    for i, s in enumerate(sections):
        if i == 0:
            st = styles
        elif any(k in s["name"].lower() for k in ("hook", "chorus")) or "副歌" in s["name"] or "口诀" in s["name"]:
            st = ["same voice and beat as before", "clear spoken hook", "every word slow and clear",
                  "emphasized chant", "drums drop out briefly", f"{int(round(bpm))} BPM"]
        else:
            st = ["same voice and flow as before", "same beat", "relaxed clear delivery",
                  "explaining tone", "leave breathing space", f"{int(round(bpm))} BPM"]
        dur = bar_ms * len(s["lines"])
        if dur < 3000:
            raise SystemExit(f"错误：段落 [{s['name']}] 只有 {len(s['lines'])} 句，不到 3 秒（接口下限），一段至少 2 句")
        chunks.append({"text": f"[{s['name']}]\n" + "\n".join(s["lines"]), "duration_ms": dur,
                       "positive_styles": st, "negative_styles": NEG[preset]})
    body = {"model_id": "music_v2_5", "composition_plan": {"chunks": chunks}}
    total = sum(c["duration_ms"] for c in chunks) / 1000
    print(f"ElevenLabs：{len(chunks)} 段，共 {total:.0f} 秒，每版约 {total / 60 * 900:.0f} 额度，出 {takes} 版")
    made = []
    for _ in range(takes):
        n = len(list(out_dir.glob("生成_*.mp3"))) + 1
        (out_dir / f"生成请求_{n:02d}.json").write_text(json.dumps(body, ensure_ascii=False, indent=1), encoding="utf-8")
        if dry:
            print(f"  只写了请求（--dry）：歌/生成请求_{n:02d}.json")
            continue
        req = urllib.request.Request(
            "https://api.elevenlabs.io/v1/music?output_format=mp3_44100_192",
            data=json.dumps(body).encode("utf-8"),
            headers={"xi-api-key": key, "Content-Type": "application/json"}, method="POST")
        print(f"  生成第 {n} 版（一首约 1–2 分钟）…", flush=True)
        try:
            with urllib.request.urlopen(req, timeout=600) as r:
                data = r.read()
        except urllib.error.HTTPError as e:
            msg = e.read().decode("utf-8", "replace")[:600]
            hint = {401: "密钥不对或过期了：重新跑 mrv.py key elevenlabs", 402: "额度不够了",
                    403: "这个账号没有开通音乐接口（要付费档）"}.get(e.code, "")
            raise SystemExit(f"错误：ElevenLabs 返回 HTTP {e.code}。{hint}\n{msg}")
        except urllib.error.URLError as e:
            raise SystemExit(f"错误：连不上 ElevenLabs（{e.reason}）。检查网络或代理")
        out = out_dir / f"生成_{n:02d}.mp3"
        out.write_bytes(data)
        made.append(out)
        print(f"  已保存 歌/{out.name}（{len(data) // 1024} KB）", flush=True)
    return made


if __name__ == "__main__":
    sys.exit("用 mrv.py music <作品目录> --api elevenlabs 调用")
