"""音频入口：客户给一条带人声的音频 + 歌词，算出每句（每个字）的时间和节拍网格，写成 timing.json。
之后的分镜、字幕、动画、背景切换全部读 timing.json；换音频只需重跑本脚本。

用法:
    python prepare_audio.py <作品目录> --audio 歌.mp3 --srt 识别.srt        # 任何工具导出的 SRT（剪映、Whisper、平台自带字幕…）
    python prepare_audio.py <作品目录> --audio 歌.mp3 --words x.words.json  # 带逐字时间的 JSON（words:[{text,start_time,end_time}]）
    python prepare_audio.py <作品目录> --audio 歌.mp3 --grid --entry 5.3    # 没有字幕：按"一句一小节"从人声进入点推算
    可选: --lyrics 歌词文件（默认 lyrics.md）   --bpm 90（速度提示）   --no-beat（纯讲解配音，没有节拍）
          --intro-bars 2（约定的前奏小节数，用来判断人声是不是进晚了）
          --out timing_02.json（比较多版音频时，每版写到不同文件，选定后复制成 timing.json）
          --deep（分离人声，量卡拍偏差；需要 demucs，要多跑几分钟）

输出最后一行是"结论"：可用 / 建议换一版（并列出原因）。结论为"建议换一版"时退出码是 3，timing 文件照常写出。

SRT 不需要和歌词逐句对应，也允许有错别字（唱腔常被识别成同音字）：脚本按字把识别结果对到歌词上，
对不上的字在前后之间插值。输出里会报告每句的匹配率，低于 50% 的句子要人工听一下。
依赖：ffmpeg、numpy、librosa（--no-beat 时不需要 librosa）；pypinyin 可选（有的话按拼音匹配，更耐同音字）。
"""
import argparse
import difflib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):  # 系统编码不支持中文时也不要崩
    try:
        _s.reconfigure(errors="replace")
    except Exception:  # noqa: BLE001
        pass

ap = argparse.ArgumentParser()
ap.add_argument("work")
ap.add_argument("--audio", required=True)
ap.add_argument("--srt")
ap.add_argument("--words")
ap.add_argument("--grid", action="store_true")
ap.add_argument("--entry", type=float, help="--grid 时人声进入的秒数")
ap.add_argument("--bars-per-line", type=float, default=1.0)
ap.add_argument("--lyrics", default=None, help="歌词文件，默认 lyrics.md（没有则找 歌词.md）")
ap.add_argument("--bpm", type=float, default=None)
ap.add_argument("--no-beat", action="store_true")
ap.add_argument("--deep", action="store_true")
ap.add_argument("--out", default="timing.json")
ap.add_argument("--intro-bars", type=float, default=None)
args = ap.parse_args()

work = Path(args.work).resolve()
audio = Path(args.audio).resolve()
if not audio.exists():
    sys.exit(f"找不到音频 {audio}")
if audio.parent != work:
    shutil.copy2(audio, work / audio.name)
    audio = work / audio.name

# ---------------- 歌词 ----------------
if args.lyrics:
    lp = Path(args.lyrics) if Path(args.lyrics).is_absolute() else work / args.lyrics
else:
    lp = next((work / n for n in ("lyrics.md", "歌词.md", "lyrics.txt") if (work / n).exists()), work / "lyrics.md")
if not lp.exists():
    sys.exit(f"找不到歌词文件 {lp}（每句一行，格式：'1. 歌词'）")
raw = lp.read_text(encoding="utf-8-sig").splitlines()
lyrics = [m.group(1).strip() for m in (re.match(r"\s*\d+[\.、]\s*(.+)", x) for x in raw) if m]
if not lyrics:  # 纯文本：每个非空、非 # 开头的行算一句
    lyrics = [x.strip() for x in raw if x.strip() and not x.lstrip().startswith(("#", "-", ">", "|"))]
if not lyrics:
    sys.exit(f"{lp} 里没有读到歌词行（格式：'1. 歌词' 每句一行）")

try:
    from pypinyin import lazy_pinyin

    def key(ch):
        return lazy_pinyin(ch)[0] if "一" <= ch <= "鿿" else ch
    MATCH = "拼音"
except Exception:  # noqa: BLE001
    def key(ch):
        return ch
    MATCH = "字"


def is_word_char(ch):
    return ch.isalnum()


def norm_chars(text):
    return [c.lower() for c in text if is_word_char(c)]


def ffprobe_duration(p):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                       capture_output=True, text=True, check=True)
    return float(r.stdout.strip())


DUR = ffprobe_duration(audio)

# ---------------- 识别结果 → 字时间线 [(字, 起, 止)] ----------------
timeline = []


def ts(x):
    h, m, s = x.replace(",", ".").split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


if args.srt:
    txt = Path(args.srt).read_text(encoding="utf-8-sig")
    for block in re.split(r"\n\s*\n", txt.strip()):
        m = re.search(r"(\d+:\d+:\d+[,.]\d+)\s*-->\s*(\d+:\d+:\d+[,.]\d+)", block)
        if not m:
            continue
        s, e = ts(m.group(1)), ts(m.group(2))
        body = block[m.end():].strip()
        cs = norm_chars(re.sub(r"<[^>]+>", "", body))
        for j, c in enumerate(cs):
            timeline.append((c, s + (e - s) * j / len(cs), s + (e - s) * (j + 1) / len(cs)))
    SOURCE = f"SRT（{Path(args.srt).name}）"
elif args.words:
    d = json.loads(Path(args.words).read_text(encoding="utf-8-sig"))
    for w in d["words"]:
        cs = norm_chars(w.get("text", ""))
        s = w.get("start_time", w.get("start"))
        e = w.get("end_time", w.get("end", s))
        for j, c in enumerate(cs):
            timeline.append((c, s + (e - s) * j / len(cs), s + (e - s) * (j + 1) / len(cs)))
    SOURCE = f"逐字 JSON（{Path(args.words).name}）"
elif not args.grid:
    sys.exit("需要 --srt、--words 或 --grid 之一")

# ---------------- 节拍网格 ----------------
bpm, beat0 = args.bpm or 90.0, 0.0
if not args.no_beat:
    import librosa
    import numpy as np

    SR, HOP = 22050, 512
    y, _ = librosa.load(audio, sr=SR, mono=True)
    env = librosa.onset.onset_strength(y=y, sr=SR, hop_length=HOP)
    fps = SR / HOP
    tempo0 = float(np.atleast_1d(librosa.feature.tempo(onset_envelope=env, sr=SR))[0])
    if args.bpm:  # 检测结果常是一半或两倍，按提示取最近的倍数
        tempo0 = min((tempo0 * m for m in (0.5, 2 / 3, 1, 1.5, 2)), key=lambda x: abs(x - args.bpm))
    best = (-1.0, 60 / tempo0, 0.0)
    # 不用 librosa.beat.beat_track（部分环境 numba 会崩），直接拟合恒定网格
    for b in np.arange(tempo0 * 0.97, tempo0 * 1.03, 0.02):
        per = 60 / b
        for ph in np.arange(0, per, 0.005):
            fr = np.clip(np.round(np.arange(ph, DUR, per) * fps).astype(int), 0, len(env) - 1)
            sc = float(env[fr].mean())
            if sc > best[0]:
                best = (sc, per, ph)
    bpm, beat0 = round(60 / best[1], 2), round(float(best[2]), 3)
BEAT = 60 / bpm
BAR = 4 * BEAT

# ---------------- 把时间对到歌词上 ----------------
lines = []
if args.grid:
    if args.entry is None:
        sys.exit("--grid 需要 --entry（人声进入的秒数，听一下或看波形）")
    step = BAR * args.bars_per_line
    for i, text in enumerate(lyrics):
        s = args.entry + i * step
        e = s + step * 0.93
        n = max(1, len(text))
        lines.append({"i": i + 1, "start": round(s, 3), "end": round(e, 3), "text": text,
                      "ct": [round(s + (e - s) * k / n, 3) for k in range(len(text))], "match": None})
    SOURCE = "按小节推算（--grid）"
else:
    if not timeline:
        sys.exit("识别结果里没有读到任何带时间的文字")
    L = []  # (key, 行号, 行内位置)
    for li, text in enumerate(lyrics):
        for pos, ch in enumerate(text):
            if is_word_char(ch):
                L.append((key(ch.lower()), li, pos))
    A = [key(c) for c, _, _ in timeline]
    sm = difflib.SequenceMatcher(None, [k for k, _, _ in L], A, autojunk=False)
    t_start = [None] * len(L)
    t_end = [None] * len(L)
    for blk in sm.get_matching_blocks():
        for k in range(blk.size):
            t_start[blk.a + k] = timeline[blk.b + k][1]
            t_end[blk.a + k] = timeline[blk.b + k][2]
    matched = [x is not None for x in t_start]
    if sum(matched) < 0.3 * len(L):
        sys.exit(f"歌词和识别结果只对上 {sum(matched)}/{len(L)} 个字：确认歌词文件和音频是同一首")
    med = sorted(e - s for _, s, e in timeline)[len(timeline) // 2] or 0.17
    idx = [k for k, m in enumerate(matched) if m]
    for k in range(len(L)):  # 没对上的字：前后插值
        if matched[k]:
            continue
        prev = max((j for j in idx if j < k), default=None)
        nxt = min((j for j in idx if j > k), default=None)
        if prev is not None and nxt is not None:
            a, b = t_end[prev], t_start[nxt]
            f0 = (k - prev - 1) / (nxt - prev - 1)
            f1 = (k - prev) / (nxt - prev - 1)
            t_start[k], t_end[k] = a + (b - a) * f0, a + (b - a) * f1
        elif prev is not None:
            t_start[k] = t_end[prev] + (k - prev - 1) * med
            t_end[k] = t_start[k] + med
        else:
            t_start[k] = t_start[nxt] - (nxt - k) * med
            t_end[k] = t_start[k] + med
    for li, text in enumerate(lyrics):
        ks = [k for k, (_, l2, _) in enumerate(L) if l2 == li]
        if not ks:
            sys.exit(f"第 {li + 1} 句没有可对齐的字：{text}")
        s, e = t_start[ks[0]], t_end[ks[-1]]
        pos_t = {L[k][2]: t_start[k] for k in ks}
        ct, nxt_t = [], e
        for pos in range(len(text) - 1, -1, -1):  # 标点取后一个字的时间
            if pos in pos_t:
                nxt_t = pos_t[pos]
            ct.append(nxt_t)
        ct.reverse()
        lines.append({"i": li + 1, "start": round(s, 3), "end": round(e, 3), "text": text,
                      "ct": [round(x, 3) for x in ct],
                      "match": round(sum(matched[k] for k in ks) / len(ks), 2)})

# 修正：保证时间单调、句与句不重叠
for a, b in zip(lines, lines[1:]):
    if b["start"] < a["start"] + 0.2:
        b["start"] = round(a["start"] + 0.2, 3)
    if a["end"] > b["start"]:
        a["end"] = b["start"]
for ln in lines:
    ln["ct"] = [min(max(x, ln["start"]), ln["end"]) for x in ln["ct"]]

t0 = round(max(0.0, lines[0]["start"] - 0.18), 2)
t_end = round(min(DUR, lines[-1]["end"] + 0.35), 2)

report = {"source": SOURCE, "match_by": MATCH}
on_bar = 0
for ln in lines:
    frac = ((ln["start"] - beat0) / BEAT) % 4
    ln["bar_pos"] = round(frac, 2)
    on_bar += min(frac, 4 - frac) < 0.5
report["lines_on_downbeat"] = f"{on_bar}/{len(lines)}"
low = [ln["i"] for ln in lines if ln["match"] is not None and ln["match"] < 0.5]
report["low_match_lines"] = low

if args.deep and not args.no_beat:
    sep_root = work / "_分离"
    wav = work / "_audio_44k.wav"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(audio), "-ac", "2", "-ar", "44100", str(wav)], check=True)
    r = subprocess.run([sys.executable, "-m", "demucs", "--two-stems=vocals", "-n", "htdemucs", "-o", str(sep_root), str(wav)],
                       capture_output=True, text=True)
    vp = sep_root / "htdemucs" / "_audio_44k" / "vocals.wav"
    if r.returncode == 0 and vp.exists():
        voc, _ = librosa.load(vp, sr=SR, mono=True)
        on = librosa.onset.onset_detect(y=voc, sr=SR, units="time")
        six = BEAT / 4
        pos = (on - beat0) / six
        dev = np.abs(pos - np.round(pos)) * six * 1000
        report["onset_dev_ms_median"] = round(float(np.median(dev)), 1)
        report["onset_within_30ms_pct"] = round(float(np.mean(dev < 30)) * 100, 1)
    else:
        print("demucs 不可用，跳过 --deep", file=sys.stderr)
    shutil.rmtree(sep_root, ignore_errors=True)  # 分离出的音轨只用来测量，不留在作品目录里
    wav.unlink(missing_ok=True)

# ---------------- 结论 ----------------
durs = sorted(ln["end"] - ln["start"] for ln in lines)
med_dur = durs[len(durs) // 2]
skipped = [ln["i"] for ln in lines if (ln["end"] - ln["start"]) < max(0.45, 0.3 * med_dur)
           or (ln["match"] is not None and ln["match"] < 0.2)]
problems = []
if skipped:
    problems.append(f"第 {skipped} 句很可能漏唱或被吞掉")
entry_bars = (lines[0]["start"] - beat0) / BAR
if not args.no_beat:
    if args.intro_bars is not None and entry_bars > args.intro_bars + 0.75:
        problems.append(f"人声在第 {entry_bars:.1f} 小节才进，比约定的前奏 {args.intro_bars:g} 小节晚，后面的歌词通常会被挤")
    span_bars = (lines[-1]["end"] - lines[0]["start"]) / BAR
    if not args.grid and span_bars < 0.88 * len(lines) * args.bars_per_line:
        problems.append(f"{len(lines)} 句只唱了 {span_bars:.1f} 小节，整体被压缩（常见于人声晚进）")
if low and len(low) > max(2, len(lines) // 6):
    problems.append(f"有 {len(low)} 句匹配率低于 50%，音频和歌词出入较大")
report.update(verdict="换一版" if problems else "可用", problems=problems, skipped_lines=skipped,
              entry_bars=round(entry_bars, 2))

out = {"audio": audio.name, "duration": round(DUR, 3), "bpm": bpm, "beat0": beat0, "bar": round(BAR, 4),
       "has_beat": not args.no_beat, "t0": t0, "t_end": t_end, "lines": lines, "report": report}
(work / args.out).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

# ---------------- 报告 ----------------
print(f"音频 {audio.name}，时长 {DUR:.2f} 秒；时间来源：{SOURCE}；按{MATCH}匹配")
if args.no_beat:
    print("未检测节拍（--no-beat）：B 和 beat() 按 90 BPM 名义值计算")
else:
    print(f"速度 {bpm} BPM，第 0 拍在 {beat0} 秒，一小节 {BAR:.3f} 秒")
print(f"人声进入 {lines[0]['start']:.2f} 秒；成片取 {t0}–{t_end} 秒（{t_end - t0:.1f} 秒）")
print(f"落在小节头的句子 {report['lines_on_downbeat']}"
      f"（下面的\"拍位\"是这句开头在小节里的位置，0–4 拍；接近 0 或接近 4 都算落在小节头）")
if "onset_dev_ms_median" in report:
    print(f"卡拍偏差中位数 {report['onset_dev_ms_median']} ms，30ms 内 {report['onset_within_30ms_pct']}%"
          f"（越小越整齐；参考：仿的那条原版视频是 12.5 ms，乱念大约 42 ms）")
for ln in lines:
    flag = ""
    if ln["i"] in skipped:
        flag = "  ← 很可能漏唱了（这句几乎没有时长）"
    elif ln["match"] is not None and ln["match"] < 0.5:
        flag = "  ← 匹配率低，时间是推算的，要人工听"
    m = "  -  " if ln["match"] is None else f"{ln['match'] * 100:4.0f}%"
    print(f"  {ln['i']:2d} {ln['start']:6.2f}–{ln['end']:6.2f} 拍位{ln['bar_pos']:5.2f} 匹配{m}  {ln['text']}{flag}")
gaps = [b["start"] - a["start"] for a, b in zip(lines, lines[1:])]
if gaps and not args.no_beat:
    off = [i + 1 for i, g in enumerate(gaps) if abs(g / BAR - round(g / BAR)) > 0.3]
    if off:
        print(f"提示：第 {off} 句的长度不是整数小节，背景切换点会跟着歌词走，不影响出片")
print("已写入", work / args.out)
if problems:
    print("结论：建议换一版。原因：" + "；".join(problems))
    sys.exit(3)
print("结论：可用。" + ("（有提示项，见上）" if low or (gaps and not args.no_beat and off) else ""))
